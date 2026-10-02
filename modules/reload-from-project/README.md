# `reload-from-project` -- RELOAD_FROM_PROJECT

Reload one track's sequence from the CF card without stopping the transport: `[PTN]` + `[TRACK n]` reloads that track's card-saved sequence with the Part untouched; `[BANK]` + `[TRACK n]` also re-applies the saved Part. A toast confirms.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `7f80b85`). `Kind.CF_PATCH`. One ROM cave (`patch_reload3.s`).
`upstream/octabam-modules/reload-from-project/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=reload-from-project` (`remixes/test/reload-from-project/`) builds and boots the
  image under the ColdFire port.

## On the unit

- On the author's MKI, including that the sequencer and the internal metronome keep their phase.

## Notes

- All-tracks and whole-bank reload are not implemented.
