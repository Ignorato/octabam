# `quantize-live-rec-toggle` -- QUANTIZE_LIVE_REC_TOGGLE

One ColdFire module by Zac Kyoti and the stock effects.

## What is in it

- **QUANTIZE_LIVE_REC_TOGGLE** -- [`modules/quantize-live-rec-toggle/README.md`](../../../modules/quantize-live-rec-toggle/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Each module's bytes are the author's: `reference` re-links them at his addresses every build and compares. Those images ran on the author's MKI, 25 and 30 Sep 2026. This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=quantize-live-rec-toggle BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=quantize-live-rec-toggle` runs every gate first.
