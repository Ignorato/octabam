# `waveload` — WAVE LOAD

A probe: K instances of a fixed-point port of CHOMPI WAVE's voice engine
(4 voices each) rendered inside the ColdFire's frame interrupt, output
discarded, so [CF METER](../cfmeter/README.md) reads what a 4-voice
wavetable track costs on the unit and how many fit.

The engine is a port of the voice in
[CHOMPI-Club/CHOMPI](https://github.com/CHOMPI-Club/CHOMPI)'s WAVE firmware
(`firmware/chompi-wave/code/src` at `a73d732`: `subtractiveEngine.h`,
`WavetableManager.h`, `DJFilter.h`, `BasicMMF.h`), MIT, Copyright (c) 2026
CHOMPI Club; the full notice is in [LICENSE-CHOMPI](LICENSE-CHOMPI). The
CHOMPI name is CHOMPI Club's trademark and is not this module's. WAVE
LOAD is a measurement, not a playable machine.

## Knobs

CF METER's BURN (T8 FX2 page 1 slot 0) is K, 0–12, when WAVE LOAD is in
the remix (CF METER's `remix.inc` sets `WAVE_LOAD`); above 12 it renders 12.

## Measured

- ✅ The engine (`engine.c`) against CHOMPI WAVE's own float classes,
  extracted verbatim and driven as `myEngine::Process` drives them at
  44.1 kHz with DaisySP's ADSR and oscillator (`harness/run.sh`, 2 Oct
  2026): a 4.5 s scenario (eight notes, a cutoff sweep 0.2 → 1 → 0,
  resonance .63 → .95 at 2 s, filter LFO depth .3 from 1 s, pitch LFO
  depth .5 from 1.5 s, 23 frame steps three of which retarget, release at
  3.5 s). Magnitude spectra per 0.25 s window agree to −53…−88 dB until
  the pitch LFO starts. From there they part to −14…−22 dB: DaisySP's float
  LFO phase runs 0.0117 % slow (4.947624 Hz against a nominal 4.948201 Hz
  over 60 s), and with both LFOs replaced by that float arithmetic in a
  host-only build the eight-note render agrees to −38…−88 dB and one voice
  (C6) to −50…−97 dB. The sample-domain residue that grows over the run is
  the oscillator's float phase accumulator against the port's exact 32-bit
  one. Falsified by: a window where the two differ with the LFOs matched.
- ✅ The ColdFire build (m68k-elf-gcc 16.2, `-mcpu=54455 -O2`, `mac.l` /
  `movclr.l` with MACSR 0x20) under the patched Unicorn
  (`.venv/lib/unicorn-emac`) is bit-identical to the host build: 198,448
  of 198,448 samples, at 4 and at 8 voices.
- ✅ Instructions executed in `eng_render`, counted per basic block under
  Unicorn over the scenario:

  | voices | mean / sample | worst 16-sample block / sample |
  |---|---|---|
  | 4 | 560.2 | 646.2 |
  | 8 | 957.0 | 1,131.2 |

  The worst blocks are the frame crossfade (two table reads per voice);
  WAVE LOAD keeps the crossfade running, so it renders the worst path.
  Instructions, not cycles: neither the cache nor the EMAC's timing is
  modelled.
- ✅ For comparison, SYNTH MACHINE's engine at VOIC 4 measured 3,304
  instructions a frame mean, 3,956 max, under the port
  (`modules/synth/upstream/synth/README.md`); a 4-voice wave engine is
  8,963 mean, 10,339 worst.
- ✅ Under the port (`waveload-port`, `OCTABAM89_setgate` with T8 FX2 =
  CF METER, BURN = K, 12,000 frames, `verify_set.py`, decoded with
  `cfmeter.py --dump`, 2 Oct 2026):

  | K | isr mean | every verify_set gate |
  |---|---|---|
  | 0 | 154.4 µs | pass |
  | 1 | 210.5 µs | pass |
  | 2 | 266.2 µs | pass |
  | 4 | — | T1's chain silent, the readout's sync lost |

  +56.1 and +55.9 µs per engine; at K = 4 the interrupt (154.4 + 4 × 56)
  passes the 362.8 µs period. The port prices every instruction at one
  step of its own clock, so these are the port's µs, not the unit's: one
  4-voice engine is 36 % of what stock's frame interrupt executes in this
  project, and that ratio is what carries to the unit only if both run
  at the same cycles per instruction.
- ✅ CF METER's image and build report for remix `cfmeter` are
  byte-identical with and without the `WAVE_LOAD` change (built both ways,
  2 Oct 2026).

## On the unit

Not flashed. The procedure is in
[remixes/test/waveload](../../remixes/test/waveload/README.md).

## Open

- The µs per 4-voice engine and the K at which the unit stops playing
  clean.

## Gates

- `modules/waveload/harness/run.sh 4` (and `8`): the oracle comparison,
  the ColdFire build's bit identity, the instruction count. Needs
  `clang`, `m68k-elf-gcc` and the emulator `.venv`; clones CHOMPI into
  `out/chompi` at the pinned commit.
- `python3 modules/waveload/generate.py --check`: `load.s` matches
  `load.c` + `engine.c`.
- `OT_PROJECT=<dir> make check REMIX=waveload-port`.

## Design

- `engine.c`: every voice shares the cutoff, the LFOs, the resonance and
  the frame crossfade in CHOMPI (`setMasterCutoff`, `setCycle`,
  `setMasterResonance` set all voices alike), so the slews, the feedback
  `res + res / (1 − f)` (one Newton step a sample from the last
  reciprocal) and both LFOs run once a sample. DjFilter's `hp_ > .8`
  branch is absent: `hp_` is clamped to at most .9³ = .729.
- `load.c`: twelve engine states and a scratch output in `.data` (the
  platform runtime is the linked image's bytes); the tables are 1 MB above
  them in the arena reserve, never in the image. With the 1,622,016 B of
  tables in `.data` the loader's hash of the runtime held the PC inside
  64 bytes for over 2 M instructions, which the port's stall check
  (`machine.cpp`, 4 bursts of 500,000) stops as a spin.
- `wrap.s`: `cl_load`, called from CF METER's `m_isr` before the stock
  handler saves anything, saves MACSR, ACC0 and ACCext01 the way the
  handler does (MACSR to 0 before the accumulator moves), sets MACSR
  0x20, renders, restores.
