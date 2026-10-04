# `testgen` -- TESTGEN

TESTGEN beside 13 stock effects (all but PLATE REV, whose words it takes), on FX2 and FX1.

## What is in it

- **TESTGEN** -- [`modules/testgen/README.md`](../../../modules/testgen/README.md).
- the stock effects but PLATE REV, listed so the chooser is otherwise stock's.
- FX1: TESTGEN first, then FX1's ten stock effects. TESTGEN has no buffers, so an FX1 instance is safe.

## Status

Ran on Ignorato's MKII as OCTABAM4, OCTABAM5 and OCTABAM6, 3-4 Oct 2026 (`make image REMIX=testgen BUILD=6`), and measured at its main outs (`modules/testgen/README.md`). 0.2 (NEEDLE, DC, the FX1 row) has passed the emulator gates only.

## Build

```bash
make check REMIX=testgen
```
