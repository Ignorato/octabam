# `testgen` -- TESTGEN

A measurement source: TESTGEN replaces its track's audio with a known test signal.

On the unit it is an FX2 effect. Put it on a track, play a trig (or use a THRU machine) and that track's output, analogue or a channel of Octabam's USB audio out, carries the signal. Uses: measuring the Octatrack's own path (level, frequency response, distortion, channel mapping), measuring a USB audio stream on a host, and proving other modules' claims by putting a known signal through them. [`DESIGN.md`](DESIGN.md) has the plan for all five signals; [`testgen_ref.py`](testgen_ref.py) is the float reference and the analysis the gate uses.

Every signal is defined exactly: `testgen_ref.py` reproduces each one as the module computes it, so a capture can be compared against the reference sample by sample, and a sweep can be deconvolved with its own inverse.

## Signals (MODE)

| MODE | signal | at LEVL 127 |
|---|---|---|
| SINE | a sine at FREQ | peak 0 dBFS, RMS -3.01 dBFS |
| SWEP | an exponential sweep, 20 Hz to 20 kHz over LEN, then 1 s of silence, repeating | peak 0 dBFS |
| PINK | pink noise: Kellet's three-pole filter on WHITE, one filter per channel | RMS -14.4 dBFS |
| WHIT | white noise: a 46-bit linear congruential generator (drand48's multiplier), its top 23 bits; one generator per channel, so with CHAN L+R the two sides are independent | peak 0 dBFS, RMS -4.77 dBFS |
| IMPL | a single full-scale sample every LEN/4 seconds | peak 0 dBFS |

A change of MODE, FREQ or LEN restarts the signal from its first sample: a sine from phase 0, a sweep from 20 Hz, the noise from its seed, the impulses with one at once.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | LEVL | 0-127 | output level: 0 = silent (the default), 1 = -63 dBFS, 127 = 0 dBFS, 0.5 dB a step (115 = -6 dBFS) |
| 1 | 1 | FREQ | select, shown in Hz | SINE frequency: the 31 ISO third-octave centres, 20 Hz to 20 kHz, and A440, across the knob's whole turn; 1k is the default |
| 1 | 2 | LEN | 0-127 | SWEEP length in whole seconds, LEN/8 + 1 (0 = 1 s, 32 = 5 s, the default, 120 = 16 s); the IMPULSE period is a quarter of it (0.25 s to 4 s) |
| 1 | 3 | FINE | -64..+63 | SINE fine tune: -200 to +197 cents in 3.125-cent steps, so FREQ and FINE together reach any frequency from 17.8 Hz to 20 kHz; 0 is the FREQ step exactly. Turning it does not restart the tone |
| 2 | 6 | MODE | select | SINE, SWEP, PINK, WHIT, IMPL |
| 2 | 8 | CHAN | select | L+R, L only, R only, L and inverted R (a polarity check), MONO. For the noises, L+R gives independent noise on each side, and MONO the same noise on both |

LEVL starts at 0, so choosing TESTGEN makes no sound until you turn it up: a full-level tone on insert is hard on ears and speakers (reported on the unit with the first image, which defaulted to -6 dBFS). FREQ was a plain 0-127 knob in that image, with the 31 frequencies packed into its first quarter; it is now a select that shows the frequency.

The FREQ steps:

| FREQ | Hz | FREQ | Hz | FREQ | Hz | FREQ | Hz |
|---|---|---|---|---|---|---|---|
| 0 | 20 | 8 | 125 | 16 | 630 | 24 | 4000 |
| 1 | 25 | 9 | 160 | 17 | 800 | 25 | 5000 |
| 2 | 31.5 | 10 | 200 | 18 | 1000 | 26 | 6300 |
| 3 | 40 | 11 | 250 | 19 | 1250 | 27 | 8000 |
| 4 | 50 | 12 | 315 | 20 | 1600 | 28 | 10000 |
| 5 | 63 | 13 | 400 | 21 | 2000 | 29 | 12500 |
| 6 | 80 | 14 | 440 (A) | 22 | 2500 | 30 | 16000 |
| 7 | 100 | 15 | 500 | 23 | 3150 | 31 | 20000 |

## Measured

All by `tools/verify/verify_testgen.py` through `dsp_host` on the audition's scratch image, 3 Oct 2026, unless stated.

- ✅ The output does not depend on the input: full-scale noise in and silence in give identical output.
- ✅ 150 cycles a sample at most, in PINK and WHITE (two generators and two filters; SWEEP 85, SINE 51, IMPULSE 18; `make cycles REMIX=testgen`): four instances on one core price at 600 of 4,535.
- ✅ Every FREQ index matches the sine the phase accumulator defines, sin(2 pi n inc / 2^24), within 3 LSB at 0 dBFS, from sample 0.
- ✅ Every FREQ step is within 0.0013 Hz of its nominal value (1 kHz measures 1000.0007 Hz, A440 440.0007 Hz; the accumulator's resolution is 0.0026 Hz).
- ✅ FINE moves the frequency to FREQ x 2^(FINE/384) within half an accumulator step plus 1 ppm, from -64 to +63 (the 2^x polynomial is within 0.19 ppm); FINE 0 is the FREQ step bit for bit; THD at 1 kHz with FINE +63 is -149.4 dB; 20 kHz with FINE up holds at 20 kHz.
- ✅ THD at 0 dBFS: -149.5 dB at 1 kHz, -140.5 dB at 100 Hz (nine harmonics, Blackman window, 65,536 samples).
- ✅ Every LEVL step from 1 to 127 is 0.5 dB within 0.0006 dB; LEVL 127 peaks within 1 LSB of full scale (RMS -3.010 dBFS); LEVL 0, the default, is silent in every MODE.
- ✅ CHAN: L+R gives equal channels, L only and R only silence the other side, and L with inverted R gives R = -L within 1 LSB.
- ✅ SWEEP follows the reference's exact phase law (`sweep_phases`: a 48-bit increment growing by a constant ratio each sample) within 4 LSB, over two whole periods at 1 s and one at 16 s, into the next period's start. Deconvolved through an identity path with the ideal inverse filter it is flat within 0.12 dB from 40 Hz to 16 kHz.
- ✅ WHITE: each channel is the reference's 46-bit generator within 1 LSB (it repeats every 2^46 samples, about 50 years). Over 2^20 samples: flat (slope -0.002 dB/octave); autocorrelation at lags 1 to 64 at most 0.0027; with CHAN L+R, the L/R cross-correlation at lags -64 to 64 at most 0.0026 (1/sqrt(n) is 0.0010) and the (L, R) pairs fill a 64 x 64 grid evenly (chi-square 4,150 on 4,095 degrees of freedom); the output's low bits have no short cycles. MONO gives R = L, L-R gives R = -L.
- ✅ PINK, each channel: -3.000 and -3.001 dB/octave, no octave band more than 0.44 dB off the fit; within -107.9 dB of the float filter on the same noise; RMS -14.39 and -14.52 dBFS. With CHAN L+R the channels are independent (differenced cross-correlation at most 0.0022).
- History: 0.1's WHITE was a 24-bit generator whose low bits repeated on short cycles (the low 16 bits every 1.5 s, -48 dB under the noise) and whose L and R were the same; replaced at the tester's request.
- ✅ IMPULSE puts a full-scale sample at exactly the reference's positions (every 0.25 s at LEN 0, every 1 s at LEN 24) and zero everywhere else.
- ✅ An invalid saved MODE byte plays SINE; every knob at both ends renders.
- ✅ Under the ColdFire port in a real project (`verify_set`, `OT_PROJECT`, 3 Oct 2026): a project made on a MKII on stock 1.40C (T1 THRU, T2 STATIC with trigs), TESTGEN put on T2's FX2 in every part of every bank with `ot_project.py set-fx` (LEVL 115, FREQ 17, LEN 32). LOAD PROJECT completed and 900 frames ran; the live FX2 id on T2 read 0x17; T2's chain output was -16.5 dB against -41.7 dB in (the sine replaces the track's quiet audio); the load rewrote no project file; every shared-window DSP write lay in a permitted range. This proves the module loads and its signal reaches the chain on the emulated firmware, not the signal's accuracy there.

## On the unit

- ✅ Image OCTABAM4 (`make image REMIX=testgen BUILD=4`) on Ignorato's MKII, 3 Oct 2026: boots, and TESTGEN is listed on FX2. Two findings from the tester, both fixed in the next image: LEVL defaulted to 115 (-6 dBFS), so a loud tone started on insert; and FREQ, then a plain 0-127 knob, reached 5 kHz by about 24.
- ✅ Image OCTABAM5 (`make image REMIX=testgen BUILD=5`, with FINE and A440), same unit and day: boots, OS VERSION reads OCTABAM5; on insert LEVL reads 0 (silent), and FREQ shows its steps in Hz; FINE tunes smoothly; all five MODEs and the four CHAN settings work as expected (tester, by ear).

## Using it

- **A level or a channel check**: SINE at 1 kHz (FREQ 17), LEVL 127 gives a 0 dBFS peak; step LEVL to find where a path clips, 0.5 dB at a time. CHAN L-R shows whether a path keeps polarity.
- **A frequency response**: record a whole SWEEP period from where you want to measure, then deconvolve it with `testgen_ref.deconvolve(capture, f1=20.0007, T=<LEN/8 + 1>)`: the peak is the path's impulse response, and the harmonic distortion lands before it in time, apart from the linear part. `testgen_ref.sweep_dsp` gives the exact sweep for sample-accurate comparison.
- **A noise floor or a quick response**: PINK into a spectrum analyser, with third-octave bands, reads flat for a flat path.
- **Latency and dropouts**: IMPULSE, then count the samples between the impulses in a capture; a missing or shifted impulse is a dropout.

## Open

- Not yet run on hardware.
- What the Octatrack's own path does to the signal after FX2 (track level, the mixer, the converters) is what TESTGEN is for; it is not measured yet.

## Gates

- `tools/verify/verify_testgen.py` (the manifest's `Gate`). It refuses to run if the id resolves to SEND's entry points.
- `make check REMIX=testgen`; with `OT_PROJECT=<a project>` it adds `verify_set` under the ColdFire port.
