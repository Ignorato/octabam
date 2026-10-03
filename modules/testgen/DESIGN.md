# TESTGEN: design note (draft)

3 Oct 2026. Status: all five signals written and proved in `dsp_host` (README.md, Measured); not yet on hardware.

## What it is

An Octabam FX2 insert that **replaces** its track's audio with an exact, reproducible test signal. Put it on any track, play a trig (or use a THRU machine), and that track's output (analogue, or a channel of Octabam's USB audio out) carries a known signal. Uses:

- measuring the Octatrack's own path: level, frequency response, noise, distortion, channel mapping, latency;
- measuring Octabam's USB audio on a Windows host (B-007): dropouts, latency, the stream-start reordering defect;
- proving other modules' claims: a sweep through any FX chain gives its impulse and frequency response by deconvolution.

## Signals (MODE, page 2 slot 6, even slot as Octabam requires for a select)

| MODE | Signal | Exactness |
|---|---|---|
| SINE | A sine at FREQ | Phase accumulator plus a polynomial sine; THD target below -100 dB |
| SWEEP | An exponential (Farina) sine sweep, 20 Hz to 20 kHz over LEN seconds, then 1 s of silence, repeating | The phase law is exact (a 48-bit increment grown by a constant ratio each sample, modelled bit for bit in the reference); deconvolution separates the linear response from the harmonics. The silence lets a path's tail ring out and marks where each period starts |
| PINK | Pink noise (WHITE through Kellet's 3-pole filter) | Seeded; -3 dB/octave within 0.3 dB/octave, every octave band within 1 dB of the fit, 40 Hz to 16 kHz |
| WHITE | White noise from a 46-bit linear congruential generator, one per channel | Seeded and exact: the reference reproduces each channel within 1 LSB; L and R independent |
| IMPULSE | A one-sample impulse every LEN/4 seconds | Exact |

Every MODE restarts from the same state when the module initialises (on load or a mode change), so a capture can be compared sample-accurately against the reference.

## Knobs

| Page | Slot | Name | Range | What |
|---|---|---|---|---|
| 1 | 0 | LEVL | 0..127 | output level: 0 dBFS at 127, 0.5 dB steps (-63.5 dBFS at 0); the steps are exact powers of the 0.5 dB ratio |
| 1 | 1 | FREQ | 0..127 | SINE frequency: ISO third-octave centres from 20 Hz upwards (exact 1 kHz included) |
| 1 | 2 | LEN | 0..127 | SWEEP duration, LEN/8 + 1 whole seconds (1 to 16 s); the IMPULSE period is a quarter of it |
| 2 | 6 | MODE | select | SINE, SWEEP, PINK, WHITE, IMPULSE |
| 2 | 8 | CHAN | select | L+R, L only, R only, L and inverted R (polarity check); an even slot, as Octabam requires for a select |

## DSP56300 constraints (Octabam's rules)

- No per-sample division, log or exp: the sweep's increment is multiplied by a constant ratio each sample (exponential law), in 48-bit precision; the sine is a short odd polynomial on a quarter wave (five rounded MACs); levels come from a table per block.
- No buffers, no lookahead: an insert on any track, cheap: 80 cycles a sample at most (SWEEP).
- Size: it runs in PLATE REV's 594 words. The first full build was one word over; the impulse period is now computed from the sweep length instead of read from a table (581 words: 390 of code, 191 of table); with FINE and A440, 584 (392 and 192: the sine core became a shared subroutine to make room); with the 46-bit stereo noise, 588 (396 and 192: short-form compares, one restart routine for init and proc, one noise routine for both channels).
- Output replaces the input: a THRU track becomes a signal source.

## The reference (testgen_ref.py)

Float generators plus the analysis the gate needs: THD of the sine, deconvolution of the sweep (Farina inverse filter), the pink noise's octave-band slope. The self-check proves the analysis on ideal signals; the DSP module is later proved against the same analysis, sample-accurately where the law is exact.

## What would falsify it

- A sine THD above the target, or a frequency that is not the stated value to within the phase accumulator's resolution.
- A sweep whose deconvolved impulse response shows anything but a single clean peak through an identity path.
- Pink noise whose octave bands deviate from -3 dB/octave by more than the stated tolerance.
