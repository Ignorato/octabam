# STEM REC on current upstream: the port

Piece 1 of 5. The others, in order: eight tracks and 24-bit in the
recorder; the STEM REC category in MAIN MENU; the flash; later, a custom
recording window. Each gets its own spec and plan.

## 1. Purpose

Carry STEM REC, and the tool support it depends on, from branch
`crosscheck` (`7dee174`) onto current upstream `main` (`81126f7`,
sambanks/octabam), with no change in what it does. Pieces 2 to 4 then
build on upstream's emulator, which can show the screen (`--lcd`), take
panel keys (`--live`), boot as an MKII (`--mkii`) and run a clock
(`--rtc`). `crosscheck` split from upstream on 9 Sep 2026 and lacks 788
upstream commits.

The work happens on branch `stem-rec-v2`, cut from `main`. `crosscheck`
stays as it is.

## 2. What moves

`crosscheck` adds 34 files over its split point. They fall into five
groups.

| Group | Files | Upstream today |
|---|---|---|
| The module | `modules/stems/` (`stems.s`, `manifest.py`, `README.md`), `remixes/stems.py` | absent |
| Build support | `tools/remix/schema.py` (`DramRegion`), `platform_build.py`, `ledger.py` (a hook site registered even when its cave floats), `tools/build/build_bus.py`; and a general fix, `prereq.py` with its callers `selftest.py`, `verify_octakit.py` and `verify_replaces.py` (skip, by name, a remix this machine can't build), kept only if upstream still lacks it, `Makefile`, `.gitignore`, `scripts/refhash.sh` | no `DramRegion`; `ArenaReserve` only |
| The emulator | `tools/emu/ot_emu/main.cpp`: `--call-before-play` (several calls, each run from main's spin), `--at FRAME:ADDR:ARG` (several), `--poke-before-play`; `card.h`/`card.cpp`: `--card-fail-after` | has `--card-out`, `--poke`, `--poke-early`, one `--call` and `--call-at`; none of ours |
| The card reader and the fixture | `tools/emu/emu_card.py` (`read_file`, `list_dir`), `tools/verify/verify_card_reader.py`, `tools/verify/stems_fixture.py` | has `stage_project` (moved into `emu_card.py`) and `extract_image`; `emu_rtos.py`, which the fixture used, is deleted |
| The verifier and the docs | `tools/verify/verify_stems.py`; `docs/firmware/STEM_REC.md`, `CROSSCHECK.md`; the STEM REC parts of `FAILURE_MODES.md`, `FLASHPLAN.md` (Flash 13) and `PLAN.md` (item 8); `docs/superpowers/specs/` and `plans/` for STEM REC; `docs/proposals/`, `docs/WSL.md` | absent, or upstream's own version |

## 3. How

- **Apply, don't merge.** Each group is brought across as its own commit,
  by cherry-pick where the commit still applies, and otherwise by
  re-applying the change by hand against upstream's current code.
- **Upstream's version wins where it does the same job.** Our additions go
  in beside it, not over it:
  - `--card-out` exists upstream; ours is dropped.
  - The fixture stages its card with upstream's `emu_card.stage_project`.
  - `read_file` and `list_dir` stay only if `extract_image` can't serve
    the verifier.
  - Our three calling and poking flags are kept: upstream's single
    `--call` can't make the several calls before play and the calls at
    chosen frames that the verifier makes.
- **`stems.s` moves byte for byte.** Its md5 on `stem-rec-v2` equals its
  md5 at `7dee174`. The port changes no module behavior.
- **A general fix found on the way goes in as its own commit,** named as
  such, so it can go upstream on its own.

## 4. Rules the port must keep

- **A build change proves it changed nothing.** Before the first build
  change, `scripts/refhash.sh save` on `main`. After the build-support
  commits, `scripts/refhash.sh check`: every configuration's artifacts and
  build reports bit-identical. A report line that differs only because a
  tool path changed is shown identical in its artifacts before a re-save.
- **The emulator change is additive.** Every existing flag keeps its
  meaning and its report text. A run without the new flags prints what it
  printed before.
- **No new behavior.** Nothing in pieces 2 to 5 lands here.

## 5. Risks, and how each is handled

- **Upstream's emulator changed under the tests.** Since 9 Sep it merged
  another author's port changes, retired the old RTOS route, and changed
  DSP scheduling defaults. The verifier pins exact values: the take's lag
  (40 frames), the poke landing about 26 frames into play, 23 sectors on
  the refused card, the hook's instruction counts. Each value that moves
  is a finding: re-measured, explained, and written down, never loosened
  to pass.
- **The fixture depends on a deleted module.** `stems_fixture.py` staged
  its card through `emu_rtos.stage_project`. Upstream's
  `emu_card.stage_project` takes other arguments. The fixture is rebuilt
  on it, and the tap check proves T1 is still the only core-1 track that
  sounds.
- **`make check` for other remixes.** The ledger and selftest changes
  touch every remix. `make check` for `bamsep26` and for `stems`, and the
  selftest over every remix, must pass.

## 6. Done when

- `stem-rec-v2` carries STEM REC, with `stems.s` byte-identical to
  `7dee174`.
- `scripts/refhash.sh check` passes against the `main` baseline.
- `make check REMIX=stems` exits 0.
- `python3 tools/verify/verify_stems.py stems` passes every check (93 on
  `crosscheck`), and `--long` passes its 20-second take.
- `REMIX=stems python3 tools/verify/verify_dram_boot.py` passes.
- `make check` passes for upstream's default remix, `bamsep26`, too.
- Every value the verifier pins that moved is written down in
  `STEM_REC.md`, with its cause.

## 7. Not in this piece

The menu, eight tracks by default, 24-bit, the image for the flash, and
any pull request to upstream. The pull request waits until you decide.
