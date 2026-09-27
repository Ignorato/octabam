# `stems`: STEM REC alone

One ColdFire module and nothing else. For recording what the tracks play to the card, while the sequencer runs, as one file per track.

## What is in it

- **STEM REC.** MAIN MENU > CONTROL > STEM REC arms a take, or starts one if the sequencer is running. Selecting it again stops the take, and so does stopping the sequencer or reaching 60 minutes. Each enabled track is a 16-bit stereo file, `<set>/AUDIO/YYMMDD-HHMM/T<n>.wav`. This build enables T1. `modules/stems/README.md`.

## Status

Never flashed. Measured under the ColdFire port: `python3 tools/verify/verify_stems.py stems` records takes and checks every sample against the track's own audio. The first flash's plan is `modules/stems/FLASH.md`. The stock facts it stands on are in `docs/firmware/STEM_REC.md`.

## Build

```bash
make image REMIX=stems BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=stems` runs every gate first.
