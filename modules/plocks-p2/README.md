# `plocks-p2` — PLOCKS P2

Parameter locks on page 2 of FX1 and FX2. `Kind.CF_PATCH`: one DRAM
unit, 50 detours, nothing on the DSP. Requires SCENES P2.

## Use

Open the FX1 or FX2 SETUP page, hold one or more trigs and turn a knob:
each held step gets that slot's page-2 lock. FUNC held while turning
removes it. The trig plays the lock and the next trig puts the Part's
value back, as page 1 does.

## Measured

Under the port, 2 Oct 2026, `tools/verify/verify_plocksp2.py` on
`plocks-p2` and on bottleservice with PLOCKS P2 added (Octakit, the rig,
SCENES P2 KITS), project OCTABAM89_setgate:

- A held trig and knob A on the FX2 SETUP page lock step 1's page-2
  slot 0; stock's page-1 locks of step 1 stay 0xff.
- Trig copy and paste, clear a trig's locks, pattern copy and paste,
  clear pattern and its undo each carry or clear the page-2 locks with
  the stock data.
- T1 step 1 locked to 99 with trigs on steps 1 and 2: the live lane reads
  99 after step 1 and the Part's value after step 2; no other track's
  page-2 lane byte moves. The DSP record follows the lane (both pings,
  measured by hand the same day).
- SAVE PROJECT writes `p2lk03.work` and `p2lk03.strd` with the lock; a
  second boot of that card has it in the table after the load.

## On the unit

Not flashed.

## Open

- The current bank between saves. Stock's background save skips the
  bank being played (`0x40084d8c`: the dirty mask less the current bank)
  and keeps it in RAM and a battery-backed copy (`0x1001614e`) until a
  bank change or SAVE PROJECT. This module has no battery-backed copy:
  page-2 locks edited in the current bank since the last save are lost on
  a power cut, where stock's page-1 locks may survive. Whether stock
  restores the current bank from that copy at boot is not measured.
- Bank reload and project reload (the `.strd` → `.work` copies) are
  hooked and not exercised by the gate.
- The dial draw with trigs held (SCENES P2's dial hooks call `plk_dial`;
  the port's LCD was not decoded).
- Page 2 has no slide: a slide trig moves page 1 only.
- A held step with no trig takes a page-2 lock that never plays (stock
  makes a lock trig from a page-1 lock; not mirrored).
- On the unit.

## Gates

- `tools/verify/verify_plocksp2.py`.

## What stock does

`docs/firmware/STEP_LOCKS.md`. A step record is 32 lock bytes, page 1 of
the five pages. A trig's record goes from the step through a per-track
staging record and a pending slot to the frame ISR, which writes each
lock into the track's live lane and restores the Part's value at the next
trig. Nothing carries page 2, and every byte of the pattern data is used.

## What this adds

- **The table** (`.bss`, 1,572,864 B): 12 bytes a step for every bank,
  pattern, track and step; byte j = FX1 page-2 slot j, 6 + j = FX2's;
  0xff = no lock. `plk_init` fills it at the first use. The platform build
  refuses a `.bss` that ends past the arena reserve's ceiling.
- **Recording.** With a SETUP window open (`0x460d175c`) on the FX1 or
  FX2 page (`0x460d1684` = 3 / 4) and trigs held (`0x460d174a`), stock
  sends a knob turn to the page-1 lock editor `0x400508e4`, which locks
  the page-1 slot behind the window. `plk_edit` takes the turn instead:
  the slot's encoder hook and clamp from its descriptor, stock's edited
  marks (`DB + 0x9b332`, `0x100f8598`, `0x40027e00`), the slot's redraw.
- **Playback**, beside stock's stages: the record builder `0x4009d1e8`'s
  two fill paths (staging or pending slot n), the two staging → pending
  copies, the pending reset, the frame ISR's pending → trig record copy
  and a MIDI note's own record, and the join of the restore and apply
  paths (`0x4000c59e`), which writes the page-2 locks into the lane
  (`0x80000810 + 72t + 50 + j`) and restores the Part's bytes the last
  trig locked. SCENES P2's morph reads the lane as the knob.
- **Operations**: placing a trig, clearing locks, clearing a track or a
  pattern, trig copy and paste, and every memcpy site that moves a
  pattern (`0x8ed8`) or a track (`0x91a`) between the bank RAM, the
  clipboard (`0x460c8122`) and the undo buffer (`0x460bf218`): page 2
  follows in the same shape (two 6,144 B mirrors for the buffers). memcpy
  itself runs before the loader has placed the runtime, so its call sites
  are hooked, not its entry.
- **Files**: `p2lkNN.work` / `p2lkNN.strd` beside `bankNN.*` in the
  project directory, 16 bytes of header (`P2LK`, version 1, bank, length)
  and the bank's 98,304 B. Written where stock writes `bankNN.work`
  (`0x400918aa`), copied where stock copies `.work` ↔ `.strd` (bank store
  and reload, the project store and reload loops), read at the project
  load and the masked bank loads, and emptied for a new project. A missing
  source copies as an empty file.

## Octakit

Built and gated beside Octakit in bottleservice: none of the 50 sites is
one her recipe writes. The masked bank loader `0x400905d4` (her entry
wrapper) is reached through its call sites.
