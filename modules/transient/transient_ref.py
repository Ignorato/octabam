#!/usr/bin/env python3
"""Float reference for TRANSIENT (B-005): the law in DESIGN.md, in float64.

The DSP56300 implementation is proved against this. Run it directly for a
self-check on synthetic tone bursts:

    python3 modules/transient/transient_ref.py
"""
import numpy as np

FS = 44100.0
FLOOR_BITS = -16.0          # -96 dBFS detector floor
RANGE_BITS = 2.0            # gain clamp, +-12 dB
KA = 1.0                    # bits of gain per bit of atk at ATCK = +1
KS = 1.0                    # bits of gain per bit of sus at SUST = +1
PEAK_MS = 10.0              # linear peak detector release (instant attack)
LAG_BITS = RANGE_BITS / KA  # S may lag F by at most this: where the gain clamps anyway
ONSET_BITS = 0.5            # v must exceed F by this (3 dB) to count as a new hit: ripple in a
                            # tail stays below it (v3: without it the tails clicked, 3 Oct 2026)


def coef(ms):
    """One-pole coefficient for a time constant in ms."""
    return 1.0 - np.exp(-1.0 / (FS * ms * 1e-3))


def time_ms(knob):
    """TIME knob 0..127 -> 5..50 ms, logarithmic."""
    return 5.0 * 10.0 ** (knob / 127.0)


def bipolar(knob):
    """-64..+63 drawn value (stored 0..127 around 64) -> -1..+1."""
    return (knob - 64) / 64.0


def process(x, atck=64, sust=64, time=40, out=64, mix=127, trace=False):
    """x: (n, 2) float array in [-1, 1]. Knobs as stored values (0..127)."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    a, s = bipolar(atck), bipolar(sust)
    cF = (coef(0.5), coef(50.0))
    cS = (coef(time_ms(time)), coef(50.0))
    cH = (coef(0.5), coef(500.0))
    trim = 2.0 ** (bipolar(out) * 2.0)
    m = 1.0 if mix >= 127 else mix / 128.0   # the DSP: value/128, 127 pinned to full

    d = np.maximum(np.abs(x[:, 0]), np.abs(x[:, 1]))
    # linear peak detector: instant attack, PEAK_MS release (keeps the log off the zero crossings)
    r = np.exp(-1.0 / (FS * PEAK_MS * 1e-3))
    pk = np.empty(n)
    p = 0.0
    for i in range(n):
        p = max(d[i], p * r)
        pk[i] = p
    lg = np.log2(np.maximum(pk, 2.0 ** FLOOR_BITS))
    F = S = H = FLOOR_BITS
    g = np.empty(n)
    tr = np.empty((n, 3)) if trace else None
    for i in range(n):
        v = lg[i]
        F += (cF[0] if v > F else cF[1]) * (v - F)
        S += (cS[0] if v > S else cS[1]) * (v - S)
        S = max(S, F - LAG_BITS)          # every onset starts from the same gap: level independence
        H += (cH[0] if v > H else cH[1]) * (v - H)
        if v > F + ONSET_BITS:            # a new hit starts its own tail: without this a
            H = min(H, v - ONSET_BITS)    # quieter hit inside a louder one's tail was boosted
        atk = max(F - S, 0.0)
        sus = max(H - max(F, v - ONSET_BITS), 0.0)   # no sustain gain at an onset (v2, 3 Oct 2026:
                                          # v1 put +12 dB on every onset of a drum loop at SUST +63)
        g[i] = min(max(a * KA * atk + s * KS * sus, -RANGE_BITS), RANGE_BITS)
        if trace:
            tr[i] = (F, S, H)
    G = 2.0 ** g
    y = x * G[:, None] * trim
    outp = x + m * (y - x)
    return (outp, g, tr) if trace else outp


def burst(freq=1000.0, rise_ms=1.0, decay_ms=150.0, dur_s=0.5, level_db=-6.0, gap_s=0.1):
    """A tone burst: linear rise, exponential decay, after a short silence."""
    t = np.arange(int(dur_s * FS)) / FS
    env = np.minimum(t / (rise_ms * 1e-3), 1.0) * np.exp(-np.maximum(t - rise_ms * 1e-3, 0) / (decay_ms * 1e-3))
    sig = 10 ** (level_db / 20) * env * np.sin(2 * np.pi * freq * t)
    sig = np.concatenate([np.zeros(int(gap_s * FS)), sig])
    return np.stack([sig, sig], axis=1)


def _db(v):
    return 20 * np.log10(max(v, 1e-12))


if __name__ == "__main__":
    x = burst()
    ok = True

    # 1. Neutral knobs: exact passthrough.
    y = process(x)
    ok &= np.array_equal(y, x)
    print(f"neutral passthrough exact: {np.array_equal(y, x)}")

    # 2. MIX 0: exact passthrough whatever the knobs.
    y = process(x, atck=127, sust=0, mix=0)
    ok &= np.array_equal(y, x)
    print(f"MIX 0 passthrough exact:   {np.array_equal(y, x)}")

    # 3. Shape of the gain for ATCK max and SUST min.
    on = int(0.1 * FS)
    for label, kw in [("ATCK +63", dict(atck=127)), ("ATCK -64", dict(atck=0)),
                      ("SUST +63", dict(sust=127)), ("SUST -64", dict(sust=0))]:
        _, g, _ = process(x, trace=True, **kw)
        win = lambda a_ms, b_ms: g[on + int(a_ms * FS / 1e3): on + int(b_ms * FS / 1e3)]
        print(f"{label}: gain dB  onset 0-10 ms peak {6.02 * np.max(np.abs(win(0, 10))) * np.sign(win(0, 10).sum() or 1):+6.2f}"
              f"  | 50-60 ms mean {6.02 * win(50, 60).mean():+6.2f}  | 200-300 ms mean {6.02 * win(200, 300).mean():+6.2f}")

    # 4. Level independence. The law is invariant to level above the detector floor (-96 dBFS).
    # (a) burst on a noise bed scaled with it (-40 dB re the burst): everything stays above the
    #     floor, so the gain trajectory must match to rounding at -6, -24 and -42 dBFS;
    # (b) from digital silence the first samples sit on the floor, so compare from 1 ms on.
    rng = np.random.default_rng(1)
    bed = rng.standard_normal(len(x)) * 10 ** (-40 / 20) * 10 ** (-6 / 20) / 3
    def at(lv, with_bed):
        b = burst(level_db=lv)
        if with_bed:
            b = b + (bed * 10 ** ((lv + 6) / 20))[:, None]
        return process(b, atck=127, sust=127, trace=True)[1]
    for label, with_bed, start, tol in (("noise bed, whole burst", True, 0, 0.01),
                                        ("from silence, after 1 ms", False, int(0.001 * FS), 0.25)):
        gs = [at(lv, with_bed)[on + start: on + int(0.3 * FS)] for lv in (-6.0, -24.0, -42.0)]
        dev = max(np.max(np.abs(gs[0] - gs[1])), np.max(np.abs(gs[0] - gs[2]))) * 6.02
        ok &= dev < tol
        print(f"level independence ({label}, tolerance {tol} dB): max gain difference {dev:.4f} dB")

    # 5. Steady tone: no pumping once settled (atk should be ~0).
    t = np.arange(int(1.0 * FS)) / FS
    tone = 0.5 * np.sin(2 * np.pi * 1000 * t)
    _, g, _ = process(np.stack([tone, tone], 1), atck=127, sust=127, trace=True)
    settled = g[int(0.6 * FS):] * 6.02
    print(f"steady 1 kHz tone, ATCK/SUST max, after 0.6 s: gain {settled.min():+.2f}..{settled.max():+.2f} dB")

    # 6. Both signs: a negated input gives a negated output.
    yp = process(x, atck=127, sust=0)
    yn = process(-x, atck=127, sust=0)
    sym = np.array_equal(yn, -yp)
    ok &= sym
    print(f"sign symmetry exact: {sym}")

    print("SELF-CHECK", "OK" if ok else "FAILED")
