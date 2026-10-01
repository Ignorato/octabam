# STEM REC: stems after the fader, MAIN, CUE and the inputs, and 24-bit

Piece 5 of the roadmap in
`docs/superpowers/specs/2026-09-26-stem-rec-upstream-port-design.md`,
section 0, reshaped by Yves on 1 Oct 2026 after flash A. Flash A ran
STEMS1 on Yves's MKII on 30 Sep 2026 (`docs/firmware/STEM_REC.md` section
17.1). Flash B (STEMS2, the stock effects back) is staged in
`modules/stems/FLASH.md`. This piece branches from `stem-rec-p3` at
`343476a` (`stem-rec-p5`).

## 1. Purpose

Flash A recorded eight tracks to the card, and every file played. Three
things are missing for real use:

- **The level.** A stem is the track before its fader. Yves heard it about
  12 dB under the mix. Yves wants a stem to be exactly the track's share of
  MAIN.
- **More sources.** The main mix, the cue mix, and the four inputs.
- **24-bit files.**

## 2. Decisions (Yves, 1 Oct 2026)

| Question | Decision |
|---|---|
| What level should a track's stem have? | After the fader: exactly the track's share of MAIN. That's its post-FX signal × the gain core 0's mix applies to it (LEVEL, MAIN LEVEL, scenes, crossfader, the ramp) × 4, the mix's boost. With the inputs off, the eight stems sum to MAIN. |
| Where do the gains come from? | The frame hook redoes core 0's gain arithmetic from the same inputs the ColdFire sends core 0 each frame. It's proven bit-exact against the DSP's own gains under the port. Rejected: the DSP exports post-fader tracks (C), or exports its gains (C-lite). Both need core 0 code, and the build places DSP code only in stock effects' words today (`docs/firmware/CHIP.md` section 4), so as the build stands either would cost a stock effect. ❌ Corrected 1 Oct 2026: that is a rule of the build, not of the chip. Core 0's code ends at `P:0x1fdf`, 33 words short of `0x2000` (CHIP.md section 2), and no stock code writes there (its only program-memory writes are `P:0x58c`, `P:0x59b`, `P:0x49e` and `P:0x4a2`). C-lite would still need the build to place code in that tail, X memory to stage 128 gains, and a longer transfer on both the DSP and the ColdFire side. A needs none of it. |
| What does "as stock as possible" mean? | No octabam module or setting besides STEM REC. All 14 stock effects stay in the FX2 chooser. |
| 24-bit | One switch, `24 BIT`, for the whole take. Off means 16-bit, as today. |
| New sources | MAIN, CUE, AB, and CD, each on or off. |
| Inputs in stereo or mono | Two switches, `AB STEREO` and `CD STEREO`. On: one stereo file (`AB.wav`). Off: two mono files (`A.wav`, `B.wav`). |
| What does an input file hold? | The raw input, as the stock recorder records INAB and INCD. An input that also plays through a THRU track is in that track's stem too, after its fader. |
| Boot defaults | T1 to T8 on; MAIN, CUE, AB, and CD off; both STEREO switches on; 24 BIT off. Nothing survives a power cycle, as today. |
| A layout faster than the card | No automatic limit. The take stops with `RING FULL` and its files hold everything up to that point, as today. |
| The ring's size | 8 MiB, up from 4, inside the platform's fixed 10 MiB reserve, so it costs no sample memory. ⚠️ The roadmap asked this piece to leave room in the reserve for other DRAM modules. The `stems` remix carries none, and a combined image would need a smaller ring; the build refuses a reserve that overflows. |
| Deferred | A status that ticks by itself, and a key that arms a take. |

## 3. What you see

**The files.** Up to 14 per take, in the take's folder
(`<set>/AUDIO/YYMMDD-HHMM/`):

| Source | File | What it holds |
|---|---|---|
| T1 to T8 | `T1.wav` to `T8.wav`, stereo | The track after its fader: its share of MAIN |
| MAIN | `MAIN.wav`, stereo | The main mix, as the stock recorder's MAIN source records it |
| CUE | `CUE.wav`, stereo | The cue mix, as the stock recorder's CUE source records it |
| AB | `AB.wav`, stereo; or `A.wav` and `B.wav`, mono | The raw inputs A and B, as the stock recorder's INAB records them |
| CD | `CD.wav`, stereo; or `C.wav` and `D.wav`, mono | The raw inputs C and D, likewise |

Every file of a take has the same width, 16 or 24 bits, as PCM WAV. The
Octatrack plays both widths, mono and stereo.

**The STEMS list.** 18 rows; the screen shows seven and scrolls.

| Row | Shows | ENTER |
|---|---|---|
| 1 | `REC`, `CANCEL`, `STOP` or `SAVING` | As today |
| 2 | The status | None: the cursor skips it |
| 3-10 | `T1 [X]` to `T8 [X]` | Turns the track on or off |
| 11-14 | `MAIN [ ]`, `CUE [ ]`, `AB [ ]`, `CD [ ]` | Turns the source on or off |
| 15-16 | `AB STEREO [X]`, `CD STEREO [X]` | Switches stereo and mono |
| 17 | `24 BIT [ ]` | Switches 24-bit and 16-bit |
| 18 | `PEAK n%` | None: the last row, never reached |

**The rules.**

- At least one source stays on. Turning off the last one does nothing, as
  T8 stays on today when every other track is off.
- Every row from 3 to 17 works while idle or armed, and is locked from the
  first recorded frame until the take is saved.
- The STEREO rows always switch. They take effect only while their source
  is on.
- The exact texts are settled by the menu gate's width check: every text
  ends inside the pane, which clips at x = 118. Shorter forms are ready
  (`AB ST [X]`, `24B [ ]`).

**Data rates and the ring.** One stereo file at 16 bits is 176,400 B/s,
at 24 bits 264,600 B/s; a mono file half that.

| Layout | Rate | 4 MiB ring | 8 MiB ring |
|---|---|---|---|
| Eight tracks, 16-bit | 1.41 MB/s | 3.0 s | 5.9 s |
| Eight tracks, 24-bit | 2.12 MB/s | 2.0 s | 4.0 s |
| Everything, 24-bit (12 stereo files) | 3.18 MB/s | 1.3 s | 2.6 s |

The ring column is how long a card stall can last before `RING FULL`.
OctaLab measured card writes that stall for up to 1.2 s while STATIC
tracks play, and 1.4 to 2.1 MB/s while they read
(`docs/proposals/OTX_PROJECT_PROPOSAL.md`). The ring can't raise the
card's sustained speed; flash B's sweep measures Yves's card.

## 4. How it's built

### 4.1 Every frame

A frame is 16 samples, about 0.36 ms.

1. Stock, unchanged: both DSP cores render their tracks, and each track's
   post-FX signal before its fader reaches the read-back block
   (`0x80003190`). Core 0 mixes: for each sample it ramps each track's
   MAIN gain (`Y:0x4a + 20j + k`), multiplies, sums, and shifts left by
   two (`docs/firmware/DSP.md`, "Core 0's frame"). Channel 6 carries MAIN
   and CUE to `0x80005e60`; channel 7 carries the inputs to the ColdFire.
2. New, in the frame hook: it computes the same gains, multiplies each
   enabled track by them, and copies MAIN, CUE and the inputs, all into
   the ring.
3. The writer task streams the ring to the card, one file per source.

No DSP code changes.

### 4.2 The gain model

Each frame the ColdFire sends core 0 the inputs of its gain calculation:
three 16-bit words per slot (eight tracks and two inputs) through
`X:$205`, and the MAIN and CUE levels. Core 0 scales them, squares them,
scales them by its tables at `X:0x6c00`, applies the master square, and ramps from the slot's state at
`X:0x3dd + 5k` over the 16 samples (`P:0xf5`-`0x165`, `P:0x203`-`0x237`).

The hook reads the same words where the ColdFire keeps them, and repeats
that arithmetic in the same order, with the DSP's widths and rounding. It
keeps its own copy of each slot's ramp state. It runs the model every frame
while armed, so the first recorded frame starts in step. If the code shows
the state needs more history than one armed frame gives, the model runs
every frame from boot instead, and its cost is measured in IDLE too.

The plan reads the code before writing any (section 5). A stem is then
`4 × g × x`, clipped at 24-bit full scale: `g` the model's gain for that
sample, `x` the tap's sample from the frame the mix uses.

### 4.3 The hook

While recording, per frame:

1. Run the gain model.
2. For each enabled track: each sample, left and right, is the stem above,
   from the tap frame the plan measures as the one core 0 mixes.
3. MAIN and CUE: copy their 16 samples from `0x80005e60` (`+0x00`,
   `+0x80`).
4. AB and CD: copy their 16 samples from where the stock recorder reads
   them. A mono layout splits a pair into two files.
5. Write every enabled source into the ring in file order, at the take's
   width: 16 bits as the top 16 of the 24, or all 24.

At the start edge the hook latches a source mask (T1-T8, MAIN, CUE, AB,
CD) and a format (24 BIT, AB STEREO, CD STEREO), and from them each file's
bytes per frame and the ring frame's size. This replaces today's track
mask and its table of ring sizes.

### 4.4 The ring and the writer

- The ring is one 8 MiB `DramRegion`. A ring frame holds every enabled
  file's 16 samples, in file order.
- The writer takes each file's bytes from a ring frame, turns them into
  WAV's little-endian order, and streams them as today. It handles up to
  14 files; its handle, length and position tables and its stream buffers
  grow to match.
- Each header carries its file's channel count and width.

### 4.5 The menu

Rows 11 to 17 join the list in `stems.s`, with labels STEM REC rewrites as
it does the track rows. The track action generalises to a source action
(rows 3-14) and a switch action (rows 15-17). The list descriptor's count
becomes 18. MAIN MENU's root and every other category stay as they are.

### 4.6 Cost

The hook runs 743 instructions per frame at eight tracks today
(`STEM_REC.md` 15.3). The estimate for everything at 24 bits is 3,000 to
4,000. The ceiling is 5,000 per frame. At one cycle each that's about 5%
of a frame's 95,800 CPU cycles; memory waits make it more. Above it, the multiply moves into the writer task, and the plan
says what that costs the ring.

## 5. Probes first

Before any feature code, each measured under the port and written into
`STEM_REC.md`:

1. **The gain inputs.** Where the ColdFire builds the words core 0 reads
   through `X:$205`, and the MAIN and CUE levels; whether scenes and the
   crossfader are already in them. Method: the transfer routine's DMA
   sources (`DSP.md` 6c), then a write watch.
2. **The gain code.** `P:0xf5`-`0x165` and `P:0x203`-`0x237` read in
   full: every instruction, its width and rounding, the ramp's state, and
   when a ramp reaches its target.
3. **The frame offset.** Which read-back frame core 0 mixes in the frame a
   gain belongs to. Method: a LEVEL step, the DSP's gains read per frame,
   and the tap.
4. **The inputs.** Where the stock recorder reads INAB and INCD, their
   format, and which slot is A, B, C and D. Method: the recorder's source
   setup before `0x400068e4`, then `--audio-in` with one live channel per
   run.
5. **MAIN and CUE in the hook.** That `0x80005e60` holds the frame the
   hook believes it does when the hook runs.
6. **MASTER TRACK.** Which gains the master path uses for T1 to T7. The
   stems follow them, or the docs say what a stem holds in that mode.
7. **The texts.** The new labels' widths.

**Stop condition.** If probe 1 or 2 shows the gains can't be made
bit-exact on the ColdFire, the work stops there. Yves chooses between
C-lite with one stock effect given up and approximate gains with the
error measured.

## 6. The checks

Gates under the port, in `tools/verify/verify_stems.py` or a gate of its
own declared in the manifest, all run by `make check REMIX=stems`:

1. **The gains are exact.** The hook's gains (a test seam: the last
   frame's 128 values) equal the DSP's `Y:0x4a + 20j + k`, read with the
   port's DSP peek after the ramp, bit for bit. In every frame of a run
   with LEVEL steps, a MAIN LEVEL change, a crossfader sweep and a scene
   change, from a take armed while stopped and one started while
   playing.
2. **The stems sum to MAIN.** Inputs off: each track alone, then all
   eight; the sum of the stems equals the port's MAIN capture within one
   24-bit step per sounding track, plus one.
3. **The alignment.** A LEVEL step during a take reaches the stem on the
   same sample as MAIN.
4. **The sources.** `MAIN.wav` and `CUE.wav` equal the port's captures
   sample for sample. The inputs, fed a known WAV through the port's
   audio input, equal the stock recorder's INAB and INCD, in stereo and in
   mono.
5. **The formats.** A 24-bit take keeps all 24 bits; the same signal at
   16 bits is its top 16. Mono files have one channel. Every header
   matches its data.
6. **The menu** (`verify_stems_menu.py`, MKII and MKI): the new rows, the
   last source kept, every row locked while recording, the boot defaults,
   every text inside the pane.
7. **The cost.** At most 5,000 hook instructions per frame, everything on
   at 24 bits (the coverage method of `STEM_REC.md` 10.0).
8. **Nothing that passes today breaks:** the eight-track THRU takes,
   overflow, FAT32, the card-speed sweep, the static checks.

**What the port can't show**, for flash C's checklist: the card's speed
with more files; a null test on the unit (the stock recorder's MAIN minus
the sum of the stems, near silence in a DAW); real inputs, mono and
stereo.

## 7. The records

- `docs/firmware/STEM_REC.md`: a section per probe, then the gates' runs.
- `docs/firmware/DSP.md`: the gain path as read, for any module to use.
- `modules/stems/README.md` ("How to use it", "Limits"),
  `remixes/stems/README.md`, and the manifest's `doc`: the sources, the
  formats, after the fader.
- `modules/stems/FLASH.md`: flash C, with STEMS3.
- `CHANGELOG.md`, Unreleased.

## 8. Rules

- Every value that moves is a finding: re-measured, explained, written
  down, never loosened to pass.
- Every gate runs on a committed tree, and its log's first line shows it.
- The bare-metal `m68k-elf` toolchain (binutils 2.47, GCC 16.1.0).
- No Elektron byte in the repository.
- Separate commits per finding. Nothing is pushed.

## 9. Risks

- **The gains may not replicate exactly.** Guarded by the probes and the
  stop condition.
- **More work in the audio interrupt.** Guarded by gate 7's ceiling.
- **MAIN and CUE are single-buffered.** Channel 6 rewrites them every
  frame; read at the wrong moment they give the previous or next frame.
  Probe 5.
- **The port runs both cores and the ColdFire in lock-step.** It can't
  show a timing race or the card's real speed. Flash C.
- **The ramp state starts from nothing.** A take started while playing
  arms for one frame only; probe 2 says whether that's enough.
- **The reserve.** An 8 MiB ring and 14 stream buffers use about 9 MiB of
  the 10 MiB reserve, leaving little for another DRAM module in a combined
  image.
- **14 open files.** Within the stock file system's 511 handles; a take's
  open and close times grow, measured in the take runs.

## 10. Done when

- Probes 1-7 are measured and written down, and the gain model is
  bit-exact under gate 1.
- Every gate in section 6 passes on a committed tree, on both panels.
- `make reach` against upstream `main` lists the gates, and they pass.
- The records in section 7 are written, and STEMS3 is built with flash C's
  checklist.

## 11. Not in this piece

A status that ticks by itself, a key that arms a take, a PRE/POST switch
for the stems (Yves, 1 Oct 2026: next, after this piece; piece 3's copy is
the pre-fader path and this piece adds the post-fader one), the file length
set every few chunks (the roadmap's piece 5), seconds in the folder name,
saved settings, a speed limit by layout, a screen of its own, and any pull
request.
