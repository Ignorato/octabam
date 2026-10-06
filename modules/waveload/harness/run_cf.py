"""Run the ColdFire build of the fixed engine under the patched Unicorn:
the same command stream as the native build, 16 samples a call. Prints
instructions per sample (eng_render, eng_cmds) and writes raw int32 output."""
import bisect, os, re, struct, subprocess, sys
os.environ.setdefault("LIBUNICORN_PATH", os.path.join(os.path.dirname(__file__), "../../../.venv/lib/unicorn-emac"))
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_BLOCK
from unicorn.m68k_const import UC_M68K_REG_A7

elf, binf, tablef, cmdsf, outf = sys.argv[1:6]
limit = int(sys.argv[6]) if len(sys.argv) > 6 else None
CODE, TABLE, ENG, CMDS, OUT, STACK, RET = 0x10000, 0x100000, 0x200000, 0x210000, 0x220000, 0x3f0000, 0x300000
syms = {m.group(2): int(m.group(1), 16) for m in re.finditer(r"([0-9a-f]+) T (\w+)", subprocess.check_output(["m68k-elf-nm", elf], text=True))}
starts = sorted(int(m.group(1), 16) for m in re.finditer(r"^\s+([0-9a-f]+):\t", subprocess.check_output(["m68k-elf-objdump", "-d", elf], text=True), re.M))

uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
uc.mem_map(0, 0x400000)
uc.mem_write(CODE, open(binf, "rb").read())
uc.mem_write(TABLE, open(tablef, "rb").read())
uc.mem_write(RET, b"\x4e\x71")
# MACSR fractional and ACC0 clear, as WAVE LOAD's cl_load sets them
PROLOGUE = 0x300100
uc.mem_write(PROLOGUE, bytes.fromhex("a93c00000020" "a13c00000000"))
uc.emu_start(PROLOGUE, PROLOGUE + 12)
count = [0]
def on_block(uc, addr, size, _):
    count[0] += bisect.bisect_left(starts, addr + size) - bisect.bisect_left(starts, addr)
uc.hook_add(UC_HOOK_BLOCK, on_block)

def call(fn, *args):
    sp = STACK - 4 * len(args) - 4
    uc.mem_write(sp, struct.pack(">I" + "I" * len(args), RET, *[a & 0xffffffff for a in args]))
    uc.reg_write(UC_M68K_REG_A7, sp)
    count[0] = 0
    uc.emu_start(fn, RET)
    return count[0]

data = open(cmdsf, "rb").read()
pos, out, blocks = 0, open(outf, "wb"), 0
n_render = n_cmds = 0
worst = 0
while pos < len(data) and (limit is None or blocks <= limit):
    n = struct.unpack_from(">I", data, pos)[0]; pos += 4
    uc.mem_write(CMDS, data[pos:pos + 8 * n]); pos += 8 * n
    n_cmds += call(syms["eng_cmds"], ENG, CMDS, n)
    if blocks == 0:          # the first record is init; no render follows it
        blocks = 1
        continue
    r = call(syms["eng_render"], ENG, OUT, 16)
    n_render += r; worst = max(worst, r)
    out.write(bytes(uc.mem_read(OUT, 64)))
    blocks += 1
out.close()
nb = blocks - 1
print(f"blocks {nb}  eng_render {n_render / (16 * nb):.1f} instr/sample mean, worst block {worst / 16:.1f}/sample; eng_cmds {n_cmds / (16 * nb):.2f} instr/sample")
