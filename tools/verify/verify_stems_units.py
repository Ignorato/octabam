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


_asm_cache = {}


def assemble(src):
    """ColdFire text -> bytes, assembled as the platform assembles a DRAM
    unit (-mcpu=54455), in a private scratch directory (AGENTS.md: never a
    fixed /tmp name)."""
    if src not in _asm_cache:
        import shutil
        import tempfile
        d = pathlib.Path(tempfile.mkdtemp(prefix="stems_units_"))
        try:
            (d / "s.s").write_text(src)
            subprocess.run(["m68k-elf-as", "-mcpu=54455", "-o", str(d / "s.o"), str(d / "s.s")], check=True)
            subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text", str(d / "s.o"), str(d / "s.bin")],
                           check=True)
            _asm_cache[src] = (d / "s.bin").read_bytes()
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return _asm_cache[src]


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

    CODE, SAVE = 0x00020000, 0x00021000     # scratch code and its results, inside the stack's mapping

    def run(self, code):
        self.uc.mem_write(self.CODE, code)
        self.uc.emu_start(self.CODE, self.CODE + len(code))

    def set_emac(self, macsr, acc0, accext01):
        """The interrupted code's EMAC state, as the hook finds it: written in
        integer mode, then its MACSR."""
        self.run(assemble(f"""
        moveq   #0,%d0
        move.l  %d0,%macsr
        move.l  #{acc0:#x},%d0
        move.l  %d0,%acc0
        move.l  #{accext01:#x},%d0
        move.l  %d0,%accext01
        move.l  #{macsr:#x},%d0
        move.l  %d0,%macsr
"""))

    def get_emac(self):
        """(MACSR, ACC0, ACCEXT01), ACC0 and ACCEXT01 read in integer mode."""
        self.run(assemble(f"""
        move.l  %macsr,%d0
        move.l  %d0,{self.SAVE:#x}
        moveq   #0,%d1
        move.l  %d1,%macsr
        move.l  %acc0,%d1
        move.l  %d1,{self.SAVE + 4:#x}
        move.l  %accext01,%d1
        move.l  %d1,{self.SAVE + 8:#x}
        move.l  %d0,%macsr
"""))
        return tuple(self.r32(self.SAVE + 4 * i) for i in range(3))


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


LV_PAGES, LV_SENT = 0x80005460, 0x80004804      # STEM_REC.md 18.1: four pages, the index sent
DIRTY_EMAC = (0x40, 0x5a5a5a5a, 0x00a5005a)     # an interrupted task's EMAC: MACSR, ACC0, ACCEXT01


def random_page(rng):
    page = [0] * 64
    for k in range(8):
        page[4 * k + 1] = rng.choice((0, 0x4000, 0x7f00, 0x8000, rng.randrange(0x10000)))
        page[4 * k + 2] = rng.choice((0x7f00, 0, rng.randrange(0x8000)))
        page[4 * k + 3] = rng.randrange(16) if rng.random() < 0.4 else 0
    page[0x29] = rng.choice((0x40, 0x7f, 0x80, rng.randrange(0x100)))
    return page


def send_page(rt, idx, page):
    rt.wmem(LV_PAGES + 0x80 * idx, b"".join(w.to_bytes(2, "big") for w in page))
    rt.w32(LV_SENT, idx)


def mirror_reset(rt):
    s = rt.s
    rt.w32(s["stems_state"], 1)                     # ARMED: the gains are written
    rt.w32(s["stems_lvlast"], 0xffffffff)
    rt.w32(s["stems_gqn"], 0)
    rt.w32(s["stems_lvskip"], 0)
    rt.wmem(s["stems_gstate"], bytes(96))
    rt.wmem(s["stems_gcache"], b"\xff" * 64)
    rt.w32(s["stems_gw29"], 0xffffffff)


def mirror_read(rt):
    s = rt.s
    state = [[rt.r32s(s["stems_gstate"] + 12 * k + 4 * f) for f in range(3)] for k in range(8)]
    q = s["stems_gq"] + ((rt.r32(s["stems_gqn"]) - 1) % GQ_N) * 512
    gq = [[rt.r32s(q + 64 * k + 4 * j) for j in range(16)] for k in range(8)]
    return state, gq


@unit
def mirror(rt, n=4000, seed=5):
    """stems_mirror against stems_gain.Mirror: n random pages through the
    four-page ring, a third of them repeated (the target cache), with the
    edges of the arithmetic (levels 0, 0x4000, 0x7f00, 0x8000 = -1.0, any;
    the MAIN level 0x40, 0x7f, 0x80 = -1.0, any; splits 0-15). Before every
    call the EMAC holds an interrupted task's state, ACC0 not zero. After
    every page: the state of all eight slots and their 16 gains equal the
    model's, the caller's EMAC state reads back as it went in, and every
    register is as it was."""
    s = rt.s
    model = sg.Mirror(rt.table)
    mirror_reset(rt)
    rt.set_emac(*DIRTY_EMAC)
    caller = rt.get_emac()
    regs = {r: (0x10203040 + 0x01010101 * i) & 0xffffffff for i, r in enumerate(rt.REGS)}
    rng = random.Random(seed)
    page, first, emac, kept = [0] * 64, None, None, None
    for i in range(n):
        if i == 0 or rng.random() > 0.33:
            page = random_page(rng)
        send_page(rt, i % 4, page)
        rt.set_emac(*DIRTY_EMAC)
        out = rt.call("stems_mirror", **regs)
        if emac is None and rt.get_emac() != caller:
            emac = (i, rt.get_emac(), caller)
        if kept is None and any(out[r] != v for r, v in regs.items()):
            kept = (i, {r: hex(out[r]) for r, v in regs.items() if out[r] != v})
        want = model.step(page)
        state, gq = mirror_read(rt)
        if state != model.state or gq != want:
            first = (i, state[0], model.state[0], gq[0][:4], want[0][:4])
            break
    check(f"mirror: {n} pages, every slot's state and gains equal the model", first is None,
          f"first difference (page, mirror, model, gains, model's): {first}" if first else "")
    check("mirror: the caller's MACSR, ACC0 and ACCEXT01 come back", emac is None,
          f"page, after, before: {emac}" if emac else f"{tuple(hex(v) for v in caller)}")
    check("mirror: every register comes back", kept is None, f"page, changed: {kept}" if kept else "")
    check("mirror: no page index jump counted", rt.r32(s["stems_lvskip"]) == 0)


@unit
def mirror_cache_mark(rt):
    """The target cache marks every entry stale with the key 0xffffffff when
    the MAIN level changes. A slot whose level and index words are both
    0xffff has that key for real: it must still get its own target (0: the
    index is below the table), not the stale one."""
    model = sg.Mirror(rt.table)
    mirror_reset(rt)
    page = [0] * 64
    for k in range(8):
        page[4 * k + 1], page[4 * k + 2] = 0x7f00, 0x7f00
    page[0x29] = 0x40
    send_page(rt, 0, page)
    rt.call("stems_mirror")
    model.step(page)
    page = list(page)
    page[1], page[2], page[0x29] = 0xffff, 0xffff, 0x7f      # slot 0's key is the stale mark
    send_page(rt, 1, page)
    rt.call("stems_mirror")
    model.step(page)
    state, _ = mirror_read(rt)
    check("mirror_cache_mark: a real key of 0xffffffff gets its own target", state[0] == model.state[0],
          f"mirror {state[0]}, model {model.state[0]}")


@unit
def mirror_idx4(rt):
    """The fourth frame writes the sent index 4, then 0 (STEM_REC.md 18.1).
    A 4 seen between the two is not a page: nothing changes, nothing is
    counted, and the 0 that follows is mirrored as the wrap it is."""
    s = rt.s
    mirror_reset(rt)
    rng = random.Random(7)
    for i in range(4):
        send_page(rt, i, random_page(rng))
        rt.call("stems_mirror")
    before = (mirror_read(rt), rt.r32(s["stems_gqn"]), rt.r32(s["stems_lvlast"]))
    rt.w32(LV_SENT, 4)
    rt.call("stems_mirror")
    after = (mirror_read(rt), rt.r32(s["stems_gqn"]), rt.r32(s["stems_lvlast"]))
    check("mirror_idx4: an index of 4 changes nothing", after == before,
          f"gqn {before[1]} -> {after[1]}, lvlast {before[2]} -> {after[2]}")
    send_page(rt, 0, random_page(rng))
    rt.call("stems_mirror")
    check("mirror_idx4: the 0 after it is a page, and no jump", rt.r32(s["stems_gqn"]) == before[1] + 1
          and rt.r32(s["stems_lvskip"]) == 0, f"gqn {rt.r32(s['stems_gqn'])}, skip {rt.r32(s['stems_lvskip'])}")


if __name__ == "__main__":
    sys.exit(main())
