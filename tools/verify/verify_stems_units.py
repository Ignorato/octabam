#!/usr/bin/env python3
"""STEM REC's ColdFire routines, one at a time, in Unicorn: no boot, no DSP.

    python3 tools/verify/verify_stems_units.py [test ...]

Loads the built runtime (out/platform/runtime/runtime.bin at its .text
base, inside the platform's DRAM reserve), maps the memory the routines read
(the SRAM at 0x80000000, the page holding the input ring's index, a stack),
and calls one routine with its registers set. The image's gain-table words
are deliberately not mapped: the OS reuses that RAM after the upload
(docs/firmware/STEM_REC.md 18.4), so a routine that reads them faults here.
The Unicorn is the one tools/emu/emu_bringup.py selects: the repository's
patched build, whose EMAC multiplies in fractional mode as the MCF5445x
does. The harness refuses to run when that self-test fails. Each test
compares a routine with tools/verify/stems_gain.py or a reference beside
it (docs/superpowers/plans/2026-10-01-stem-rec-sources.md, "Testing")."""
import pathlib
import random  # noqa: F401  (the tests that follow draw their inputs from it)
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools/emu", "tools", "tools/verify"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa: E402,F401
import emu_bringup  # noqa: E402  (exports LIBUNICORN_PATH before unicorn loads)
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN  # noqa: E402
from unicorn import m68k_const as K  # noqa: E402
import stems_gain as sg  # noqa: E402,F401

# The constants of modules/stems/stems.s these tests depend on. Each task
# that adds one to stems.s copies its value here.
GQ_N = 4
SRC_BITS = 0xff                                         # Task 8: 0xfff
GAIN_LAG, TRACK_HALF, TRACK_DELAY = 2, 1, 1             # STEM_REC.md 18.5
IN_RING, IN_IDX = 0x80005660, 0x46104d00                # STEM_REC.md 18.7: eight frame pages, the index
IN_AB_OFF, IN_CD_OFF, IN_A_IS_LEFT = 0x80, 0x00, 1      # STEM_REC.md 18.7: within a page

RESERVE = (0x40a95000, 0x41496000)        # the platform reserve, page-aligned (docs/contributing/PLACEMENT.md)
SRAM = (0x80000000, 0x10000)
IDX_PAGE = (IN_IDX & ~0xfff, 0x1000)
TABLE = 0x400ea18a                        # X:0x6c00's words in the stock slice, 3 bytes LE (18.4)
STOP, STACK = 0x00010000, 0x00030000
fails = 0
UNITS = []


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1


def unit(f):
    UNITS.append(f)
    return f


class Rt:
    REGS = {**{f"d{i}": getattr(K, f"UC_M68K_REG_D{i}") for i in range(8)},
            **{f"a{i}": getattr(K, f"UC_M68K_REG_A{i}") for i in range(7)}}

    def __init__(self):
        ok, why = emu_bringup.emac_selftest()
        if not ok:
            sys.exit(f"the EMAC self-test fails ({why}): run scripts/build_unicorn.sh (plan Task 4b)")
        rt = ROOT / "out/platform/runtime"
        nm = subprocess.check_output(["m68k-elf-nm", str(rt / "runtime.elf")], text=True)
        self.s = {f[2]: int(f[0], 16) for f in (line.split() for line in nm.splitlines()) if len(f) == 3}
        hdr = subprocess.check_output(["m68k-elf-objdump", "-h", str(rt / "runtime.elf")], text=True)
        base = int(next(line.split()[3] for line in hdr.splitlines()
                        if len(line.split()) > 3 and line.split()[1] == ".text"), 16)
        self.uc = uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(K.UC_CPU_M68K_CFV4E)
        uc.mem_map(RESERVE[0], RESERVE[1] - RESERVE[0])
        uc.mem_write(base, (rt / "runtime.bin").read_bytes())
        uc.mem_map(*SRAM)
        uc.mem_map(*IDX_PAGE)
        uc.mem_map(STOP & ~0xfff, STACK - (STOP & ~0xfff))
        img = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
        t0 = TABLE - 0x40000400
        self.table = [int.from_bytes(img[t0 + 3 * i:t0 + 3 * i + 3], "little") for i in range(258)]
        uc.reg_write(K.UC_M68K_REG_SR, 0x2700)

    def call(self, name, **regs):
        uc = self.uc
        for r, v in regs.items():
            uc.reg_write(self.REGS[r], v & 0xffffffff)
        uc.reg_write(K.UC_M68K_REG_A7, STACK - 4)
        uc.mem_write(STACK - 4, struct.pack(">I", STOP))
        uc.emu_start(self.s[name], STOP, count=2_000_000)
        assert uc.reg_read(K.UC_M68K_REG_PC) == STOP, f"{name} did not return"
        sp = uc.reg_read(K.UC_M68K_REG_A7)
        assert sp == STACK, f"{name}: the stack is off by {sp - STACK}"
        return {r: uc.reg_read(n) for r, n in self.REGS.items()}

    def wmem(self, a, b):
        self.uc.mem_write(a, bytes(b))

    def rmem(self, a, n):
        return bytes(self.uc.mem_read(a, n))

    def w32(self, a, v):
        self.wmem(a, (v & 0xffffffff).to_bytes(4, "big"))

    def r32(self, a):
        return int.from_bytes(self.rmem(a, 4), "big")

    def r32s(self, a):
        return int.from_bytes(self.rmem(a, 4), "big", signed=True)


def main():
    names = sys.argv[1:]
    rt = Rt()
    for f in UNITS:
        if not names or f.__name__ in names:
            print(f"== {f.__name__}")
            f(rt)
    print(f"verify_stems_units: {fails} failure(s)")
    return 1 if fails else 0


@unit
def layout_now(rt):
    """The harness on code that exists: piece 3's stems_layout for one and
    eight tracks. Task 7 replaces it with the file table's test."""
    s = rt.s
    for mask, nt in ((0x01, 1), (0xff, 8)):
        rt.w32(s["stems_tracks"], mask)
        rt.call("stems_layout")
        got = tuple(rt.r32(s[n]) for n in ("stems_nt", "stems_fbytes", "stems_rframes", "stems_rlimit"))
        want = (nt, 64 * nt, 0x400000 // (64 * nt), 0x400000 // (64 * nt) * 64 * nt)
        check(f"layout_now: mask {mask:#04x}", got == want, f"{got} vs {want}")


if __name__ == "__main__":
    sys.exit(main())
