# `wave` — WAVE with the scale and page-2 tools

[WAVE](../../../modules/wave/README.md) (a 4-voice wavetable synth on FX2)
with [SCALE QUANTIZER](../../../modules/quantizer/README.md) for the played
notes, [CC MAP](../../../modules/cc-map/README.md),
[SCENES P2](../../../modules/scenes-p2/README.md) and
[PLOCKS P2](../../../modules/plocks-p2/README.md) for WAVE's page 2, and
USB MIDI + USB AUDIO OUT TRACKS MAIN CUE to record it. DARK REV and SPRING
REV are off the chooser: WAVE runs in their words.

## Status

Not flashed. `python3 tools/verify/verify_wave.py wave` passes under
dsp_host.

## Procedure

1. `make image REMIX=wave BUILD=N`, flash, power-cycle.
2. `python3 modules/wave/carrier.py WAVCAR.wav`; copy it to the set's
   audio pool.
3. A new project. T1: FLEX, WAVCAR.wav, loop on; FX2 = **Wave Synth**.
   Volume low for the first PLAY.
4. Trigs and the CHROMATIC keys play it; PROJECT > CONTROL > SEQUENCER >
   SCALE sets the scale.
5. USB to the Mac: `tools/hw/rec 12 <name>.wav Octatrack` records T1 on
   USB channels 1/2.
