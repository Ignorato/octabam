# `mods` — every ColdFire mod in one image

MIDI SCENES, Octakit, the recorder fixes, REPITCH, octatrick's three machines, USB MIDI and USB AUDIO on the stock effects. SCENES P2 is not in it: the ledger refuses it beside KITS RELOAD and MIDI SCENES.

## What is in it

- **MIDI SCENES** (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc) 1.40MIDISC8.2) — per-scene parameter locks driven over MIDI: a second lock table the panel never had; scene hold, XF morph, part save/reload and the scene clear/copy/paste rows read it when a MIDI event is driving. The panel path is untouched. Twelve units in DRAM, 38 detours, 4 pokes inside the OS.
- **OCTAKIT** (Em, [ems-octakit](https://github.com/emuyia/ems-octakit) ot-26914) — 256 Kits per Project in place of 64 bank-tied Parts. MKII: PART opens LOAD KIT, FUNC+PART opens SAVE KIT; MKI: FUNC+MIDI opens LOAD KIT, FUNC+BANK opens SAVE KIT. FUNC+CUE reloads the assigned Kit; Kits have 7-character names; the LOAD/SAVE KIT menus copy/paste/clear/undo, LOAD KIT > UNDO KIT reloads the last loaded Kit; FUNC+PASTE+PART (MKI: FUNC+PASTE+MIDI) on a pasted Pattern also saves its Kit to the next free slot; PTN+FUNC+RIGHT saves the current Kit, copies it and the Pattern to the next free slots and loads the pair; PTN+FUNC+TRIG copies/pastes/clears/undoes inactive Patterns (BANK+TRIG, then BANK+FUNC+TRIG for other Banks). Costs 3.6 % of the flex pool (18.4 s at 16-bit). Old projects migrate their Parts into the first 64 Kit slots on load. A 154,718-byte runtime in DRAM, carried by octabam's loader.
- **LOFI AMF FIX** (Bryan T, [octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt)) — stock LO-FI's AMF knob jumps the pitch backwards at some settings because its coefficient multiply is `mpysu` (signed × unsigned) where both operands are magnitudes; two DSP words become `mpyuu`.
- **CC MAP** (Sam Banks) — MIDI CC 62–67 reach the FX2 effect's page-2 knobs (slots 6–11) and CC 68–73 the FX1 effect's; stock reaches only page 1 over MIDI. One ColdFire cave. Confirmed on hardware 13 Sep 2026.
- **SCENES KITS** (Sam Banks) — the bridge that lets CC MAP and Octakit share the MIDI CC dispatch entry: CCs 62–73 CC MAP's, then Octakit's, then stock's. Nothing of its own to use.
- **KITS RELOAD** (Sam Banks) — the bridge that lets MIDI SCENES' Part Reload run beside Octakit's kit reload: Octakit's reload validates its caller's return address, midisc's stub substituted it (OKMS1 trapped on the first Part Reload); the stock call stays and midisc's post-reload restore runs from the return sites.
- **FLEX SEEK BIND** (sambanks) — ColdFire cave: a same-slot/type/generation FLEX re-bind takes the bind's same-sample path (DSP seek) instead of becoming a new note.
- **FLEX SEEK BIND CTR** (sambanks) — ColdFire cave: on a same-sample FLEX re-bind, do not bump the voice's per-bind counter (pairs with FLEX SEEK BIND).
- **RECORDER SPACING** (sambanks) — ColdFire cave: a fixed-RLEN recording is exactly as long as the gap to the next arm, derived from the current arm -- no lane, no stored state.
- **RECORDER HOLD** (sambanks) — ColdFire cave: a recorder-buffer FLEX voice reading one sample past its recording repeats the last sample instead of reading zero.
- **RLEN PLEN** (sambanks) — ColdFire cave: RLEN value PLEN (past MAX) = one loop of the track's pattern on its own scale, so TRIG ONE + QREC PLEN records the next pass and stops.
- **REPITCH** (repeat98) — Adds TSTR REPITCH (STATIC/FLEX and the sample's own TIMESTRETCH): project-tempo following by playback speed, without grains; PTCH off.
- **DIRECT JUMP** (timhastie/octatrick-modules) — CHAIN AFTER: DIRECT (its unused value 1) -- a pattern change lands at the next step, the step count continuing (A4/Rytm direct jump).
- **SCALE QUANTIZER** (timhastie/octatrick-modules) — PROJECT > CONTROL > SEQUENCER > SCALE: the PTCH knob and CHROMATIC trig keys quantize to a scale (24 scales, OFF = stock); > GLIDE: the synth's glide time (OFF, 1..127) and 303-style legato on the chromatic keys; polyphonic chromatic keys on a synth track whose VOIC is 2..4.
- **SYNTH MACHINE** (timhastie/octatrick-modules) — A FLEX track whose sample is named SYNTH* plays a two-operator FM voice (STRT/LEN/RTRG/RTIM = ratio/index/feedback/decay); the DSP shapes and effects it as a sample. Its PLAYBACK page reads RATO/INDX/FDBK/DEC with icons and the title FM SYNTH.
- **USB MIDI** (markandrus/octemu) — Class-compliant USB-MIDI in and out on the OT's own USB port, mirroring the DIN ports (markandrus/octemu).
- **USB AUDIO OUT TRACKS MAIN CUE** (markandrus/octemu) — Twenty 24-bit channels over USB (UAC2): the tracks post-FX pre-fader, MAIN, CUE; the stereo sum at full speed (markandrus/octemu).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Boots under the ColdFire port; every `apply_part` in a project load runs the chain. Not flashed as a whole. On hardware in subsets: `ok-ms` (MIDI SCENES + Octakit + KITS RELOAD, 14 Sep 2026), the recorder fixes as OCTABAM83/84 (12 Sep 2026; RECORDER HOLD and RLEN PLEN port-gated), REPITCH as OCTABAM81 (16 Sep 2026), octatrick's three with USB as OCTATRICK9 (26 Sep 2026), USB AUDIO as image 64 (25 Sep 2026). Unmeasured: MIDI CCs through the chained dispatch, and his Part save/reload menu hooks against her LOAD/SAVE KIT menus.

## Build

```bash
make image REMIX=mods BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=mods` runs every gate first.

## Before you flash

- **Octakit migrates Parts into Kits on project load.** Back up projects first; going back to stock can lose Kit data.
