# `testgen` -- TESTGEN

A measurement source: TESTGEN replaces its track's audio with a known test signal.

On the unit it is an FX2 effect. Put it on a track, play a trig (or use a THRU machine) and that track's output, analogue or a channel of Octabam's USB audio out, carries the signal. Uses: measuring the Octatrack's own path (level, frequency response, distortion, channel mapping), measuring a USB audio stream on a host, and proving other modules' claims by putting a known signal through them. [`DESIGN.md`](DESIGN.md) has the plan for all five signals; [`testgen_ref.py`](testgen_ref.py) is the float reference and the analysis the gate uses.

Every signal is defined exactly: `testgen_ref.py` reproduces each one as the module computes it, so a capture can be compared against the reference sample by sample, and a sweep can be deconvolved with its own inverse.

## Signals (MODE)

| MODE | signal | at LEVL 127 |
|---|---|---|
| SINE | a sine at FREQ | peak 0 dBFS, RMS -3.01 dBFS |
| SWEP | an exponential sweep, 20 Hz to 20 kHz over LEN, then 1 s of silence, repeating | peak 0 dBFS |
| PINK | pink noise: Kellet's three-pole filter on WHITE | RMS -14.4 dBFS |
| WHIT | white noise: a 24-bit generator (it repeats every 2^24 samples, 6 min 20 s) | peak 0 dBFS, RMS -4.77 dBFS |
| IMPL | a single full-scale sample every LEN/4 seconds | peak 0 dBFS |

A change of MODE, FREQ or LEN restarts the signal from its first sample: a sine from phase 0, a sweep from 20 Hz, the noise from its seed, the impulses with one at once.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | LEVL | 0-127 | output level: 127 = 0 dBFS, 0.5 dB a step (115 = -6 dBFS, the default; 0 = -63.5 dBFS) |
| 1 | 1 | FREQ | 0-127 | SINE frequency, ISO third-octave centres: 0 = 20 Hz, 7 = 100 Hz, 17 = 1 kHz (the default), 30 = 20 kHz; above 30 holds at 20 kHz |
| 1 | 2 | LEN | 0-127 | SWEEP length in whole seconds, LEN/8 + 1 (0 = 1 s, 32 = 5 s, the default, 120 = 16 s); the IMPULSE period is a quarter of it (0.25 s to 4 s) |
| 2 | 6 | MODE | select | SINE, SWEP, PINK, WHIT, IMPL |
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

## Measured

All by `tools/verify/verify_testgen.py` through `dsp_host` on the audition's scratch image, 3 Oct 2026, unless stated.

- ✅ The output does not depend on the input: full-scale noise in and silence in give identical output.
- ✅ 80 cycles a sample at most, in SWEEP (SINE 46, PINK 50, WHITE 17, IMPULSE 19; `make cycles REMIX=testgen`): four instances on one core price at 320 of 4,535.
- ✅ Every FREQ index matches the sine the phase accumulator defines, sin(2 pi n inc / 2^24), within 3 LSB at 0 dBFS, from sample 0.
- ✅ Every frequency is within 0.0013 Hz of its ISO nominal value (1 kHz measures 1000.0007 Hz; the accumulator's resolution is 0.0026 Hz).
- ✅ THD at 0 dBFS: -149.5 dB at 1 kHz, -140.5 dB at 100 Hz (nine harmonics, Blackman window, 65,536 samples).
- ✅ Every LEVL step is 0.5 dB within 0.0007 dB; LEVL 127 peaks within 1 LSB of full scale (RMS -3.010 dBFS).
- ✅ CHAN: L+R gives equal channels, L only and R only silence the other side, and L with inverted R gives R = -L within 1 LSB.
- ✅ SWEEP follows the reference's exact phase law (`sweep_phases`: a 48-bit increment growing by a constant ratio each sample) within 4 LSB, over two whole periods at 1 s and one at 16 s, into the next period's start. Deconvolved through an identity path with the ideal inverse filter it is flat within 0.12 dB from 40 Hz to 16 kHz.
- ✅ WHITE is the reference's 24-bit generator within 1 LSB; its octave bands are flat within 0.16 dB (slope -0.016 dB/octave over 2^20 samples).
- ✅ PINK slopes at -3.009 dB/octave, no octave band more than 0.32 dB off the fit; it matches the float filter on the same noise within -107.9 dB, and its RMS is -14.44 dBFS.
- ✅ IMPULSE puts a full-scale sample at exactly the reference's positions (every 0.25 s at LEN 0, every 1 s at LEN 24) and zero everywhere else.
- ✅ An invalid saved MODE byte plays SINE; every knob at both ends renders.

## Using it

- **A level or a channel check**: SINE at 1 kHz (FREQ 17), LEVL 127 gives a 0 dBFS peak; step LEVL to find where a path clips, 0.5 dB at a time. CHAN L-R shows whether a path keeps polarity.
- **A frequency response**: record a whole SWEEP period from where you want to measure, then deconvolve it with `testgen_ref.deconvolve(capture, f1=20.0007, T=<LEN/8 + 1>)`: the peak is the path's impulse response, and the harmonic distortion lands before it in time, apart from the linear part. `testgen_ref.sweep_dsp` gives the exact sweep for sample-accurate comparison.
- **A noise floor or a quick response**: PINK into a spectrum analyser, with third-octave bands, reads flat for a flat path.
- **Latency and dropouts**: IMPULSE, then count the samples between the impulses in a capture; a missing or shifted impulse is a dropout.

## Open

- Not yet run on hardware. Under the ColdFire port it builds and passes `make check REMIX=testgen`.
- What the Octatrack's own path does to the signal after FX2 (track level, the mixer, the converters) is what TESTGEN is for; it is not measured yet.

## Gates

- `tools/verify/verify_testgen.py` (the manifest's `Gate`). It refuses to run if the id resolves to SEND's entry points.
- `make check REMIX=testgen`.
