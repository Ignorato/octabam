# `direct-jump-kyoti` -- DIRECT_JUMP_KYOTI

An immediate pattern change, toggled with `[PTN]` + `[YES]` and OFF at every power-on. A cued pattern takes over on the next step, locked to the master clock: it plays where it would be had it been running since START, whatever its track lengths, scales or master settings.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `7f80b85`). `Kind.CF_PATCH`. One floating ROM cave (`patch_directjump_v7.s`) with hooks at `0x400a1f72` (the landing), `0x400a221c` and `0x40043418` (the `[PTN]` release), and the `[PTN]`-layer YES record. Its on/off word lives in the cave, so it is re-loaded from the image at every boot.
`upstream/octabam-modules/direct-jump-kyoti/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=direct-jump-kyoti` (`remixes/test/direct-jump-kyoti/`) builds and boots the
  image under the ColdFire port.

## On the unit

- 27-28 Sep 2026: the clock-locked timing and the Part change on the author's MKI (standalone image `140C_KDJ7`, and the KYOTI V1.0 combined image).
- Emulator-verified only (author's `ot_emu`): Program Change on fast re-cues, MIDI tracks, START SILENT and the trig-condition reset.

## Notes

- Not the same module as Tim Hastie's DIRECT JUMP (`modules/direct-jump/`, CHAIN AFTER: DIRECT). The ledger finds no shared address, but both change when a cued pattern takes over and they have not been run in one image: take one per remix.
- The author pairs it with BATCH_BUGFIXES: its Part changes reach the handler that module's Part-change carryover fix repairs.
