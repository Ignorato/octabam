#!/usr/bin/env python3
"""TRANSIENT render gates, against arithmetic you can predict and the float
reference (modules/transient/transient_ref.py).

Renders the module straight through dsp_host (the render-gate shape: the id
and the slots come from the manifest, and the entry points are checked
against SEND's so an absent module cannot pass as a dry passthrough).

Gates:
  defaults      -> bit-exact passthrough of a full-scale bipolar ramp and noise
  MIX = 0       -> bit-exact passthrough with ATCK and SUST at their extremes
  both signs    -> a negated input gives the negated output within 4 LSB
                   (truncation; an mpysu would be off by millions)
  the law       -> the per-sample gain on a tone burst matches the float
                   reference within 0.1 dB, for ATCK +-max and SUST +-max
  level         -> the same burst on a scaled noise bed at -18/-33/-48 dBFS
                   gets the same gain within 0.1 dB (above the -96 dB floor)
  no spike      -> SUST +63 does not raise the onset peak of a quieter hit
                   inside a louder hit's tail
  no clicks     -> SUST +63 on a decaying noise tail steps the gain by under
                   0.5 dB between samples
  steady tone   -> no pumping: a settled 1 kHz sine moves by under 0.25 dB
  every knob    -> renders without dsp_host dying

    python3 tools/verify/verify_transient.py
"""
import importlib.util, pathlib, struct, subprocess, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe  # dispatch-table entry resolution
from remix import registry

ROOT = pathlib.Path(__file__).resolve().parents[2]
MOD = registry.by_name("transient")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES = 15
TMP = pathlib.Path("out/_trgate")
TMP.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location("transient_ref", ROOT / "modules/transient/transient_ref.py")
REF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REF)
FS = int(REF.FS)

# Rebuild the dump every run: a stale audition image measures whatever the id
# pointed at last (verify_character's warning).
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
KNOBS = ("ATCK", "SUST", "TIME", "OUT", "MIX")


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def q23(x):
    return [max(-(1 << 23), min((1 << 23) - 1, int(round(s * (1 << 23))))) for s in x]


def render(samples, **kw):
    """samples: MONO ints in Q23, fed to both channels. Returns (L, R) ints."""
    n = len(samples) - len(samples) % FRAMES
    src, out = TMP / "tr_in.raw", TMP / "tr_out.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples[:n]))
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1",
           "-frames", str(FRAMES), "-blocks", str(n // FRAMES),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    w = struct.unpack(f"<{len(out.read_bytes()) // 4}i", out.read_bytes())
    return list(w[0::2])[:n], list(w[1::2])[:n]


FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def gain_db(inp, outp, mask):
    i = np.asarray(inp, float)[mask]
    o = np.asarray(outp, float)[mask]
    return 20 * np.log10(np.abs(o) / np.abs(i))


# ---- bit-exact passthroughs ---------------------------------------------------
N = 6000
ramp = [int((i * 2 * (1 << 23) // N) - (1 << 23)) for i in range(N)]
rng = np.random.default_rng(7)
noise = q23(rng.uniform(-0.999, 0.999, N))
for label, sig in (("ramp", ramp), ("noise", noise)):
    L, R = render(sig)
    check(f"defaults: bit-exact passthrough ({label})", L == sig[:len(L)] and R == sig[:len(R)])
    L, R = render(sig, MIX=0, ATCK=127, SUST=0, TIME=0, OUT=127)
    check(f"MIX 0: bit-exact passthrough with ATCK/SUST/OUT at extremes ({label})",
          L == sig[:len(L)] and R == sig[:len(R)])

# ---- both signs --------------------------------------------------------------
b = REF.burst(level_db=-20.0)[:, 0]   # +12 dB of ATCK stays below full scale
bq = q23(b)
Lp, _ = render(bq, ATCK=127, SUST=0)
Ln, _ = render([-s for s in bq], ATCK=127, SUST=0)
# Truncation is not antisymmetric in two's complement (floor(-y) != -floor(y)).
# The output path truncates twice: (wet-dry)/2 into x0 (then doubled) and the
# store, so up to 3 LSB; allow 4. An mpysu on a negative operand would be
# wrong by millions of LSB.
sdev = max(abs(a + b) for a, b in zip(Lp, Ln))
check(f"both signs: negated input -> negated output within 4 LSB (max {sdev} LSB)", sdev <= 4)

# ---- the law, against the float reference -------------------------------------
x = REF.burst(level_db=-20.0)   # +12 dB of gain stays below full scale (the DSP clips; the reference does not)
xq = q23(x[:, 0])
mask = np.abs(np.asarray(xq[: len(xq) - len(xq) % FRAMES], float)) > (1 << 23) * 10 ** (-60 / 20)
for kw in (dict(ATCK=127), dict(ATCK=0), dict(SUST=127), dict(SUST=0), dict(ATCK=127, SUST=0, TIME=127)):
    L, R = render(xq, **kw)
    ref = REF.process(np.asarray(xq, float)[:, None].repeat(2, 1) / (1 << 23),
                      **{k.lower(): v for k, v in kw.items()})[: len(L), 0] * (1 << 23)
    gd = gain_db(xq[: len(L)], L, mask[: len(L)])
    gr = gain_db(xq[: len(L)], ref, mask[: len(L)])
    dev = float(np.max(np.abs(gd - gr)))
    peak = float(np.max(np.abs(gd)))
    check(f"law vs float reference {kw}: max gain difference {dev:.3f} dB (peak gain {peak:+.2f} dB)",
          dev < 0.1 and L == R)

# ---- no sustain spike on an onset inside a louder hit's tail ---------------------
# A -20 dBFS kick-like burst (60 ms decay), then a -32 dBFS hit 150 ms later,
# inside the first one's 500 ms hold and above its tail. With SUST +63 the
# hit's peak in its first 5 ms must not be raised: law v1 raised every onset of
# a drum loop by up to +12 dB, heard as a spike (3 Oct 2026). The hit starts at
# full amplitude (cosine phase), as a sample does.
def _hit(level_db, n, decay_ms=150.0):
    t = np.arange(n) / FS
    return 10 ** (level_db / 20) * np.exp(-t / (decay_ms * 1e-3)) * np.cos(2 * np.pi * 1000 * t)
b1 = REF.burst(level_db=-20.0, dur_s=0.15, gap_s=0.05, decay_ms=60.0)[:, 0]
o2 = len(b1)
# The tail's fast envelope F sits near -35 dBFS when the hit arrives. A hit at
# -26 dBFS is a new hit by the law (more than 0.5 bit = 3 dB above F); a hit
# at -32 dBFS is within the margin, indistinguishable from ripple, and shares
# the tail's boost (reported, not gated; DESIGN.md).
for label, b2 in (("hit 9 dB above the tail, full-amplitude start", _hit(-26.0, int(0.4 * FS))),
                  ("hit 9 dB above the tail, zero-phase start (info)", REF.burst(level_db=-26.0, dur_s=0.4, gap_s=0.0, rise_ms=0.05)[:, 0]),
                  ("hit 3 dB above the tail, within the margin (info)", _hit(-32.0, int(0.4 * FS)))):
    pq = q23(np.concatenate([b1, b2]))
    L, _ = render(pq, SUST=127)
    w = slice(o2, o2 + int(0.005 * FS))
    sp = 20 * np.log10(max(abs(v) for v in L[w]) / max(abs(v) for v in pq[w]))
    if label.endswith("(info)"):
        print(f"  [info] SUST +63, quieter hit inside a louder tail, {label}: onset peak {sp:+.2f} dB "
              f"(within the margin, or a sine's first quarter cycle below it, shares the tail's boost; DESIGN.md)")
    else:
        check(f"SUST +63, quieter hit inside a louder tail, {label}: onset peak {sp:+.2f} dB (under +0.5 dB)", sp < 0.5)

# ---- no clicks in a tail ----------------------------------------------------------
# A decaying noise burst (a snare-like tail) with SUST +63: after its first
# 10 ms the gain may not step by more than 0.5 dB between samples. Law v2 (a
# new hit = v > F, no margin) stepped by up to 12 dB in tails, heard as clicks
# (3 Oct 2026); with the 0.5-bit margin the float reference steps 0.05 dB.
tn = np.arange(int(0.5 * FS)) / FS
sn = np.concatenate([np.zeros(4410), 10 ** (-20 / 20) * np.exp(-tn / 0.12)
                     * np.random.default_rng(3).standard_normal(len(tn)) / 3])
snq = q23(sn)
L, _ = render(snq, SUST=127)
ga = np.asarray(L[4410 + 441:], float); gi = np.asarray(snq[4410 + 441:len(L)], float)
ok_ = np.abs(gi) > (1 << 23) * 10 ** (-70 / 20)
gdb = 20 * np.log10(np.abs(ga[ok_]) / np.abs(gi[ok_]))
idx = np.nonzero(ok_)[0]
adj = np.diff(idx) == 1
step = float(np.max(np.abs(np.diff(gdb))[adj])) if adj.any() else 0.0
check(f"SUST +63, decaying noise tail: largest gain step between samples {step:.2f} dB (under 0.5 dB: no clicks)", step < 0.5)

# ---- level independence, above the floor ---------------------------------------
# The same burst on a noise bed scaled with it (-40 dB re the burst), at three
# levels 15 dB apart: everything stays above the -96 dB detector floor and below
# full scale after +12 dB, so the gain trajectories must match. One mask for all
# three: samples where the clean burst is within 30 dB of its peak.
bed = rng.standard_normal(len(x)) * 10 ** (-40 / 20) / 3
clean = REF.burst(level_db=0.0)[:, 0]
on = int(0.1 * FS)
seg = slice(on, on + int(0.3 * FS))
common = np.abs(clean[seg]) > 10 ** (-30 / 20)
gains = []
for lv in (-18.0, -33.0, -48.0):
    s = (clean + bed) * 10 ** (lv / 20)
    sq = q23(s)
    L, _ = render(sq, ATCK=127, SUST=127)
    gains.append(gain_db(sq[seg], L[seg], common))
dev = max(float(np.max(np.abs(gains[0] - gains[i]))) for i in (1, 2))
check(f"level independence (noise bed, -18/-33/-48 dBFS): max gain difference {dev:.3f} dB", dev < 0.1)

# ---- steady tone ------------------------------------------------------------------
t = np.arange(int(1.0 * FS)) / FS
tq = q23(0.5 * np.sin(2 * np.pi * 1000 * t))
L, _ = render(tq, ATCK=127, SUST=127)
seg = slice(int(0.6 * FS), len(L))
g = gain_db(tq[seg], L[seg], np.abs(np.asarray(tq[seg], float)) > (1 << 23) * 0.1)
check(f"steady 1 kHz tone, ATCK/SUST max: gain {g.min():+.2f}..{g.max():+.2f} dB", g.max() - g.min() < 0.25)

# ---- every knob at both ends renders ---------------------------------------------
for k in KNOBS:
    for v in (0, 127):
        render(noise, **{k: v})
check("every knob at 0 and 127 renders", True)

if FAILS:
    sys.exit(f"verify_transient: {len(FAILS)} gate(s) failed")
print("verify_transient: OK")
