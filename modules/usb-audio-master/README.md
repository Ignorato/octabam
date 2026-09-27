# USB AUDIO MASTER

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), two channels:
track 8's L/R, post-FX, pre-fader, on channels 1/2 at both USB speeds.
With MASTER TRACK on, track 8 is the mix through T8's effects, before T8's
LEVEL and MAIN volume. Needs USB MIDI.

[USB AUDIO EXTENDED](../usb-audio-extended/README.md)'s source,
`usbaudio.s` (markandrus/octemu, MIT), assembled with `USB_LAYOUT = 2`.
The variant is Sam Banks's (27 Sep 2026):

- **Producer.** Reads T8's two read-back words per frame (the same words
  as EXTENDED's channels 15/16, the same 24-bit format) and writes one
  8-byte slot per frame into a 1,024-frame ring. No other track, no
  MAIN/CUE, no stereo sum.
- **Both speeds send the same ring.** High speed: 11/12 frames, at most
  96 bytes, every 250 µs. Full speed: 44/45 frames, at most 360 bytes,
  every 1 ms.
- **Descriptors.** USB MIDI's descriptor unit declares a two-channel input
  with bmChannelConfig front left + front right (`0x3`, the standard stereo
  cluster) in the input terminal and AS_GENERAL, at both speeds; 24-bit
  samples in 4-byte subslots, a fixed 44.1 kHz clock, as EXTENDED.
- It takes the same hook sites as EXTENDED and FULL, so a remix carries
  one of the three.

## Measured under the port

`verify_usb` with `REMIX=usb-master` and `REMIX=bottleservice`
(27 Sep 2026):

- EP `0x83` isochronous, 96 bytes, bInterval 2; AS_GENERAL 2 channels,
  bmChannelConfig `0x3`.
- 88/96-byte packets, none empty after the first ten; every subslot's low
  byte zero; counters: 0 overruns, 0 underruns.
- Taps: with the read-back arena re-poked before every poll with words that
  name their source, side and frame, channel 1 carries T8 L and channel 2
  T8 R, only those, at high speed and at full speed.

## Per block

Instructions executed per block by the producer at high speed, counted
from the source: about 180 (10 per frame), against about 2,710 for
EXTENDED; 32 read-back words read per block against 320. The copy into
each packet moves 88–96 bytes against 880–960. Not cycles: `modules/cfmeter`
(CF METER) measures the frame interrupt's duration on a unit.

## Not measured

- Anything on hardware.
- Which channels an iOS app records by default. The descriptor declares a
  plain two-channel front L/R input; an app that takes the first two
  channels gets T8.
- Full speed on a phone: whether an iPhone or its adapter connects at high
  or full speed. Both carry T8.
