# STEM REC: crosscheck's flash plan, a record

Carried from `docs/effects/FLASHPLAN.md` on branch `crosscheck` (`7dee174`), which upstream does not have: upstream records flashed images in `CHANGELOG.md`, and this one has not been flashed. Read the old file with `git show 7dee174:docs/effects/FLASHPLAN.md`.

⚠️ **A record, not the plan for this branch.** It builds tag 28 from branch `crosscheck`, and what it says about the emulator is about crosscheck's port, which could not draw the screen; upstream's can (`--lcd`, `--live`). Flash A, piece 4 of the roadmap (`docs/superpowers/specs/2026-09-26-stem-rec-upstream-port-design.md`), gets its own plan on this branch, built from this record.

## Flash 13 — `stems`, tag 28: STEM REC streams T1 to the card (staged 13 Sep 2026, restaged 14 Sep, restaged for streaming 23 Sep)

STEM REC alone (`modules/stems`, `modules/stems/README.md`), so a first
flash can only fail in one module's ways. This is the streaming build: it
writes the take to the card while it records, so a take runs until it's
stopped, up to 60 minutes (STEM_REC.md section 12). Build it from branch
`crosscheck` at the streaming plan's last commit, with
`make image REMIX=stems BUILD=28` → `out/OCTATRACK_OCTABAM28.bin` /
`out/OCTATRACK_OS1.40C_OCTABAM28.syx`. Yves builds it; the hashes are his
to record here. `make check REMIX=stems` and `verify_stems.py --long` (a
20-second take) pass on that branch; every claim below was measured under
the ColdFire port first (`docs/firmware/STEM_REC.md` sections 10 to 12).
Tag 27's images are withdrawn, for the two reasons below. ❌ The 13 Sep image
(`22d98c51…` / `0488b824…`, OS `c3cf29d9…`) is withdrawn: under the port its
15-second take froze the whole unit (STEM_REC.md 11.7). Do not flash it.

❌ **The 14 Sep image above is withdrawn too (22 Sep 2026): it records T3,
not T1.** Its module read T1 from the read-back block's third slot. Stock
puts track k at k × 0x80, so the third slot is T3 (STEM_REC.md 9.2,
corrected; the fixture's NEIGHBOR chain on T2 and T3 had hidden it). The
fix is `T1_OFFSET = 0x00` on branch `crosscheck`. **Rebuild the image from
that branch and take the new hashes before this flash. Do not flash
`e1596682…`.**

⚠️ **Confirm 28 is unused before you copy it.** The last tag flashed in
this series on any branch this clone has fetched is 26 (Flash 12), and 27
was built but withdrawn. If another machine flashed a 28 since, rebuild
with the next free number.

⚠️ **Use a spare card, not a backed-up working card.** Two risks were
accepted for the proof of concept (Yves, 12 Sep 2026). The first still has
a do-not; the streaming build retires the second:

1. The writer task sleeps on the kernel's shared timer, which holds one
   waiter (STEM_REC.md 4.7). **Once STEM REC has been selected since
   power-on, do not run an OS upgrade without a power cycle first.**
2. STEM REC no longer uses the shared staging buffer (STEM_REC.md 12.0).
   Stock's own saves still share it with each other, as in stock.

⚠️ **The STEM REC row may not show.** STEM REC reaches CONTROL the way the
bus screen and MENU SHORTCUT did: count 6 → 7 at `0x400cbd54` and the row
pointer at `+0x18` repointed. That worked on the unit for the bus screen
(tags 85–90), and it failed on tag 16 with the right bytes in the image.
`FAILURE_MODES.md`, "CONTROL menu shows its stock six rows", is still open
🔴 with no known cause. The port tests call STEM REC's action directly and
have never opened the menu. main's copy of that entry says to open CONTROL
in the ColdFire emulator's own menu before any flash that appends rows.
main's port can now draw the screen and take keys (`ot_emu --live`,
18 Sep 2026); this branch's port can't. If the row is missing on the unit,
the flash tests nothing else. (Added 22 Sep 2026, cross-check.)

⚠️ **This image patches a stock card routine.** The stock PIO card write
has a race (STEM_REC.md 11.7): an interrupt at the wrong instruction either
writes a sector twice with no error, or leaves the card handler waiting
forever with the audio frame blocked, which freezes the unit. The first
15-second take under the port hit the freeze. STEM REC patches the routine
(`stems_ata_first`), and that changes every PIO write on the unit, stock
saves included. A card that reports DMA takes the stock DMA path instead,
where the patch never runs; that path is not analysed. Yves chose to ship
the patch in this flash (14 Sep 2026) rather than leave the race in. Test 4
below checks that stock saves still work.

⚠️ **Yves's card takes the DMA path.** The card for this flash is a SanDisk
Extreme 64 GB, UDMA 7. A card that lists any UDMA mode gets the driver's DMA
table (STEM_REC.md 11.7), so on this card the patch never runs. Every take
goes through the stock WRITE DMA path, which the port cannot run. So on this
card, test 4 checks stock saves but not the patch. 🟡 Inferred from the
card's rating: its IDENTIFY data has not been read.
✅ Read 22 Sep 2026 (STEM_REC.md 11.8): the WRITE DMA path has no
counterpart to the PIO race. The hardware moves every sector, one interrupt
ends the command, and transmission errors are retried. A card that refuses
a write does not hang it, but the error may not be reported, so check
test 1's file length. It has still never been run by any emulator.

**How a take behaves.** The take is written to the card while it runs, in
512-frame chunks (about 0.19 s of audio each). At the end, the writer
writes the rest, then each file's real header and exact length. **Wait
at least 5 seconds after the stop before you pull the card or power
off.** The folder isn't a signal: it appears when the take starts. A take
cut off before the end leaves 0-byte files (STEM_REC.md 12.3). Under the
port the end took under 2 ms, but the port's card answers at once; the
5 seconds is a margin, not a measurement. The screen shows nothing, and
STEM REC ignores a select while the end is written. Use a card with
plenty of free space: a full card isn't analysed (FAILURE_MODES.md). If the card falls behind
and the 4 MiB ring fills (about 24 s of T1), the take stops by itself at
the last whole frame. The folder is `YYMMDD-HHMM` from the unit's clock. Under the
port every take is `000000-0000`, because the port's clock reads 0.

**One expectation.** Under the port, T1 sits in the read-back block about
24 dB below its source sample (STEM_REC.md section 9, unexplained). A quiet
take is a known possibility. Record the same pattern with the stock
recorder, resampling T1, and compare the two levels.

The three tests of the spec's section 11, then one for the patch, in order:

1. **Record at least 60 s** with Flex machines only, stopped with STEM
   REC. **Report:** the folder name and the unit's clock, `T1.wav`'s
   length (data bytes = frames × 64), whether it plays whole in a DAW, and
   any dropout heard live. Also the card's make, model and size: whether it
   reports DMA decides which stock write path ran.
2. **The same with a static machine playing.** A static machine streams
   from the card, and the take now writes to the card while it records, so
   the two overlap for the whole take. **Report:** whether the static
   machine's playback glitched during the take, and whether the take is
   intact.
3. **Arm while stopped, then press PLAY.** Then a second take stopped with
   the sequencer's STOP, and a third stopped with STEM REC, each in a new
   minute. **Report:** that the first take starts on the first step, and
   that all three files are there and play. Then select STEM REC twice in
   one minute: the second take must be refused, and the first must stay
   intact.
4. **Stock saves still work.** On this image, after the takes: save the
   project, save a sample (the stock recorder's take from test 1 will do),
   power cycle, and load both back. **Report:** that both saved and both
   load. This is the patch's test: it changes the stock routine those saves
   use on a PIO card.

**Stop conditions.** A hang when STEM REC is selected: power cycle, and
stop the session. A take that never appears while card access stops
working: this is STEM_REC.md 11.4, a card that aborts a write hanging the
stock driver. Power cycle, and do not use that card again for this test.
The whole unit freezing, audio and keys, during or after a take: the race of
STEM_REC.md 11.7, which the patch should prevent. Power cycle, stop the
session, and report the card's make and model. A stock save that fails in
test 4: power cycle, stop the session, and go back to a stock OS for that
card.
Every new failure goes into `docs/remixer/FAILURE_MODES.md`, whose STEM REC
block lists what is predicted, the moment it is seen.

**After the flash:** every result, good and bad, goes into
`docs/firmware/STEM_REC.md` (a new "Hardware" section) and
`FAILURE_MODES.md`, and the Status of `remixes/stems/README.md` is updated.
