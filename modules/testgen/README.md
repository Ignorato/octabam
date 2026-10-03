# `testgen` -- TESTGEN

A measurement source: TESTGEN replaces its track's audio with a known test signal.

On the unit it is an FX2 effect. Put it on a track, play a trig (or use a THRU machine) and that track's output, analogue or a channel of Octabam's USB audio out, carries the signal. Uses: measuring the Octatrack's own path (level, frequency response, distortion, channel mapping), measuring a USB audio stream on a host, and proving other modules' claims by putting a known signal through them. [`DESIGN.md`](DESIGN.md) has the plan for all five signals; [`testgen_ref.py`](testgen_ref.py) is the float reference and the analysis the gate uses.

Version 0.1 has the SINE signal. SWEEP, PINK, WHITE and IMPULSE are listed on MODE but are silent until they are written.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | LEVL | 0-127 | output level: 127 = 0 dBFS, 0.5 dB a step (115 = -6 dBFS, the default; 0 = -63.5 dBFS) |
| 1 | 1 | FREQ | 0-127 | SINE frequency, ISO third-octave centres: 0 = 20 Hz, 7 = 100 Hz, 17 = 1 kHz (the default), 30 = 20 kHz; above 30 holds at 20 kHz |
| 1 | 2 | LEN | 0-127 | SWEEP length and IMPULSE period (not used in 0.1) |
| 2 | 6 | MODE | select | SINE (0.1); SWEP, PINK, WHIT, IMPL to follow |
| 2 | 8 | CHAN | select | L+R, L only, R only, L and inverted R (a polarity check) |

The FREQ table:

| FREQ | Hz | FREQ | Hz | FREQ | Hz | FREQ | Hz |
|---|---|---|---|---|---|---|---|
| 0 | 20 | 8 | 125 | 16 | 800 | 24 | 5000 |
| 1 | 25 | 9 | 160 | 17 | 1000 | 25 | 6300 |
| 2 | 31.5 | 10 | 200 | 18 | 1250 | 26 | 8000 |
| 3 | 40 | 11 | 250 | 19 | 1600 | 27 | 10000 |
| 4 | 50 | 12 | 315 | 20 | 2000 | 28 | 12500 |
| 5 | 63 | 13 | 400 | 21 | 2500 | 29 | 16000 |
| 6 | 80 | 14 | 500 | 22 | 3150 | 30 | 20000 |
| 7 | 100 | 15 | 630 | 23 | 4000 | | |

A change of FREQ or MODE restarts the sine at phase 0.

## Measured

All by `tools/verify/verify_testgen.py` through `dsp_host` on the audition's scratch image, 3 Oct 2026.

- ✅ The output does not depend on the input: full-scale noise in and silence in give identical output.
- ✅ Every FREQ index matches the sine the phase accumulator defines, sin(2 pi n inc / 2^24), within 3 LSB at 0 dBFS, from sample 0.
- ✅ Every frequency is within 0.0013 Hz of its ISO nominal value (1 kHz measures 1000.0007 Hz; the accumulator's resolution is 0.0026 Hz).
- ✅ THD at 0 dBFS: -149.5 dB at 1 kHz, -140.5 dB at 100 Hz (nine harmonics, Blackman window, 65,536 samples).
- ✅ Every LEVL step is 0.5 dB within 0.0007 dB; LEVL 127 peaks within 1 LSB of full scale (RMS -3.010 dBFS).
- ✅ CHAN: L+R gives equal channels, L only and R only silence the other side, and L with inverted R gives R = -L within 1 LSB.
- ✅ The unwritten modes are silent; every knob at both ends renders.

## Open

- Not yet run under the ColdFire port or on hardware.
- What the Octatrack's own path does to the signal after FX2 (track level, the mixer, the converters) is what TESTGEN is for; it is not measured yet.

## Gates

- `tools/verify/verify_testgen.py` (the manifest's `Gate`). It refuses to run if the id resolves to SEND's entry points.
- `make check REMIX=testgen`.
