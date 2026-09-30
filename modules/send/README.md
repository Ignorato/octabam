# SEND

The bus client: two knobs, DEL (slot 0), this track's level into the delay,
and REV (slot 1), its level into the reverb. The reverb also hears the
delay's repeats × its DLY knob; each engine's wet comes out on the track
that hosts it. One knob into a delay-then-reverb chain from 6 to 25 Sep 2026.

It taps the audio buffer and never writes it, so a SEND at DEL 0 and REV 0 is
indistinguishable from no effect. A fresh, unassigned track (FX2 id 0) is
aliased to it rather than to NONE because SEND does the per-block bus
housekeeping, so no track can stall the bus. It is also the fallback: an id
a bus-carrying remix does not implement resolves here. The send is refused
on track 8 by construction: with MASTER TRACK on, T8's input is the mix,
the hosts' wet included, and a send from it would put that wet back into
the bus. The alias also puts SEND on every FX1 slot set to NONE; there it
returns at proc entry (r7 0x6100/0x6400/0x6700/0x6a00, image 48), so an
empty FX1 slot neither sends nor touches the rotation tracker
(`docs/effects/XBUS.md`).

## Measured

Carried by every flashed bus image (`CHANGELOG.md`); the two-knob form
(DEL and REV, 25 Sep 2026) by image 88 on Sam's MKII (27 Sep 2026). The
auto-gain numbers below are `dsp_host` measurements; the T8 refusal and
the FX1-NONE return were measured under the ColdFire port.

## The auto-gain

Each accumulator (DEL's and REV's) is scaled by 1/√N of its own registered clients, so eight
senders drive a server as hard as one. A quiet sender turns the loud sender's
reverb down: three senders, two of them 10–15 dB quieter, measured 4.8 dB
below the loud sender alone. A client that registers and contributes nothing
dilutes everyone (−3.0 dB with one sender under 1/√N; the −6.02 dB
measured on 17 Aug 2026 was under 1/N), which is why every level knob
gates its own registration. A track already sending loses 3 dB of wet each
time the sender count doubles (1→2, 2→4, 4→8), stepped per block when a
knob leaves 0; N counts knobs, not signal, per bus.

[`docs/effects/XBUS.md`](../../docs/effects/XBUS.md).

## Who uses what on the bus (Y memory)

| | |
|---|---|
| BusVerb | `Y:0x4000–0xBFFF`, 32,768 words, hardcoded, both payloads (different cores) |
| BusDelay | LineL `Y:0x38000–0x3FFFF` + LineR `Y:0x4000–0xBFFF` on core 1 ([`busdelay`](../busdelay/README.md) "Memory") |
| bus scratch | `Y:0x900–0xad9`, 474 words; `send_client.asm` is the authoritative map (❌ `0x900–0x980`, "parity word", 4 wet buffers until 30 Aug 2026) |
| per-instance base stash | `Y:0x795 + (r7>>8)`, one word per instance |
| SEND | nothing; never touches its own slot |

32,768 words of shared window is the ceiling per server; BusVerb is at it,
and BusDelay adds the private region on its core. The Y map per core is
`docs/firmware/CHIP.md` §3.
