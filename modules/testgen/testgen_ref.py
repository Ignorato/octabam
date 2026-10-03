#!/usr/bin/env python3
"""Float reference for TESTGEN (B-013): the signals and the analysis that proves them.

    python3 modules/testgen/testgen_ref.py      # self-check on ideal signals
"""
import math
import numpy as np

FS = 44100.0                       # the Octatrack's rate
ISO_THIRDS = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000,
              1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]


def level_lin(k):
    """LEVL 0..127 -> linear gain: 0 dBFS at 127, 0.5 dB steps."""
    return 10 ** (-(127 - k) * 0.5 / 20)


def freq_hz(k):
    """FREQ 0..127 -> ISO third-octave centre (held at 20 kHz past the end)."""
    return ISO_THIRDS[min(k, len(ISO_THIRDS) - 1)]


def sine(f, n, level=1.0):
    return level * np.sin(2 * math.pi * f * np.arange(n) / FS)


def sweep(f1=20.0, f2=20000.0, T=4.0, level=1.0):
    """Exponential (Farina) sweep: phase = 2 pi f1 L (e^(t/L) - 1), L = T / ln(f2/f1)."""
    n = int(round(T * FS))
    t = np.arange(n) / FS
    L = T / math.log(f2 / f1)
    return level * np.sin(2 * math.pi * f1 * L * (np.exp(t / L) - 1.0)), L


def inverse_filter(f1, f2, T):
    """Farina's inverse: the time-reversed sweep, amplitude-weighted by -6 dB/octave."""
    s, L = sweep(f1, f2, T)
    t = np.arange(len(s)) / FS
    return s[::-1] * np.exp(-t / L)


def white(n, seed=1):
    return np.random.default_rng(seed).uniform(-1.0, 1.0, n)


def pink(n, seed=1):
    """Paul Kellet's economy pink filter on white noise (3 poles)."""
    w = white(n, seed)
    b0 = b1 = b2 = 0.0
    out = np.empty(n)
    for i, x in enumerate(w):
        b0 = 0.99765 * b0 + x * 0.0990460
        b1 = 0.96300 * b1 + x * 0.2965164
        b2 = 0.57000 * b2 + x * 1.0526913
        out[i] = b0 + b1 + b2 + x * 0.1848
    return out * 0.11


def thd_db(x, f, harmonics=9):
    """THD of a steady sine x at f, by a Blackman-Harris windowed FFT."""
    n = len(x)
    w = np.blackman(n)
    X = np.abs(np.fft.rfft(x * w))
    bins = lambda hz: int(round(hz * n / FS))
    def power(k):
        k0 = max(k - 4, 0)
        return float(np.sum(X[k0:k + 5] ** 2))
    p1 = power(bins(f))
    ph = sum(power(bins(f * h)) for h in range(2, harmonics + 1) if f * h < FS / 2)
    return 10 * math.log10(max(ph, 1e-30) / p1)


def deconvolve(y, f1=20.0, f2=20000.0, T=4.0):
    """Impulse response of the path that turned the sweep into y (linear part at the peak)."""
    inv = inverse_filter(f1, f2, T)
    n = len(y) + len(inv) - 1
    N = 1 << (n - 1).bit_length()
    h = np.fft.irfft(np.fft.rfft(y, N) * np.fft.rfft(inv, N), N)[:n]
    return h / np.max(np.abs(h))


def octave_slope_db(x, lo=40.0, hi=16000.0):
    """Level per octave band; returns the fitted slope (dB/octave) and the worst deviation from it."""
    X = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / FS)
    centres, levels = [], []
    c = lo
    while c <= hi:
        m = (f >= c / math.sqrt(2)) & (f < c * math.sqrt(2))
        levels.append(10 * math.log10(np.sum(X[m]) / max(np.sum(m), 1)))
        centres.append(math.log2(c))
        c *= 2
    p = np.polyfit(centres, levels, 1)
    dev = max(abs(l - np.polyval(p, c_)) for c_, l in zip(centres, levels))
    return float(p[0]), float(dev)


if __name__ == "__main__":
    ok = True
    s = sine(1000.0, 1 << 16)
    t = thd_db(s, 1000.0)
    print(f"ideal 1 kHz sine: THD {t:.1f} dB (the analysis floor)"); ok &= t < -120
    s3 = s + 1e-3 * sine(3000.0, 1 << 16)
    t3 = thd_db(s3, 1000.0)
    print(f"1 kHz sine with a -60 dB 3rd harmonic: THD {t3:.1f} dB (expect -60)"); ok &= abs(t3 + 60) < 0.5
    sw, _ = sweep(T=2.0)
    h = deconvolve(np.concatenate([sw, np.zeros(int(FS))]), T=2.0)
    pk = int(np.argmax(np.abs(h)))
    seg = h[pk - 4096:pk + 4096] * np.hanning(8192)            # the linear impulse response
    Hm = np.abs(np.fft.rfft(seg, 1 << 15)); fr = np.fft.rfftfreq(1 << 15, 1 / FS)
    band = (fr >= 40) & (fr <= 16000)
    db = 20 * np.log10(Hm[band] / np.median(Hm[band]))
    flat = float(np.max(np.abs(db)))
    print(f"sweep through an identity path: deconvolved response flat within {flat:.2f} dB, 40 Hz-16 kHz"); ok &= flat < 0.5
    sl, dev = octave_slope_db(pink(1 << 20))
    print(f"pink noise: slope {sl:+.2f} dB/octave, worst band deviation {dev:.2f} dB"); ok &= abs(sl + 3.0) < 0.3 and dev < 1.0
    sl, dev = octave_slope_db(white(1 << 20))
    print(f"white noise: slope {sl:+.2f} dB/octave, worst band deviation {dev:.2f} dB"); ok &= abs(sl) < 0.3
    print(f"LEVL 127 = {20 * math.log10(level_lin(127)):.1f} dBFS, LEVL 0 = {20 * math.log10(level_lin(0)):.1f} dBFS; FREQ 17 = {freq_hz(17)} Hz")
    print("SELF-CHECK", "OK" if ok else "FAILED")
