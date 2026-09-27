# `usb-io` — twenty channels out, a stereo pair in, over USB, on the stock effects

The stock chooser plus USB MIDI, USB AUDIO EXTENDED, USB CROSSBAR and USB
AUDIO IN: the Octatrack as a USB audio interface with a stereo return into
inputs A/B.

- **USB MIDI** and **USB AUDIO EXTENDED** (markandrus/octemu; MAIN/CUE Bryan
  T): USB-MIDI mirroring DIN; the eight tracks, MAIN and CUE to the host,
  24-bit, every 250 µs. [`modules/usb-audio-extended`](../../modules/usb-audio-extended/README.md).
- **USB CROSSBAR** (Bryan T): the USB controller bursts and goes first on the
  SDRAM and SRAM crossbar ports, set at boot. Without it the IN stream loses
  packet tails under a busy project. [`modules/usb-crossbar`](../../modules/usb-crossbar/README.md).
- **USB AUDIO IN** (Bryan T): a stereo pair from the host into inputs A/B,
  asynchronous with implicit feedback from the EXTENDED stream; C/D and,
  while the stream is closed, A/B are the jacks. [`modules/usb-audio-in`](../../modules/usb-audio-in/README.md).
- 13 of the 14 stock FX2 effects. SPATIALIZER is on neither menu: its words on
  payload A hold USB AUDIO IN's RX inject, and a project that still selects
  it runs NONE.

Under the port, `make check REMIX=usb-io` passes (28 Sep 2026): `verify_usb`
(six interfaces at high speed, five at full), `verify_usb_in` (the pair
bit-exact on A/B, C/D untouched, the jacks back after alt 0). This form has
not been flashed. Bryan T's usbin-test `usb-io` (four channels each way
beside MAIN + CUE, builds 12–16, 26–27 Sep 2026) ran on his MKII: about
5 million host packets with no bad packet, underrun or overrun; DISK MODE
works and the stream comes back after it; the round trip through the two
rings measured about 31 ms. `usb-mc` keeps that MAIN + CUE input layout.

```
make image REMIX=usb-io BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a
fresh machine to a flashed unit. On the unit: `tools/hw/usb_probe.py`
(sustained, then churn) with the counters before and after, then a host →
A/B → recorder take.
