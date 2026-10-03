#!/usr/bin/env python3
"""Write WAVE's carrier: a C5 sine (523.25 Hz, 2,093 whole cycles in 4 s, so
it loops without a seam), 24-bit mono 44.1 kHz at -1 dBFS.

    python3 modules/wave/carrier.py out/WAVCAR.wav
"""
import math
import sys
import wave

SR, SECONDS, CYCLES = 44100, 4, 2093          # 2093 / 4 = 523.25 Hz = C5
AMP = 10 ** (-1 / 20)


def main(path):
    n = SR * SECONDS
    frames = bytearray()
    for i in range(n):
        v = round(AMP * 8388607 * math.sin(2 * math.pi * CYCLES * i / n))
        frames += (v & 0xFFFFFF).to_bytes(3, "little")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(bytes(frames))
    print(f"wrote {path}: {n} samples, {CYCLES / SECONDS:.2f} Hz")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "WAVCAR.wav")
