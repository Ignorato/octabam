# `usb-midi` — USB MIDI

Class-compliant USB-MIDI in and out on the Octatrack's own USB port,
mirroring the DIN ports. markandrus's work ([octemu](https://github.com/markandrus/octemu),
`custom/usb-midi.py` + `custom/coldfire/usb-midi.s` at `6a9ff68`, MIT),
carried onto octabam's DRAM platform.

## Measured

Under the ColdFire port (25 Sep 2026), `make check REMIX=usb`, `verify_usb`:

- enumerates at high speed as Elektron 1935:0002, three interfaces, 124-byte
  configuration; INQUIRY and TEST UNIT READY still answered by the stock
  mass-storage stack;
- two channel messages sent to EP2 OUT → six bytes into the firmware's
  MIDI receive FIFO (`midi_rx_fifo_head` `0x46100b80`, six writes from
  `midi_rx_enqueue`);
- the firmware's own `midi_send` on a note-on → one event packet `09 90 3c 64`
  on EP2 IN.

His build from the same stock bytes, tested first under the port with his
own patch scripts, behaved the same (the ISR shim ran nine times, the
decoder once, the same six FIFO writes).

## Receive path (port only, 5 Oct 2026)

Static review of `usbmidi_rx_decode` found no bound on the FIFO, then
measured under the port (`usb-midi` remix, `ot_emu --watch-mem` on the
FIFO and the framer's message buffer, one EP2 OUT packet per case):

| packet | before | after |
|---|---|---|
| 16 note-ons, 64 B (48 MIDI bytes) | FIFO count reached 48 of 32 slots; 16 messages parsed, notes `3b 3c 3d 3e 3f 35 36 37 38 39 3a 3b 3c 3d 3e 3f`; `30..34` never parsed | 16 messages, notes `30..3f` in order |
| 68-byte SysEx, 23 events, 92 B | dTD accepted 64 of 92 B; the 68 bytes did not arrive in the parser's buffer (`verify_usbmidi_rx`, first difference at byte 0) | 92 B accepted, `F0 01..42 F7` parsed intact |
| 128 note-ons, 512 B | dTD accepted 64 of 512 B; the 384 bytes did not arrive in order (first difference at byte 0) | 512 B accepted, 384 bytes parsed in order |
| 16 note-ons at full speed, 64 B | in order | in order |

Causes (read from the stock disassembly; the measurements above agree):

- `midi_rx_enqueue` (`0x40092bbc`) stores `ring[head]`, `head++` (wrap at 32),
  `count++` and forces INTC source 36, with no full check. The consumer, the
  framer `0x40092bf4`, pops one byte per interrupt. Its ICR (`0xfc048064`) and
  the USB OTG ICR (`0xfc04c06f`) are both written `4` by the firmware, so the
  framer cannot run inside the USB interrupt at any SR. The DIN path takes one
  byte per UART interrupt and never fills the ring; a packet of more than 32
  MIDI bytes overwrites unread ones.
- The RX dTD token is `0x00408080` (64 bytes) at the dormant init and in
  `usb_midi_rx_prime`, while the dQH and the descriptors advertise a 512-byte
  bulk max packet at high speed.
- The dTD token's status bits were not read.

`usbmidi_rx.s` (octabam's; `usbmidi.s` is unchanged and still matches his
build) takes over the SET_CONFIGURATION and usb_isr detours and hands on to
his shims:

- Before the bytes of each event are enqueued, `count + event bytes` must be
  at most 32; otherwise the framer is entered from the decoder with a
  fabricated exception frame (format 4, vector `0x64`, the current SR, over a
  return address), pops one byte, parses it and posts what it completes, as its
  interrupt would. The framer runs at the SR the USB ISR entered with; the
  enqueues of one event run at SR `0x2700`.
- Chosen over lowering the SR mask around each enqueue (the framer is the same
  INTC level as the USB interrupt and cannot preempt it; lowering the mask
  below 4 lets the USB interrupt re-enter) and over keeping the rest of the
  packet for a later interrupt (nothing wakes the module after the last USB
  interrupt of a burst).
- At high speed the RX dTD is re-sized to 512 bytes: flush EP2 OUT
  (ENDPTFLUSH bit 2), clear the dQH overlay token, prime with token
  `0x02008080`. Full speed keeps the firmware's 64-byte dTD (max packet 64: a
  dTD larger than the max packet does not complete on a full packet).
- A completed dTD with halted, data buffer error or transaction error status
  is counted in `usbmidi_rx_errs` and not decoded.

The port's flush completes at once and ignores the overlay; the controller's
behaviour on the flush/re-prime sequence is not measured. Hardware status:
port only.

## On the unit

Image 64, `usb-audio`, Sam's MKII, 25 Sep 2026:

- Enumerates on macOS as a MIDI port "Elektron Octatrack DPS-1", beside
  the USB AUDIO input.
- Receive: 896,760 messages (7,170/s, notes + CCs on channel 16) and then
  1,471,080 messages (7,950/s, 185 s) sent into the unit, with the audio
  stream running, without a stall or a change in the audio stream
  (`modules/usb-audio-out-tracks-main-cue/README.md`, the image 64 takes).
- No USB MIDI transmit measurement from the unit is recorded.

Also carried on Tim Hastie's MKI (`octatrick-usb`, OCTATRICK9, 26 Sep 2026),
Bryan T's MKII (`usb-lean` image 90, 25 Sep 2026) and Sam's MKII as image 88
(`bottleservice`, 27 Sep 2026); none of those runs measured MIDI itself.
The `usb-midi` remix (this module on the stock effects) has not been flashed.

## Open

- Not measured: timing on the unit (bulk transfers have no schedule; clock
  jitter over USB against DIN), a CC flood against the 256-byte queue,
  DISK MODE entered with a MIDI session open, Windows.

## Gates

- `verify_usb` (`make check REMIX=usb`).
- `verify_usbmidi_rx` (image stage): the four packets of "Receive path",
  parsed bytes compared with sent bytes, and each packet accepted whole by
  the dTD. Five of its nine checks fail on the code before this change.

## What it is

OS 1.40C ships a complete USB-MIDI transmit encoder (`0x4001d204`: raw
bytes to 4-byte event packets, running status, SysEx spans) and the EP2
primitives, reached by nothing, and no receive decoder. The module:

- grows the configuration descriptors to MSC + AudioControl + MIDIStreaming
  with EP2 bulk in/out (`descriptors.py`, generated per remix into the
  `usbmidi_cfg` unit; `cfg_len` is the length the two clamp shims read);
- brings EP2 up at SET_CONFIGURATION (512-byte packets at high speed),
  answers CLEAR_FEATURE(ENDPOINT_HALT) for it;
- dispatches EP2 completions from the USB ISR: IN completion frees the
  transmit slot and drains the queue, OUT completion runs the receive
  decoder, which feeds `midi_rx_enqueue` (`0x40092bbc`), the byte path DIN
  MIDI uses, then re-primes (`usbmidi_rx.s`, see "Receive path");
- mirrors both senders into the encoder: `midi_send` (channel messages)
  and the priority byte sender (clock, transport). Messages are queued in
  a 256-byte accumulator behind one transfer; a message that would
  overflow it is counted in `usbmidi_tx_drops`, never sent corrupt.

Seven detours, four descriptor-pointer rewrites, no pokes. The `usbmidi`
unit is his file verbatim (two of the detours reach `usbmidi_rx` first), and the build proves it: every build re-links
it at his zone address `0x400d24f0` and compares with the 1,124-byte blob
his `usb-midi.py` produced from our stock bytes (`Linked.reference`, the
port-is-a-proof rule). The clamps are a second unit (`clamp.s`, his
usb-audio.s shims reading `cfg_len`).

## Ground

| what | where |
|---|---|
| code + queues | DRAM units `usbmidi` (1,124 B, his bytes), `usbmidi_rx` and `usbmidi_clamp` in the platform reserve |
| descriptors | DRAM unit `usbmidi_cfg` (4 × 124 B, or 4 × 250 B with a USB AUDIO module) |
| hooks | `0x4001d9ca` `0x4001daec` `0x4001e606` `0x40010bc8` `0x400108b0` `0x4001d858` `0x4001d896` |
| pointer rewrites | the responder's four `pea` operands `0x4001d882` `0x4001d88a` `0x4001d8c0` `0x4001d8c8` |
| firmware memory it uses | the firmware's own EP2 dQHs, dTDs and buffers (`0x4ec94900..`, `0x4ecc8000`, `0x4ecc9000`; the RX buffer's 4 KB page has no other reference in the image) |
