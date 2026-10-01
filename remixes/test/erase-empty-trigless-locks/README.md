# `erase-empty-trigless-locks` -- ERASE_EMPTY_TRIGLESS_LOCKS

One ColdFire module by Zac Kyoti and the stock effects.

## What is in it

- **ERASE_EMPTY_TRIGLESS_LOCKS** -- [`modules/erase-empty-trigless-locks/README.md`](../../../modules/erase-empty-trigless-locks/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Each module's bytes are the author's: `reference` re-links them at his addresses every build and compares. Those images ran on the author's MKI. This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=erase-empty-trigless-locks BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=erase-empty-trigless-locks` runs every gate first.
