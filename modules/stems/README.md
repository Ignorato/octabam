# STEM REC

MAIN MENU › CONTROL › STEM REC records tracks to the card while the
sequencer plays. It writes the take while it records, so a take can run
until you stop it, up to 60 minutes. Each track lands as its own file,
`<set>/AUDIO/YYMMDD-HHMM/T<n>.wav`, 16-bit stereo at 44,100 Hz. This build
records T1 only. The code handles all eight tracks. The port has run
eight tracks in one short take; the ring's limit and its wrap have run at
T1 only. It's a step of `docs/proposals/MULTITRACK_TO_CARD.md`.

- The design: `docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md`,
  over the proof of concept's `docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md`.
- Every stock address the module uses, with its evidence:
  `docs/firmware/STEM_REC.md`. Section 12 covers streaming.
- The remix: `stems`, STEM REC alone. `make image REMIX=stems` builds it.

## Status

**Measured under the ColdFire port, unflashed.** The port is the project's
emulator of the unit's main processor. `tools/verify/verify_stems.py`, part
of `make check REMIX=stems`, runs the module on fixture projects. It reads
each take back off the port's card and checks the header, the sizes, and
every sample. Every sample equals its track's post-FX2 read-back block at
a fixed lag. The read-back block is where the unit's audio processor hands
each track's finished audio back to the main processor. The runs cover:

- A take stopped by STEM REC, by the sequencer, and by the 60-minute cap.
- A take long enough that the writer writes while it records.
- A take across the ring's wrap, with the take's sound on both sides.
- A ring that fills because the card falls behind.
- Eight tracks, eight files, each equal to its own track.
- A card that refuses a write: the run records that the writer hangs.
- A take cut off mid-way: the run records that its file is empty.

Under the port the fixture's sounds play only their first four frames, so
most of each take is silence. A lost or repeated sector in a silent
stretch wouldn't show. The first flash's 60-second take (FLASH.md) is the
first test with sound throughout.

`--long` adds a 20-second take whose file must equal the ring byte for
byte. It takes about 20 minutes and stays outside `make check`.

| Measured under the port | Value | STEM_REC.md |
|---|---|---|
| The frame hook, IDLE | 2 instructions per frame | 10.2 |
| The frame hook, ARMED | 17 instructions per frame | 10.2 |
| The frame hook, recording T1 | 130 instructions per frame | 12.2 |
| The frame hook, recording eight tracks | 739 instructions per frame | 12.2 |
| The writer task's stack peak | 1,052 of 8,192 bytes | 12.2 |

The IDLE and ARMED figures come from the proof-of-concept build. Those two
paths are unchanged in the source. The hook's figures are instruction
counts. Its time on the unit isn't measured.

Known from the port, before any flash:

- **Every port take is named `000000-0000`**, because the port's clock
  reads 0. The name comes from the unit's own clock, and the order of its
  fields is first checked on the unit (STEM_REC.md 11.2).
- **T1 sits about 24 dB below its source sample** in the read-back block
  under the port, unexplained (STEM_REC.md section 9). A quiet take is a
  known possibility.
- **A card that refuses a write command hangs the writer** inside the stock
  card driver, which has no timeout. Recovery is a power cycle. The stock
  sample save shares this (STEM_REC.md 11.4).
- **The stock PIO card write has a race, and the module fixes it.** PIO is
  the mode where the processor copies each sector to the card itself. An
  interrupt could land between the stock routine sending a write's first
  sector and updating the card handler's pointer and count. The handler
  then either waited forever with the frame interrupt blocked, or wrote a
  sector twice without an error. The module patches the stock routine to
  update both first (STEM_REC.md 11.7). The patch changes every PIO card
  write, not only STEM REC's. A card that reports DMA takes a different
  stock path, where the patch never runs.

## How to use it

1. Open MAIN MENU › CONTROL and select **STEM REC**.
   - If the sequencer is stopped, STEM REC arms. Recording starts on the
     first frame the sequencer plays.
   - If the sequencer is running, recording starts at once.
2. The take stops when the sequencer stops, when you select STEM REC
   again, or after 60 minutes. Selecting it while armed cancels the arm.
3. The writer finishes the files a moment after the stop: it writes the
   last audio, then each file's real header and exact length. **Wait at
   least 5 seconds after the stop before you pull the card or power off.**
   The folder isn't a signal: it appears when the take starts.

The screen shows nothing. You know a take worked when its files open with
the right length.

## Limits

- One build-time set of tracks: T1 in this build. There's no menu to pick
  tracks.
- 16-bit, at most 60 minutes.
- No screen feedback, and no error report on the unit.
- The name has no seconds. A second take in the same minute is refused, and
  the first stays intact.
- If the card falls behind and the 4 MiB ring fills, the take stops by
  itself at the last whole frame. Its files still play. A slow or nearly
  full card is the likely cause.
- A power cut or a card pull before the end loses the take: each file is
  left at 0 bytes, because its length is set only at the end
  (STEM_REC.md 12.3).
- A nearly full card isn't analysed. Leave room: a T1 take needs about
  10.6 MB a minute.
- Loading a project while recording isn't detected. Don't do it.
- One risk accepted for the proof of concept (Yves, 12 Sep 2026): the
  writer task sleeps on a shared timer that holds one waiter (STEM_REC.md
  4.7). Once STEM REC has been selected since power-on, don't run an OS
  upgrade until you've power cycled.

The proof of concept also warned against saving or loading while a take
was written, because it wrote through the file layer's shared staging
buffer (STEM_REC.md 7.5 and 7.5a). This build doesn't use that buffer, so
the warning no longer applies to STEM REC. Stock's own saves still share
it with each other, as in stock.

## How it works

- **The frame hook.** A detour at the per-frame routine's only call site,
  `0x40004b12`, in the audio interrupt. When a take starts, it latches the
  track mask, `stems_tracks`. Then, each frame, it copies each enabled
  track's 16 stereo samples from the read-back block into a 4 MiB ring,
  keeping the top 16 bits of each 24-bit sample. The ring holds whole
  frames of 64 bytes per track. It calls nothing and uses no RTOS service.
- **The writer task.** The module's own RTOS task at priority 1, created
  the first time STEM REC is selected. It wakes every 10 ms. At a take's
  start it names the take from the clock, creates the folder, refuses a
  folder that exists, and opens one file per track. While recording, it
  moves the ring into each file in 512-frame chunks. At the end it writes
  the rest, rewrites each file's first sector with the real header, sets
  the exact length, and closes.
- **The raw file routines.** The writer calls the file layer's own
  sector-level routines, from its own buffers, and never the buffered API
  (STEM_REC.md 12.1). The processor reaches those buffers only through the
  uncached address alias, so a card DMA reads what was written (11.8).
- **The first-sector fix.** A detour in the stock PIO write routine at
  `0x40014cfe`. It advances the card handler's data pointer and sector
  count before the first sector goes out, not after, so a card interrupt
  can never find them stale (STEM_REC.md 11.7).
- **The memory.** The ring, the task's 8 KB stack, and the writer's
  buffers are DRAM regions at the free top of the platform's arena
  reserve. So the module costs no sample memory beyond what any DRAM remix
  already gives up.

No module upstream hooks the frame site or rewrites the CONTROL list (27 Sep
2026). The ledger refuses one that does, by name.
