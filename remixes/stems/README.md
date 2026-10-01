# `stems`: STEM REC on the stock effects

One ColdFire module on the stock effects. For recording what the tracks play to the card, while the sequencer runs, as one file per track.

## What is in it

- **STEM REC.** MAIN MENU > STEMS, a fifth category: REC arms a take, or starts one if the sequencer is running. STOP ends it, and so does stopping the sequencer or reaching 60 minutes. T1 to T8 turn tracks on and off (all eight at boot), a status row shows the take's time, `DONE` or an error by name, and PEAK the ring's highest fill. Each enabled track is a 16-bit stereo file, `<set>/AUDIO/YYMMDD-HHMM/T<n>.wav`. `modules/stems/README.md`.
- **The 14 stock effects**, listed so the FX2 chooser is stock's. A remix that lists none draws a one-row chooser, and STEMS1 did.

## Status

On hardware: STEMS1 on Yves's MKII, 30 Sep 2026. T1 alone, then T1 to T8 for about two minutes: every take whole, every file plays, and stopping the sequencer ended the take. Open: the first boot after the upgrade had no audio until a power cycle, and the stems sit about 12 dB under normal playback, by ear (`docs/firmware/STEM_REC.md` section 17.1). STEMS1 listed STEM REC alone. STEMS2, this remix with the stock effects, flashed on the same MKII on 1 Oct 2026, and FX2's page shows the stock effects again.

Measured under the ColdFire port: `python3 tools/verify/verify_stems.py stems` records takes and checks every sample against the track's own audio, and `python3 tools/verify/verify_stems_menu.py stems` presses the menu's keys on the MKII and MKI panels, a take included. The flash checklists are in `modules/stems/FLASH.md`. The stock facts STEM REC stands on are in `docs/firmware/STEM_REC.md`.

## Build

```bash
make image REMIX=stems BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=stems` runs every gate first.
