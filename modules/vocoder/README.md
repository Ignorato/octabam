# `vocoder` -- VOCODER

A ten-band channel vocoder after the Roland VP-330: the track's audio (a voice) shapes a carrier.

On the unit it is an FX2 effect. Put it on a track playing a voice, sample or live through a THRU machine: with MODE INT the carrier is built in, two sawtooths an octave apart at NOTE, so turning NOTE (or parameter-locking it on the steps) plays the vocoded voice as a melody. With MODE EXT the carrier is the track's right channel: a THRU track with the voice on input A and a synth on input B. [`DESIGN.md`](DESIGN.md) has the law and the reasons; [`vocoder_ref.py`](vocoder_ref.py) is the float reference the DSP is proved against.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | NOTE | C1..C6 | the built-in carrier's pitch, shown as a note; parameter-lock it to play a melody; default C3 |
| 1 | 1 | CONS | 0-127 | consonants: the voice above 4 kHz passed through, as the VP-330's high-consonant circuit does; default 48 |
| 1 | 2 | DRY | 0-127 | the dry voice mixed in; default 0 |
| 1 | 3 | LEVL | 0-127 | output level, 127 = unity; default 100 |
| 2 | 6 | MODE | INT, EXT | the carrier: INT the built-in sawtooths at NOTE; EXT the right channel |

The modulator is the left and right channels averaged (INT), or the left channel (EXT). The output is mono, on both channels.

## Measured

All by `tools/verify/verify_vocoder.py` through `dsp_host` on the audition's scratch image, 4 Oct 2026, unless stated. The test modulator is synthetic: a 120 Hz glottal pulse train through three formants, the vowel changing every 200 ms, with noise bursts for consonants.

- ✅ The output matches the float reference within -62.4 dB (INT at C3) and -64.2 dB (EXT with a chord carrier), level within 0.001 dB. The difference is the band sum's 24-bit rounding (it was -85.7 dB with a 48-bit sum, which cost two moves a band); it exists only while a band is active.
- ✅ Silence in gives silence out, bit-exact, with CONS and DRY up.
- ✅ 0.3 s into a pause the output is -136.3 dBFS: the envelopes decay in 48 bits (in 24 they stuck at about -90 dBFS and let the carrier through between words).
- ✅ A sine at a band's centre keeps that band at least 18.6 dB above its neighbours.
- ✅ NOTE: C1, C3 and C6 within 0.05 % (measured 32.703, 130.813 and 1046.503 Hz); a saved NOTE past C6 plays C6.
- ✅ Every knob at both ends renders.
- ✅ 760 cycles a sample (`make cycles REMIX=vocoder`); `make accept REMIX=vocoder` passes every stage: four instances on one core price at 3,040 against the 3,120 a core has after its own work, no layout over the wall. The first version cost 1,085: three on tracks 1-4 (one core) stalled a MKII (audio and sequencer stopped until a reboot); the parallel-move rewrite, a peak-detector envelope and a 24-bit band sum brought it down.
- Listened to (4 Oct 2026): a LibriVox reading (public domain) through this DSP code in `dsp_host`, at C3, C2, without consonants, a melody parameter-locked per 1/8 and an external chord carrier; judged intelligible and "really good" by the tester. The design was chosen by ear and measurement: the VP-330's steep bands against a first law with shallow ones (DESIGN.md).

## Open

- Not yet run under the ColdFire port in a project, nor on hardware.
- The VP-330's ensemble (a bucket-brigade chorus on its output) is not modelled; a chorus on the Octatrack's FX would come after FX2's output only on another track.
- Four instances on a core leave 80 cycles of the 3,120; more than four on a core is refused by the pricing gate.

## Gates

- `tools/verify/verify_vocoder.py` (the manifest's `Gate`). It refuses to run if the id resolves to SEND's entry points.
- `make check REMIX=vocoder`; with `OT_PROJECT=<a project>` it adds `verify_set` under the ColdFire port.

## Design

[`DESIGN.md`](DESIGN.md): the VP-330 as documented, why the bands are steep, what the 24-bit version changed and why, the r7 slots and the tables.
