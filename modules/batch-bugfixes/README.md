# `batch-bugfixes` -- BATCH_BUGFIXES

Three fixes to stock 1.40C behaviour as one module: MIDI Plays-Free trig (a Plays-Free MIDI track with trig quantize DIRECT and pattern scale PER TRACK stalled after its first step), empty-pattern LED (a pattern holding only parameter locks showed as unused under `[PTN]`), Part-change carryover (stale per-track state from the old Part after a pattern-triggered Part change).

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `7f80b85`). `Kind.CF_PATCH`. Three ROM caves: `patch_trigscale.s` (62 B, one 18-byte splice at `0x4009b6f2`), `patch_pattern_led.s` (158 B, a detour at `0x4009a464`; the `[BANK]` grid's calls from `0x4000fd78` get stock's test), `patch_partreapply.s` (402 B, detours at `0x40062216` and `0x400621da`).
`upstream/octabam-modules/batch-bugfixes/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=batch-bugfixes` (`remixes/test/batch-bugfixes/`) builds and boots the
  image under the ColdFire port.

## On the unit

- Bugs 1 and 3 on the author's MKI; bug 1 on 28 Aug 2026.
- Bug 2: the earlier version on the author's MKI, and the current version's end of the `[BANK]`-held stall; its `[PTN]` answers emulator-verified identical to the earlier version.

## Notes

- A remix takes all three or none.
