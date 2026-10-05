# `kits` — KITS

256 Kits per project. A Kit is a saved Part; each pattern plays the Kit
assigned to it, through the stock Part slots. `Kind.CF_PATCH`: one DRAM
unit (`kits.s`), 22 detours, nothing on the DSP. The firmware facts it
stands on are [`docs/firmware/PARTS.md`](../../docs/firmware/PARTS.md).
Markers as in `CHIP.md`: ✅ measured, 📖 read from the code.

## Use

| keys | MKII | MKI |
|---|---|---|
| LOAD KIT | PART | FUNC+MIDI |
| SAVE KIT | FUNC+PART | FUNC+BANK |
| quick save (the Kit under the cursor, its name kept) | FUNC+PART, then FUNC+YES | FUNC+BANK, then FUNC+YES |
| reload the current Kit | FUNC+CUE (stock Part Reload) | FUNC+CUE |
| the pasted pattern plays a copy of its Kit in the next empty Kit | FUNC+PASTE+PART (PART while STOP is held after the paste) | FUNC+PASTE+MIDI |
| save the Kit, copy it and the pattern to the next empty ones, play the copy | PTN+FUNC+RIGHT | PTN+FUNC+RIGHT |
| copy / paste / clear an inactive pattern of the current bank (paste or clear again: undo) | hold PTN, FUNC and the pattern's TRIG; REC / STOP / PLAY | the same |

- **LOAD KIT** lists UNDO KIT (the Kit the current pattern had before
  the last load), the 256 Kits (`NNN name`, `*` on a Kit no pattern
  plays, `NNN ---` on an empty one) and two settings, AUTOSAVE and KEEP
  LEVELS (YES turns one on or off). YES on a Kit: the current pattern
  plays it, now.
- **SAVE KIT** lists the 256 Kits, the cursor on the current Part's.
  YES opens the name editor (seven characters, `NEW KIT` for an empty
  Kit); the current Part is saved into the Kit and the current pattern
  plays it.
- In either list, FUNC+REC copies the Kit under the cursor, FUNC+STOP
  pastes onto it, FUNC+PLAY clears it; the same paste or clear again on
  the same Kit undoes it.
- **AUTOSAVE**: at a pattern change request, the playing Part's edits go
  into its Kit (and its saved Part) first (ems-octakit discussion #2).
- **KEEP LEVELS**: a Kit loaded into a slot keeps the slot's eight track
  levels (Part `+0x12 + 2t`, the bytes CC 7 writes, measured; the cue
  levels at `+0x13 + 2t` come from the Kit) (ems-octakit discussion #3).
- The current Part's name is the Kit's first six characters (the stock
  Part name field is seven bytes).

## How it works

- **Staging.** Before a pattern is scheduled (`0x400a0570`: the panel,
  program changes, the project load) or appended to a chain
  (`0x4009c634`), its Kit is copied into a Part slot of its bank that
  nothing is playing, and the pattern's Part byte names that slot; the
  switch reads the Part byte then (PARTS.md section 3). A slot is free when
  no engine track names it while the transport runs, no queued or
  chained pattern's Part byte names it, and its working Part is byte for
  byte the Kit KITS recorded there. A slot whose content is in no Kit is
  never copied over. With no free slot, or a request with an interrupt
  level set (the arranger and repeat publish from the tick), the pattern
  plays what is resident and the request is counted.
- **LOAD KIT** writes the Kit into the current Part's saved copy and runs
  the stock Part Reload `0x4004aab4` (working copy, CS1 copy, engine
  apply, machine transitions). **SAVE KIT** runs the stock Part Save
  `0x4004a908`; its tail copies the saved Part into the slot's Kit, so a
  plain Part Save and SAVE ALL update the resident Kits too. Other slots
  holding an unedited copy of a saved Kit get the new content.
- **The pattern clipboard carries the Kit**: the stock pattern copy
  (`0x40026eb0`), the paste's undo snapshot (`0x40026ef0`) and the paste
  or undo restore (`0x4002b9b0`).
- **Files.** `kits.work` and `kits.strd` in the project directory:
  64 bytes of header (`KITS`, version 1, length, CRC-32 of the rest,
  the settings), ASSIGN (256), the valid bits (32), RESID (64), then 256
  records of an 8-byte name, 8 reserved bytes and the 6,322-byte Part:
  1,622,944 bytes. Written after the bank writer (`0x400917c8`) when a
  Kit or an assignment changed, copied to `.strd` by the project store
  (`0x4008ee74`) and back by the project reload (`0x4008f180`). A
  `kits.work` that fails its CRC is never overwritten; the project then
  plays its Parts as stock.
- **First load of a project.** With no `kits.work`: Em's `kits3a.work`
  and `kits3b.work`, when present, are imported (per Kit the newest
  record whose CRC-32 holds, ASSIGN from the newest manifest); each slot
  is matched to the Kit equal to its working Part, and a slot equal to
  none is saved into the next empty Kit. Without them the stock Parts
  migrate: Kit `bank·4 + part` is the working Part with its name, each
  pattern with content plays its Part's Kit. Her files are left on the
  card.
- **Power-off.** RESID (with a magic and a sum) at `0x100f85a0` and ASSIGN
  at `0x100ffe00` in CS1 (stock references nothing there; PLOCKS P2 holds
  `0x100f8600..0x100ffe00`). The power-up's bank load (the masked load
  returning to `0x40084d66` when no project has been loaded since boot)
  takes them from CS1.
- The masked bank load `0x400905d4` is told apart by its return address
  (PARTS.md section 8): LOAD PROJECT (`0x400853de`), the power-up
  (`0x40084d66`), anything else (the masked banks' slots are forgotten
  and restaged).
- No `illegal`. The counters (`KSTATE` in the unit, read by the gate):
  READY, CNT_ISR, CNT_NOSLOT, CNT_INVALID (an assignment naming an empty
  Kit), CNT_IOERR, CNT_BADFILE, CNT_STAGED, CNT_REPOINT, CNT_AUTOSAVE.

## Measured

Under the port, 6 Oct 2026, `tools/verify/verify_kits.py kits` on
OCTABAM89_setgate (bank 3), each scenario forked from one load:

- ✅ The load migrates the Parts and writes `kits.work` (CRC holds); no
  stock file rewritten; the firmware's LOG has no new error.
- ✅ PTN+TRIG while playing, while stopped, a program change (channel 1)
  and a three-pattern chain each stage their Kits, repointing Part bytes
  off the playing slot; the engine plays the staged slot after the switch.
- ✅ The chain with a track key every 25 ms for 3 s across the first
  switch (ems-octakit #5), 250 track presses at 180 ms over the chain, and
  a CC 7 every frame for 3,000 frames: no halt, every counter zero.
- ✅ LOAD KIT, UNDO KIT, SAVE KIT with the name editor, quick save, the list
  copy / paste / clear and their undos, the AUTOSAVE and KEEP LEVELS rows
  and behaviours, a pattern copy and paste carrying its Kit (and the undo
  restore, its stock routines called in order: the panel's second
  FUNC+STOP pastes again under the port, on stock too), FUNC+PASTE+PART,
  PTN+FUNC+RIGHT, PTN+FUNC+TRIG paste and its undo.
- ✅ SAVE PROJECT writes `kits.work` and `kits.strd`; a second boot of the
  card, a power cycle of it (`--cs1-in`, `--no-post`) and a power cycle
  of a card whose change was never saved each come back with the same
  ASSIGN and RESID.
- ✅ Em's files from the Bottleservice 2026 backup: 64 occupied Kits,
  each name and Part equal to what her format gives, ASSIGN from her
  newest manifest, `kits.work` written, hers left in place.
- ✅ `PROJECT 261004p` (its `bank01.work` rejected by the firmware, her
  files holding one Kit): the load, 400 frames playing and a pattern
  paste, no halt, every counter zero.
- ✅ A project name with no directory: the load runs, the `kits.work`
  write fails and is counted.
- ✅ Cost: a stage that copies one Kit took 133,563 instructions in the
  first build (four whole-Part compares); the compare now runs only on
  slots no track names.

## On the unit

Not flashed.

## Open

- The arranger: its schedule runs in the tick, so its patterns play what
  is resident (counted as CNT_ISR). Not exercised.
- PER TRACK scale and plays-free tracks: how many Parts the engine names
  at once is measured only for the normal case (one).
- PTN+FUNC+TRIG covers the current bank; Octakit's BANK+TRIG > BANK+FUNC+
  TRIG for other banks is not carried. Its clear clears the eight audio
  tracks' steps and locks (`0x40039df4`), not the MIDI tracks.
- The status bar shows the stock `Pt:N name`, the Kit's first six
  characters; Octakit's `NNN name` is not drawn.
- `kits.work` is written whole (1.6 MB) when anything changed; Octakit's
  per-record writes are not carried.
- MIDI SCENES' own Part reload hooks are on the stock call sites; LOAD
  KIT calls the reload directly, so his post-reload restore does not run
  for a Kit load (FUNC+CUE goes through his hooks as on stock).
- Whether the CS1 range holds over a power-off on the unit is read from
  stock's use of CS1 (as PLOCKS P2), not measured.

## Gates

- `tools/verify/verify_kits.py`.
