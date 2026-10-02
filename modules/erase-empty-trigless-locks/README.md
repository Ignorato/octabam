# `erase-empty-trigless-locks` -- ERASE_EMPTY_TRIGLESS_LOCKS

A trigless lock whose last remaining lock is erased disappears from the trig row instead of staying lit. A deliberately empty trigless lock placed with `FUNC` + `TRIG` is left alone.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `8773713`). `Kind.CF_PATCH`. One ROM cave (`patch_triglock.s`).
`upstream/octabam-modules/erase-empty-trigless-locks/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=erase-empty-trigless-locks` (`remixes/test/erase-empty-trigless-locks/`) builds and boots the
  image under the ColdFire port.

## On the unit

- On the author's MKI.
