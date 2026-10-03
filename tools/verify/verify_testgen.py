#!/usr/bin/env python3
"""TESTGEN render gates, against exact arithmetic and the float reference
(modules/testgen/testgen_ref.py).

Renders the module straight through dsp_host (the render-gate shape: the id
and the slots come from the manifest, and the entry points are checked
against SEND's so an absent module cannot pass as a passthrough).

Gates:
  replaces       -> the output does not depend on the input (noise in, silence in)
SINE
  the law        -> every FREQ index matches sin(2 pi n inc / 2^24) at LEVL 127
                    within 4 LSB, from sample 0 (the phase starts at 0)
  frequency      -> each tone's measured frequency is ISO_THIRDS[k] within 0.003 Hz
  THD            -> 1 kHz and 100 Hz at 0 dBFS below -120 dB
  level          -> LEVL k is (127 - k) * 0.5 dB below full scale within 0.01 dB,
                    for k = 1..127; LEVL 127 peaks within 1 LSB of full scale;
                    LEVL 0, the default, is silent in every MODE
  CHAN           -> L+R equal; L only has R silent; R only has L silent;
                    L and inverted R has R = -L within 1 LSB
SWEEP          -> the reference's exact phase law (testgen_ref.sweep_phases) within
                    4 LSB over two whole periods (1 s) and one (16 s); the P table's
                    growth constants equal the reference's; deconvolved through an
                    identity path it is flat within 0.5 dB, 40 Hz-16 kHz
WHITE          -> the reference's 24-bit generator within 1 LSB; flat within 0.3 dB/octave
PINK           -> -3 dB/octave within 0.3, no octave band more than 1 dB off the fit;
                    the float filter on the same noise within -60 dB; RMS within 0.1 dB
IMPULSE        -> full scale (within 1 LSB) at exactly the reference's positions, zero
                    everywhere else
an invalid MODE byte -> SINE
every knob     -> renders without dsp_host dying

    python3 tools/verify/verify_testgen.py
"""
import importlib.util, math, pathlib, struct, subprocess, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe  # dispatch-table entry resolution
from remix import registry

ROOT = pathlib.Path(__file__).resolve().parents[2]
MOD = registry.by_name("testgen")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES = 15
TMP = pathlib.Path("out/_tggate")
TMP.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location("testgen_ref", ROOT / "modules/testgen/testgen_ref.py")
REF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REF)
FS = REF.FS
_mspec = importlib.util.spec_from_file_location("testgen_manifest", ROOT / "modules/testgen/manifest.py")
MAN = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(MAN)

# Rebuild the dump every run: a stale audition image measures whatever the id
# pointed at last (verify_character's warning). audition.py exits non-zero
# after building when it has no dry file to render; the image is what we need.
pathlib.Path(MEM).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/remix/audition.py", MOD.name, "out/dry/drums_110.wav"],
               capture_output=True)
if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM} -- build it first:\n  python3 tools/remix/audition.py {MOD.name} out/dry/drums_110.wav")
init, proc = send_probe.entry_points(MEM, FXID)
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} resolves to SEND's entry points -- {MOD.name} is NOT in this dump")
print(f"entries from dispatch tables: init=P:0x{init:04x} proc=P:0x{proc:04x}")

DEFAULTS = [(p.default or 0) for p in MOD.params]
FULL = (1 << 23) - 1


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def render(n, src=None, **kw):
    """n frames; src: MONO Q23 ints fed to both channels (silence if None). Returns (L, R) arrays."""
    n -= n % FRAMES
    src = [0] * n if src is None else src[:n]
    fin, fout = TMP / "tg_in.raw", TMP / "tg_out.raw"
    fin.write_bytes(b"".join(struct.pack("<i", m) for m in src))
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1",
           "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
           "-in", str(fin), "-out", str(fout),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    w = np.frombuffer(fout.read_bytes(), dtype="<i4").astype(np.int64)
    return w[0::2][:n], w[1::2][:n]


FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def exact(k, n, level=1.0):
    """The sine the accumulator defines: phase n * inc mod 2^24, a cycle 2^24."""
    inc = MAN.FINC[k]
    ph = (np.arange(n, dtype=np.int64) * inc) % (1 << 24)
    return level * np.sin(2 * np.pi * ph / (1 << 24))


def rms_db(x):
    return 20 * math.log10(math.sqrt(float(np.mean(np.asarray(x, float) ** 2))) / (1 << 23))


def measured_hz(x):
    """Frequency by a linear fit to the unwrapped analytic phase (Hilbert by FFT)."""
    x = np.asarray(x, float)
    X = np.fft.fft(x)
    h = np.zeros(len(x)); h[0] = 1; h[1:(len(x) + 1) // 2] = 2
    if len(x) % 2 == 0:
        h[len(x) // 2] = 1
    ph = np.unwrap(np.angle(np.fft.ifft(X * h)))
    m = slice(len(x) // 8, len(x) - len(x) // 8)   # away from the FFT's edges
    t = np.arange(len(x))[m] / FS
    return float(np.polyfit(t, ph[m], 1)[0] / (2 * np.pi))


N = int(FS)   # one second

# ---- replaces its input ------------------------------------------------------------
rng = np.random.default_rng(3)
noise = [int(v) for v in rng.integers(-(1 << 23), 1 << 23, N)]
Ls, Rs = render(N, LEVL=127)
Ln, Rn = render(N, noise, LEVL=127)
check("replaces: the output is the same with noise in and with silence in",
      np.array_equal(Ls, Ln) and np.array_equal(Rs, Rn))

# ---- the law, every FREQ index ----------------------------------------------------------
worst, worst_k = 0, None
for k in range(len(MAN.ISO_THIRDS)):
    L, R = render(N, LEVL=127, FREQ=k)
    ref = exact(k, len(L)) * FULL
    e = int(np.max(np.abs(L - ref)))
    if e > worst:
        worst, worst_k = e, k
    if k in (0, 17, 30):
        print(f"  [info] FREQ {k} ({MAN.ISO_THIRDS[k]} Hz): max error {e} LSB, first samples {[int(v) for v in L[:3]]}")
check(f"the law: every FREQ index within 4 LSB of the exact phase-accumulator sine, from sample 0",
      worst <= 4, f"(worst {worst} LSB at FREQ {worst_k})")
L, _ = render(N, LEVL=127, FREQ=99)
check("FREQ above 30 holds at 20 kHz", np.array_equal(L, render(N, LEVL=127, FREQ=30)[0]))

# ---- frequency -------------------------------------------------------------------------
fworst = 0.0
for k in range(len(MAN.ISO_THIRDS)):
    L, _ = render(N, LEVL=127, FREQ=k)
    fworst = max(fworst, abs(measured_hz(L) - REF.freq_hz(k)))
check("frequency: every ISO third within 0.003 Hz of nominal", fworst < 0.003, f"(worst {fworst:.5f} Hz)")
L, _ = render(N, LEVL=127, FREQ=17)
print(f"  [info] FREQ 17 measures {measured_hz(L):.4f} Hz (the increment gives {MAN.FINC[17] * FS / (1 << 24):.4f})")

# ---- THD ----------------------------------------------------------------------------------
for k in (17, 7):
    L, _ = render(1 << 16, LEVL=127, FREQ=k)
    t = REF.thd_db(np.asarray(L, float) / (1 << 23), REF.freq_hz(k))
    check(f"THD at {REF.freq_hz(k)} Hz, 0 dBFS: {t:.1f} dB", t < -120)

# ---- level ------------------------------------------------------------------------------
L127, _ = render(N, LEVL=127)
r127 = rms_db(L127)
check(f"LEVL 127 peaks within 1 LSB of full scale", abs(int(np.max(np.abs(L127))) - FULL) <= 1,
      f"(peak {int(np.max(np.abs(L127)))}, RMS {r127:.3f} dBFS)")
lworst = 0.0
for k in range(1, 128):
    L, _ = render(N // 4, LEVL=k)
    lworst = max(lworst, abs((rms_db(L) - rms_db(L127[:len(L)])) + (127 - k) * 0.5))
check("level: every LEVL step is 0.5 dB exactly within 0.01 dB (1 = -63 dB)", lworst < 0.01,
      f"(worst {lworst:.4f} dB)")
silent = all(not np.any(np.concatenate(render(N // 8, MODE=m, LEN=0))) for m in range(5))
check("LEVL 0, the default: every MODE is silent (no sound until LEVL is turned up)",
      silent and DEFAULTS[K["LEVL"]] == 0)

# ---- CHAN ---------------------------------------------------------------------------------
L, R = render(N, LEVL=127, CHAN=0)
check("CHAN L+R: both channels equal", np.array_equal(L, R) and np.any(L))
L, R = render(N, LEVL=127, CHAN=1)
check("CHAN L: R silent", np.any(L) and not np.any(R))
L, R = render(N, LEVL=127, CHAN=2)
check("CHAN R: L silent", np.any(R) and not np.any(L))
L, R = render(N, LEVL=127, CHAN=3)
check("CHAN L and inverted R: R = -L within 1 LSB", np.any(L) and int(np.max(np.abs(L + R))) <= 1)

MODE = {name: i for i, name in enumerate(MAN.MODE_LABELS)}
GAP = REF.SWEEP_GAP

# ---- SWEEP --------------------------------------------------------------------------------------
check("SWEEP: the P table's growth constants are the reference's",
      MAN.SWD == tuple(REF.sweep_d(t) for t in range(16)) and MAN.SWN == tuple(REF.len_seconds(t) * int(FS) for t in range(16)))
for t, periods in ((0, 2), (15, 1)):
    n = periods * (REF.len_seconds(t) * int(FS) + GAP) + 3000
    L, R = render(n, LEVL=127, MODE=MODE["SWEP"], LEN=8 * t)
    ref = REF.sweep_dsp(t, len(L)) * FULL
    e = int(np.max(np.abs(L - ref)))
    check(f"SWEEP {REF.len_seconds(t)} s: within 4 LSB of the exact phase law over {periods} period(s) and the next start",
          e <= 4 and np.array_equal(L, R), f"(worst {e} LSB)")
L, _ = render(2 * int(FS) + GAP, LEVL=127, MODE=MODE["SWEP"], LEN=0)
h = REF.deconvolve(np.asarray(L[:2 * int(FS) + GAP], float) / FULL, f1=REF.SWEEP_INC0 * FS / (1 << 24), T=1.0)
pk = int(np.argmax(np.abs(h)))
seg = h[pk - 4096:pk + 4096] * np.hanning(8192)
Hm = np.abs(np.fft.rfft(seg, 1 << 15)); fr = np.fft.rfftfreq(1 << 15, 1 / FS)
band = (fr >= 40) & (fr <= 16000)
flat = float(np.max(np.abs(20 * np.log10(Hm[band] / np.median(Hm[band])))))
check(f"SWEEP 1 s deconvolved through an identity path: flat within {flat:.2f} dB, 40 Hz-16 kHz", flat < 0.5)

# ---- WHITE ----------------------------------------------------------------------------------------
L, R = render(N, LEVL=127, MODE=MODE["WHIT"])
w = REF.white_q23(len(L))
e = int(np.max(np.abs(L - w)))
check("WHITE: the reference's 24-bit generator within 1 LSB", e <= 1 and np.array_equal(L, R), f"(worst {e} LSB)")
L, _ = render(1 << 20, LEVL=127, MODE=MODE["WHIT"])
sl, dev = REF.octave_slope_db(np.asarray(L, float))
check(f"WHITE: slope {sl:+.3f} dB/octave, worst octave band {dev:.2f} dB off", abs(sl) < 0.3 and dev < 1.0)

# ---- PINK -----------------------------------------------------------------------------------------
L, R = render(1 << 20, LEVL=127, MODE=MODE["PINK"])
x = np.asarray(L, float) / (1 << 23)
sl, dev = REF.octave_slope_db(x)
check(f"PINK: slope {sl:+.3f} dB/octave, worst octave band {dev:.2f} dB off", abs(sl + 3.0) < 0.3 and dev < 1.0)
ref = REF.pink(len(x))
err = 20 * math.log10(np.sqrt(np.mean((x - ref) ** 2)) / np.sqrt(np.mean(ref ** 2)))
lv = 20 * math.log10(np.sqrt(np.mean(x ** 2))) - 20 * math.log10(np.sqrt(np.mean(ref ** 2)))
check(f"PINK: the float filter on the same noise within {err:.1f} dB; RMS {rms_db(L):.2f} dBFS ({lv:+.3f} dB)",
      err < -60 and abs(lv) < 0.1 and np.array_equal(L, R))

# ---- IMPULSE ---------------------------------------------------------------------------------------
for t in (0, 3):
    n = 3 * (t + 1) * REF.IMPULSE_UNIT + 100
    L, R = render(n, LEVL=127, MODE=MODE["IMPL"], LEN=8 * t)
    where = np.nonzero(L)[0]
    want = REF.impulse_positions(t, len(L))
    check(f"IMPULSE every {(t + 1) / 4:g} s: full scale at exactly the reference's positions, zero elsewhere",
          np.array_equal(where, want) and int(np.min(L[want])) >= FULL - 1 and np.array_equal(L, R),
          f"({len(where)} impulses, at {[int(i) for i in where]})")

# ---- an invalid MODE byte ----------------------------------------------------------------------------
check("an invalid MODE byte (7) plays SINE", np.array_equal(render(N // 4, LEVL=127, MODE=7)[0], render(N // 4, LEVL=127, MODE=0)[0]))

# ---- every knob at both ends renders ----------------------------------------------------------
for name, hi in (("LEVL", 127), ("FREQ", 127), ("LEN", 127), ("MODE", 4), ("CHAN", 3)):
    for v in (0, hi):
        render(N // 8, noise, **{name: v})
check("every knob at both ends renders", True)

if FAILS:
    sys.exit(f"verify_testgen: {len(FAILS)} gate(s) failed")
print("verify_testgen: OK")
