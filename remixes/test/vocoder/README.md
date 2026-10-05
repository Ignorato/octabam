# `vocoder` -- VOCODER

VOCODER beside the stock effects (all but PLATE REV, whose words it takes, and DJ EQ, so its tables sit in X memory). VOCODER runs on FX2 of tracks 2, 3, 6 and 7 only (two per DSP core, not a core's first track) and passes audio elsewhere.

## What is in it

- **VOCODER** -- [`modules/vocoder/README.md`](../../../modules/vocoder/README.md).
- the stock effects but PLATE REV, listed so the chooser is otherwise stock's.

## Status

Renders in `dsp_host` (`tools/verify/verify_vocoder.py`); the per-track limit checked under the ColdFire port. On a MKII (OCTABAM7-9, 4 Oct 2026) two per core played and three stalled, which is why the limit is built in; with the limit built in, OCTABAM12 ran VOCODER on FX2 of all eight tracks, stable (two vocoding per core, the rest dry).

## Build

```bash
make check REMIX=vocoder
```
