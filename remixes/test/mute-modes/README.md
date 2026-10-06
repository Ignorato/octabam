# `mute-modes` -- MUTE_MODES

One ColdFire module by Zac Kyoti and the stock effects.

## What is in it

- **MUTE_MODES** -- [`modules/mute-modes/README.md`](../../../modules/mute-modes/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Each module's bytes are the author's: `reference` re-links them at his addresses every build and compares. Those images ran on the author's MKI. This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=mute-modes BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=mute-modes` runs every gate first.
