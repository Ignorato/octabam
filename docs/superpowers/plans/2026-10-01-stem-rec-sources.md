# STEM REC: stems after the fader, MAIN, CUE and the inputs, and 24-bit — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each track's stem becomes exactly its share of MAIN (bit-exact under the port), a take can also record MAIN, CUE and the inputs (AB and CD, stereo or mono), every file can be 24-bit, and the ring grows to 8 MiB, all from MAIN MENU › STEMS.

**Architecture:** No DSP code changes. The frame hook mirrors core 0's MAIN-gain arithmetic from the level words the ColdFire hands the DSP each frame (a 5-page ring at `0x80005460`), keeping the ramp state in step with the DSP from the first page. While recording it multiplies each enabled track's read-back samples by those gains on the ColdFire's EMAC, copies MAIN, CUE and the inputs from channel 6's buffer (`0x80005e60`), and writes every source into the ring big-endian at the take's width, from a file table latched at the start. The writer task turns each file's bytes little-endian and streams them as today. A Python reference model of the gain path is proven against core 0's own memory before any assembly is written.

**Tech Stack:** m68k assembly (`modules/stems/stems.s`, GNU as `-mcpu=54455`, bare-metal `m68k-elf` binutils 2.47), Python 3 (the model, the verifiers, the fixture builder), the ColdFire port `ot_emu` (unchanged), WSL2 Ubuntu.

**Spec:** `docs/superpowers/specs/2026-10-01-stem-rec-sources-design.md`

## Global Constraints

- "No DSP code changes." "All 14 stock effects stay in the FX2 chooser."
- "Every value that moves is a finding: re-measured, explained, written down, never loosened to pass."
- "Every gate runs on a committed tree, and its log's first line shows it."
- "The bare-metal `m68k-elf` toolchain (binutils 2.47, GCC 16.1.0)."
- "No Elektron byte in the repository." The gain table is read from the user's image at run time (`0x400ea18a`), never copied into the source.
- "Separate commits per finding. Nothing is pushed." Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Files: `T1.wav`…`T8.wav`, `MAIN.wav`, `CUE.wav`, `AB.wav` or `A.wav` + `B.wav`, `CD.wav` or `C.wav` + `D.wav`; 16 or 24 bits, PCM WAV, 44,100 Hz.
- Boot defaults: T1 to T8 on; MAIN, CUE, AB, CD off; AB STEREO and CD STEREO on; 24 BIT off.
- Every file of a take is sample-aligned: sample *i* of every file is the same moment, so the stems sum to MAIN.
- "At least one source stays on." Rows 3 to 17 are locked from the first recorded frame until the take is saved.
- The ring is 8 MiB. The hook's ceiling is 5,000 instructions per frame with everything on at 24 bits.
- **Stop condition (spec section 5):** if Task 3's model can't reproduce core 0's gains exactly, or Task 5's mirror can't match core 0's ramp state, stop and ask Yves (C-lite with one stock effect given up, or approximate gains with the error measured).
- Prose follows the Microsoft Writing Style Guide. Counts from logs go through a script file, never an inline `$(grep -c)` through `wsl.exe`.

## Review Focus

These five inputs follow from the spec, and no gate in its section 6 names them. Each line names the task that adds its test.

1. **A take started while a fader is moving.** Expected: the stems match MAIN from the first recorded frame, because the mirror tracked the ramp before the take. Test: Task 6's `postmove` starts the take (REC while playing) two frames before a LEVEL step.
2. **A hot track at full LEVEL and MAIN LEVEL.** Expected: the stem clips at full scale exactly where MAIN does. Test: Task 6's `clip` runs T1 at LEVEL 127 with the MAIN level at 127 on a full-scale input; every clipped sample of `T1.wav` equals MAIN's.
3. **Every source off.** Expected: the last source that's on stays on (T8 when only tracks were on; MAIN when only MAIN was). Test: Task 10's gate turns sources off in turn.
4. **All 14 files in one take.** Expected: 14 files, each with its own header (channels, width) and a length that matches its frames. Test: Task 8's `all14`, and Task 9's `all14w`.
5. **MASTER TRACK on.** Expected: what Task 4 measures, written down; no crash and no misaligned file. Test: Task 4 Step 5 and Task 6's `master`.

---

## Conventions

- **Trees.** Git work in the worktree `.claude/worktrees/stem-rec-p5` (branch `stem-rec-p5`). Builds and runs in the WSL worktree `/home/yvez/stemrec5` of the clone `/home/yvez/stemrec2`, made in Task 1. Sync with `bash .superpowers/v2/sync-p5.sh`; run with `bash .superpowers/v2/wslrun-5 NAME CMD...`, which logs to `/home/yvez/xcheck/v5-NAME.log` with the HEAD and the dirty count on its first line. Tell Yves each long run's log path when it starts. One heavy WSL job at a time (the VM has 3.8 GB).
- **`VS`** below stands for `env STEMS_TEMPLATE="/home/yvez/stemrec5/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems.py stems`, so a quick run reads `bash .superpowers/v2/wslrun-5 NAME VS --only=a,b` with `VS` spelled out.
- **Commits.** Stage by name; check `git status --porcelain` shows only the intended files staged before each commit.
- **Assembly.** `-mcpu=54455`. ColdFire instructions are at most six bytes, so an immediate can't be stored to an absolute address in one instruction: load it into a register first. `divu.l`, `mulu.l` and `muls.l` take a register, never an immediate. `movem` has no `-(sp)` or `(sp)+` form: use `lea -N(%sp),%sp` then `movem.l regs,(%sp)`, and the reverse. After any EMAC instruction or other unusual form: build, then disassemble the built routine (`scripts/disasm.sh emac ADDR N`, the address from `m68k-elf-nm out/platform/runtime/runtime.elf`) and compare it with the intent (AGENTS.md: "Disassemble what you assemble"). Use only EMAC forms the stock image runs (Task 5 Step 1), never MAC-with-load.
- **The ledger.** `.superpowers/sdd/2026-10-01-stem-rec-sources/progress.md` (local, excluded): one line per finding and ruling, with the log that shows it.

## Measured before this plan (1 Oct 2026, `/home/yvez/stemrec3` at `14ea124`, the `stems` image)

The code below is written against these facts. Task 2 re-measures each one and writes it into `docs/firmware/STEM_REC.md` section 18.

- **The level pages.** The ColdFire writes the words core 0 reads through `X:$205` into a ring of five 0x80-byte pages at `0x80005460`. `0x4000ac18`: the page written this frame is `0x80005460 + [0x80004800] << 7`. `0x400049da`: channel 0's source is `0x80005460 + [0x80004804] << 7`. The sent index cycles 1, 2, 3, 4, 0 and is written twice a frame (once per core's transfer). Per slot k = 0..9 (T1..T8, then inputs AB and CD), four halfwords at byte `8k`: w0 (cue send), w1 (level), w2 (MAIN table index), w3 (split sample, low 4 bits); then the cue level at halfword `0x28` and the MAIN level at halfword `0x29`. On the one-track fixture: `0000 7f00 7f00 0000` for T1-T4 and T7-T8, `0000 0000 7f00 0000` for T5-T6 (LEVEL 0), `0040 0040` at `0x28`/`0x29` (`--main-level 64`). In the DSP (`X:0x4800`) each word arrives with `0x03` in its top byte. Under the port the pages are written only from the frames phase (sample 520,504 on the THRU fixture, about 190 halfword writes a frame, mostly from `0x4000cb6a`).
- **The gain path** (payload A, `out/dsp/payload_A.asm`): `P:0xf5`-`0x10a` scale and square; `P:0x10b`-`0x165` the targets (`P:0x113` the MASTER TRACK branch); `P:0x203`-`0x237` the ramp; `P:0x259`-`0x28f` the mixdown. MAIN target of slot k = `lim(mpy(w1sq, lim(mpy(M2, T[idx]))))`, with `w1sq = lim(mpy(x, x))`, `x = sext24(w1 << 8)`, `M2 = lim(mpy(m, m))`, `m = sext24((W29 & 0xff) << 16)`, `idx = sext24(w2 << 8) >> 15`, `T = X:0x6c00 + idx`, and `mpy(a, b) = floor(a·b / 2^23)`.
- **The ramp.** State per slot at `X:0x3dd + 5k`: split, cue increment, MAIN increment, cue gain, MAIN gain. Per frame with the page's split s: m = min(s, last split); samples 0..m-1 continue the old ramp; m..s-1 hold; s..15 ramp by `lim((target - gain) >> 4)` per sample. Measured: target `0x1f7fe3`, settled gain `0x1f7fe0` (the floor leaves up to 15 LSB).
- **The ramp state starts at zero.** Payload A uploads 50 zero words at `X:0x3dd` at boot. `X:0x4800`/`0x2800` (the level banks) are not in the upload: on a unit they hold whatever RAM held until the first page.
- **The table.** `X:0x6c00` holds `T[0..257]`, a quarter sine (`T[254] = 0x7ffd87`, `T[256] = 0x7fffff`, not exactly `round(sin)`); its words are at `0x400ea18a` in the running image, 3 bytes each, little-endian.
- **MAIN reaches the port's TX0** on the one-track FLEX fixture (64 samples) and on the THRU fixture (ring words 2 and 3). The per-sample MAIN gains are `Y:0x4a + 20j + k` (j = sample, k = slot); the mixdown is `lim(floor(Σ g·x / 2^21))`. The port README's open item "no track's dry audio reaches TX0" watched `Y:0x40`, which is the cue bus's gain, 0 for a track not cued.

---

### Task 1: The piece-5 trees

**Files:**
- Create (local, excluded): `.superpowers/v2/wsl-p5-wt.sh`, `.superpowers/v2/sync-p5.sh`, `.superpowers/v2/wsl-sync-p5.sh`, `.superpowers/v2/run-5.sh`, `.superpowers/v2/wslrun-5`, `.superpowers/sdd/2026-10-01-stem-rec-sources/progress.md`

**Interfaces:**
- Produces: the WSL worktree `/home/yvez/stemrec5` on branch `stem-rec-p5`, its port, the fixtures; `wslrun-5`.

- [ ] **Step 1: The WSL worktree**

`.superpowers/v2/wsl-p5-wt.sh`:
```bash
#!/bin/bash
# Runs inside WSL (1 Oct 2026): the worktree /home/yvez/stemrec5 of the
# stemrec2 clone for STEM REC piece 5 (branch stem-rec-p5), AGENTS.md's
# recipe. tools/emu is unchanged since stemrec3's port was built, so the
# port binary is copied rather than rebuilt (one heavy job at a time).
set -euo pipefail
SRC=/home/yvez/stemrec2
WT=/home/yvez/stemrec5
cd "$SRC"
git fetch -q origin stem-rec-p5
if [ -d "$WT" ]; then git -C "$WT" checkout -q --detach FETCH_HEAD
else git worktree add -q --detach "$WT" FETCH_HEAD; fi
cd "$WT"
for d in vendor .venv; do [ -e "$d" ] || ln -s "$SRC/$d" "$d"; done
[ -e downloads ] || ln -s /home/yvez/stemrec3/downloads downloads
EX="$(git rev-parse --git-common-dir)/info/exclude"
grep -qx downloads "$EX" || echo downloads >> "$EX"
mkdir -p out/raw out/projects out/emu
cp --update=none "$SRC/out/raw/section_3_MAIN_OS.bin" out/raw/
[ -d "out/projects/Ultimate FX 1.5.3" ] || cp -r "$SRC/out/projects/Ultimate FX 1.5.3" out/projects/
git submodule update --init --recursive -q
test -z "$(git diff --name-only 7625c796 HEAD -- tools/emu)" || { echo "tools/emu changed: build the port"; exit 1; }
cp /home/yvez/stemrec3/out/emu/ot_emu out/emu/ot_emu
sha256sum out/emu/ot_emu /home/yvez/stemrec3/out/emu/ot_emu out/raw/section_3_MAIN_OS.bin
echo "stemrec5: HEAD $(git rev-parse --short HEAD), $(git status --porcelain | wc -l) file(s) differ"
```
Run: `MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash -c "tr -d '\r' < /mnt/c/Projects/Octabam/.superpowers/v2/wsl-p5-wt.sh > /tmp/wsl-p5-wt.sh && bash /tmp/wsl-p5-wt.sh"`
Expected: two equal port hashes, the stock slice `164f3122…af0a84e`, and `stemrec5: HEAD <stem-rec-p5's>, 0 file(s) differ`.

- [ ] **Step 2: The sync and run scripts**

```bash
cd /c/Projects/Octabam/.superpowers/v2
for f in sync-p3.sh wsl-sync-p3.sh run-3.sh wslrun-3; do
  g=$(echo "$f" | sed 's/p3/p5/; s/-3/-5/')
  sed 's/stem-rec-p3/stem-rec-p5/g; s/stemrec3/stemrec5/g; s/sync-p3-list/sync-p5-list/g; s/v3-/v5-/g; s/run-3\.sh/run-5.sh/g; s/wsl-sync-p3/wsl-sync-p5/g' "$f" > "$g"
done
grep -l "p3\|stemrec3\|v3-" sync-p5.sh wsl-sync-p5.sh run-5.sh wslrun-5 || echo "clean"
```
Expected: `clean`.

- [ ] **Step 3: The fixtures and a first check**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-start bash -c 'export STEMS_TEMPLATE="/home/yvez/stemrec5/out/projects/Ultimate FX 1.5.3"; .venv/bin/python3 tools/verify/stems_fixture.py && .venv/bin/python3 tools/verify/stems_fixture.py --thru && make bus REMIX=stems > /dev/null && python3 tools/build/dsp_disasm_all.py && .venv/bin/python3 tools/verify/verify_stems.py stems --static'`
Expected: `# exit 0`, every static check PASS, `out/dsp/payload_A.asm` written.

- [ ] **Step 4: The ledger**

Create `.superpowers/sdd/2026-10-01-stem-rec-sources/progress.md` with the plan's path, the spec's, the trees, and Task 1's result line. No commit (the directory is excluded).

---

### Task 2: The level path, measured and written down (probes 1 and 2)

**Files:**
- Create: `tools/verify/stems_levels_probe.py`
- Modify: `docs/firmware/STEM_REC.md` (section 18.1-18.4), `docs/firmware/DSP.md` (section 6c's row for `0x80005460`; "Core 0's frame")

**Interfaces:**
- Produces: `stems_levels_probe.run(fixture_json, frames=300, extra=()) -> dict` with keys `pages` (bytes, 5 pages), `write_idx`, `sent_idx`, `dsp_x4800`, `dsp_targets`, `dsp_state`, `table_ok`, `w29_writers` (set of PCs), `exit`; `out/stems_runs/lv_mover.txt` (one line: `poke 0x<addr>` or `midi`), read by Tasks 3 and 5.

- [ ] **Step 1: Write the probe**

`tools/verify/stems_levels_probe.py`:
```python
#!/usr/bin/env python3
"""STEM REC piece 5, probes 1-2: the level words the ColdFire hands core 0.

    python3 tools/verify/stems_levels_probe.py one|thru [--poke ADDR=VAL@FRAME ...]

Runs the port on a fixture card and prints, at the run's end: the page
indexes 0x80004800 (written) and 0x80004804 (sent by channel 0), the five
pages at 0x80005460, the DSP's copy at X:0x4800, core 0's targets
(Y:0x00-0x13), its ramp state (X:0x3dd, five words a slot), whether the
table words at 0x400ea18a still equal the image's, and which instructions
write a page's MAIN level halfword (0x29). Facts only: the assertions are
verify_stems' (docs/firmware/STEM_REC.md section 18)."""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
BASE = 0x40000400
PAGES, NPAGES, PAGE = 0x80005460, 5, 0x80
TABLE = 0x400ea18a                      # X:0x6c00's words in the image, 3 bytes LE
WORK = ROOT / "out/stems_runs"
WATCH = re.compile(r"\s*\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \((\d)\) at pc (0x[0-9a-f]+)")


def table_words(img, n=258):
    off = TABLE - BASE
    return [int.from_bytes(img[off + 3 * i:off + 3 * i + 3], "little") for i in range(n)]


def peeks(log, space, addr):
    m = re.search(rf"core 0 {space}:{addr:#07x}:((?: [0-9a-f]{{6}})+)", log)
    return [int(w, 16) for w in m.group(1).split()] if m else []


def run(fixture_json, frames=300, extra=()):
    fx = json.loads(pathlib.Path(fixture_json).read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    tag = pathlib.Path(fixture_json).stem
    sram, tab, idx = WORK / f"lv_{tag}.sram", WORK / f"lv_{tag}.tab", WORK / f"lv_{tag}.idx"
    w29 = ";".join(f"0x{PAGES + p * PAGE + 2 * 0x29:x},2" for p in range(NPAGES))
    args = [str(EMU), "--image", str(IMAGE), "--card", fx["card"], "--set", fx["set"],
            "--project", fx["project"], "--sequencer", "--internal-clock", "--frames", str(frames),
            "--load-ms", "20000", "--dsp", "--main-level", "64", "--pre-roll", "40", "--poke-trig", "2",
            "--mem-dump", f"0x80004800,8={idx};0x{PAGES:x},{NPAGES * PAGE}={sram};0x{TABLE:x},{258 * 3}={tab}",
            "--dsp-peek", "0:X:0x4800,48;0:Y:0x0,20;0:X:0x3dd,50",
            "--watch-mem", w29, *extra]
    if fx.get("audio_in"):
        args += ["--audio-in", fx["audio_in"]]
    r = subprocess.run(args, capture_output=True, text=True)
    log = r.stdout + r.stderr
    (WORK / f"lv_{tag}.log").write_text(log)
    ib = idx.read_bytes() if idx.exists() else b"\0" * 8
    tb = tab.read_bytes() if tab.exists() else b""
    return {"pages": sram.read_bytes() if sram.exists() else b"",
            "write_idx": int.from_bytes(ib[0:4], "big"), "sent_idx": int.from_bytes(ib[4:8], "big"),
            "dsp_x4800": peeks(log, "X", 0x4800), "dsp_targets": peeks(log, "Y", 0),
            "dsp_state": peeks(log, "X", 0x3dd),
            "table_ok": [int.from_bytes(tb[3 * i:3 * i + 3], "little") for i in range(258)]
                        == table_words(STOCK.read_bytes()),
            "w29_writers": {m.group(5) for m in map(WATCH.match, log.splitlines()) if m},
            "exit": r.returncode}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "one"
    fx = ROOT / {"one": "out/stems_fixture.json", "thru": "out/stems_fixture_thru.json",
                 "thru1": "out/stems_fixture_thru1.json"}[which]
    extra = []
    for a in sys.argv[2:]:
        if a.startswith("--poke"):
            continue
        if a.startswith("midi:"):
            extra += ["--midi", a[5:]]
            continue
        what, frame = a.split("@")
        extra += ["--step", f"{frame}:poke:{what}"]
    res = run(fx, extra=extra)
    print(f"exit {res['exit']}  write_idx {res['write_idx']}  sent_idx {res['sent_idx']}")
    for p in range(NPAGES):
        pg = res["pages"][p * PAGE:(p + 1) * PAGE]
        print(f"page {p}: " + " ".join(f"{int.from_bytes(pg[i:i + 2], 'big'):04x}" for i in range(0, 0x58, 2)))
    print("X:0x4800 ", " ".join(f"{w:06x}" for w in res["dsp_x4800"]))
    print("Y targets", " ".join(f"{w:06x}" for w in res["dsp_targets"]))
    print("X:0x3dd  ", " ".join(f"{w:06x}" for w in res["dsp_state"]))
    print(f"table words unchanged at run end: {res['table_ok']}")
    print(f"writers of a page's MAIN level halfword: {sorted(res['w29_writers'])}")


if __name__ == "__main__":
    main()
```
(The extra arguments are `ADDR=VAL@FRAME`, for example `0x80000c50=64@120`, or `midi:FILE` for the port's `--midi` file of `<frame> <hex bytes>` lines; a leading `--poke` word is ignored.)

- [ ] **Step 2: Run it on both fixtures**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-lv-one .venv/bin/python3 tools/verify/stems_levels_probe.py one && bash .superpowers/v2/wslrun-5 p5-lv-thru .venv/bin/python3 tools/verify/stems_levels_probe.py thru`
Expected, both: `exit 0`; the pages as in "Measured before this plan" (T5/T6 at LEVEL 0 on `one`); `X:0x4800` the same words with `03` on top; Y targets `000000 1f7fe3` for each slot at LEVEL 127; `X:0x3dd` slot 0 `000000 000000 000000 000000 1f7fe0`; `table words unchanged at run end: True`; one or more writer PCs.

- [ ] **Step 3: Find the MAIN level's source byte**

Disassemble each writer PC from Step 2 (`scripts/disasm.sh emac <pc-0x30> 80`) and follow the register it stores back to its load. Try the candidate this gives, then `0x80000035` and `0x8000005f` (`docs/firmware/LEVEL_LAW.md` section 3), each with `stems_levels_probe.py one <addr>=127@120`.
Expected: one of them makes halfword `0x29` of the newest pages read `007f`. Record it in the ledger as `MAIN_LEVEL_SRC`, with the disassembly lines. If none does, record "the MAIN level is not drivable under the port"; Task 5's gate then runs at MAIN level 64 only and prints a named `[SKIP]` for that part.

- [ ] **Step 4: Find a way to move a track's LEVEL**

Run: `bash .superpowers/v2/wslrun-5 p5-lv-move .venv/bin/python3 tools/verify/stems_levels_probe.py thru 0x80000c50=64@120` (T1's level byte, `docs/firmware/MIDI.md`).
Expected: page slot 0's w1 reads `4000`, and `X:0x3dd` slot 0's MAIN gain is below `0x1f7fe0`. Then write `out/stems_runs/lv_mover.txt` with the line `poke 0x80000c50` (in WSL; it's a run artifact, not committed). If the poke doesn't move w1, write `120 B0 2E 40` (CC 46, channel 1) to `out/stems_runs/lv_cc46.txt`, run the probe with `midi:out/stems_runs/lv_cc46.txt`, and on success write `midi` into `lv_mover.txt`; Task 5 Step 2 then uses the MIDI form.

- [ ] **Step 5: Write STEM_REC.md section 18.1-18.4 and fix DSP.md**

Append to `docs/firmware/STEM_REC.md` a section `## 18. The level path (piece 5)` with a method line (the probe, the logs `v5-p5-lv-*.log`, the image hash) and four subsections, each written from the measured values of Steps 2-4 in the file's style (✅ measured, 🟡 inferred with a falsifier):
- `### 18.1 The level pages ✅`: the five pages, the two indexes and their code sites (`0x4000ac18`, `0x400049da`), the sent index written twice a frame, the halfword layout per slot, `0x28`/`0x29`, the `0x03` tag in the DSP's copy, both fixtures' words, `MAIN_LEVEL_SRC` with its disassembly, and the LEVEL mover.
- `### 18.2 The gain path ✅`: the arithmetic as in "Measured before this plan", with the instruction ranges `P:0xf5`-`0x165`, the MASTER TRACK branch at `P:0x113`, and the mixdown `P:0x259`-`0x28f`.
- `### 18.3 The ramp and its residual ✅`: the state at `X:0x3dd + 5k`, the per-frame rule, target `0x1f7fe3` against the settled `0x1f7fe0`, the zero upload at boot (payload A's X module at `0x3dd`, 50 words), and that `X:0x4800`/`0x2800` are not uploaded.
- `### 18.4 The table ✅`: `X:0x6c00`, `T[0..257]`, the image address `0x400ea18a`, unchanged at a run's end, and why the hook reads it rather than computing a sine.

In `docs/firmware/DSP.md` section 6c, replace the table row that begins `` | `0x80005460..0x80005e60`, page-stepped `` with:
```
| `0x80005460` + [`0x80004804`]·`0x80` (5 pages; [`0x80004800`] is the one written) | 64 | `X:$205` (`0x4800` A / `0x2800` B) | the level words: per slot cue send, level, MAIN table index, split; cue and MAIN level at halfwords `0x28`/`0x29` (`STEM_REC.md` 18.1) |
```
and under "Core 0's frame" add after the table: `The level path and the gain ramp in detail: STEM_REC.md section 18.2-18.3.`

- [ ] **Step 6: Commit**

```bash
git add tools/verify/stems_levels_probe.py docs/firmware/STEM_REC.md docs/firmware/DSP.md
git commit -m "STEM_REC 18.1-18.4: the level pages at 0x80005460, core 0's MAIN-gain arithmetic, the ramp and its residual, the table read from the image -- measured under the port; DSP.md 6c: that ring is the level words, not input slots

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The reference model, proven against core 0's own gains

**Files:**
- Create: `tools/verify/stems_gain.py`, `tools/verify/tests/test_stems_gain.py`
- Modify: `tools/verify/stems_fixture.py` (a `--thru1` fixture: T1 alone sounding, on inputs A|B)

**Interfaces:**
- Consumes: Task 2's page layout and `lv_mover.txt`.
- Produces: in `stems_gain.py`: `sext24`, `lim24`, `mpy(a, b)`, `target(w1, w2, w29, table)`, `class Mirror(table)` with `.step(page) -> list[list[int]]` (per slot 0..7, its 16 MAIN gains) and `.state` (per slot `[split, increment, gain]`), `stem24(g, x24)`, `main24(gains, xs)`, `sent_pages(log) -> list[list[int]]`, `dsp_peeks(log, space, addr) -> list[int]`, `validate(fixture) -> bool`; `stems_fixture.build_thru1()` writing `out/stems_fixture_thru1.json`.

- [ ] **Step 1: Write the failing unit tests**

`tools/verify/tests/test_stems_gain.py`:
```python
"""tools/verify/stems_gain.py: core 0's MAIN-gain arithmetic, from the
disassembly (docs/firmware/STEM_REC.md 18.2-18.3)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import stems_gain as sg  # noqa: E402

# A stand-in table: the hook reads the real one from the image. These tests
# need only T[254], which the port read as 0x7ffd87 (STEM_REC.md 18.4).
TABLE = [0] * 258
TABLE[254] = 0x7ffd87


def page(w1=0x7f00, w2=0x7f00, w3=0, w29=0x0040):
    words = [0] * 64
    for k in range(8):
        words[4 * k + 1], words[4 * k + 2], words[4 * k + 3] = w1, w2, w3
    words[0x29] = w29
    return words


class Arithmetic(unittest.TestCase):
    def test_mpy_is_the_dsp_fractional_multiply_truncated(self):
        self.assertEqual(sg.mpy(0x400000, 0x400000), 0x200000)          # 0.5 * 0.5
        self.assertEqual(sg.mpy(-0x400000, 0x400000), -0x200000)
        self.assertEqual(sg.mpy(1, 1), 0)                               # floor
        self.assertEqual(sg.mpy(-1, 1), -1)                             # floor, not toward zero

    def test_lim24_saturates_minus_one_squared(self):
        self.assertEqual(sg.lim24(sg.mpy(-0x800000, -0x800000)), 0x7fffff)

    def test_target_reproduces_the_port(self):
        # T1 at LEVEL 127 (w1 0x7f00), table index 254 (w2 0x7f00), MAIN
        # level 64: core 0's Y:0x01 read 0x1f7fe3 under the port.
        self.assertEqual(sg.target(0x7f00, 0x7f00, 0x0040, TABLE), 0x1f7fe3)

    def test_level_zero_is_silence(self):
        self.assertEqual(sg.target(0x0000, 0x7f00, 0x0040, TABLE), 0)


class Ramp(unittest.TestCase):
    def test_a_ramp_from_zero_settles_on_the_floor_of_the_target(self):
        m = sg.Mirror(TABLE)
        g = m.step(page())
        self.assertEqual(g[0][0], 0)                                     # sample 0: the old gain
        self.assertEqual(m.state[0], [0, 0x1f7fe3 >> 4, 0x1f7fe0])      # the port's settled gain
        self.assertEqual(m.step(page())[0], [0x1f7fe0] * 16)             # 3 LSB short, for good

    def test_a_split_holds_then_ramps(self):
        m = sg.Mirror(TABLE)
        m.step(page())
        g = m.step(page(w1=0x4000, w3=5))                                # LEVEL 64 from sample 5
        self.assertEqual(g[0][:5], [0x1f7fe0] * 5)
        inc = sg.lim24((sg.target(0x4000, 0x7f00, 0x0040, TABLE) - 0x1f7fe0) >> 4)
        self.assertEqual(g[0][5:], [0x1f7fe0 + i * inc for i in range(11)])
        g = m.step(page(w1=0x4000, w3=5))                                # m = min(5, 5): five more
        self.assertEqual(g[0][:5], [0x1f7fe0 + (11 + i) * inc for i in range(5)])

    def test_a_shorter_split_cuts_the_ramp(self):
        m = sg.Mirror(TABLE)
        m.step(page())
        m.step(page(w1=0x4000, w3=5))
        cur = m.state[0][2]
        g = m.step(page(w1=0x4000, w3=0))                                # m = min(0, 5) = 0
        inc = sg.lim24((sg.target(0x4000, 0x7f00, 0x0040, TABLE) - cur) >> 4)
        self.assertEqual(g[0][:2], [cur, cur + inc])


class Stem(unittest.TestCase):
    def test_one_track_is_its_share_of_the_mix(self):
        self.assertEqual(sg.stem24(0x1f7fe0, 0x400000), (0x1f7fe0 * 0x400000) >> 21)
        self.assertEqual(sg.main24([0x1f7fe0], [0x400000]), sg.stem24(0x1f7fe0, 0x400000))

    def test_a_stem_clips_like_the_mix(self):
        self.assertEqual(sg.stem24(0x7fffff, 0x7fffff), 0x7fffff)
        self.assertEqual(sg.stem24(0x7fffff, -0x800000), -0x800000)


class Pages(unittest.TestCase):
    def test_a_page_is_taken_when_the_index_moves_past_it(self):
        log = "\n".join([
            "   [     1.0] [0x80005462] <- 0x7f00 (2) at pc 0x4000cb6a in x  i=1",
            "   [     2.0] [0x80004804] <- 0x1 (4) at pc 0x40004e72 in x  i=2",
            "   [     2.0] [0x80004804] <- 0x1 (4) at pc 0x40004e72 in x  i=3",   # the second core's write
            "   [    18.0] [0x800054e2] <- 0x4000 (2) at pc 0x4000cb6a in x  i=4",
            "   [    18.0] [0x80004804] <- 0x2 (4) at pc 0x40004e72 in x  i=5",
            "   [    34.0] [0x80004804] <- 0 (4) at pc 0x40004e72 in x  i=6"])
        pages = sg.sent_pages(log)
        self.assertEqual(len(pages), 2)                                  # page 1, then page 2
        self.assertEqual(pages[0][1], 0x4000)
        self.assertEqual(pages[1][1], 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-gain-red .venv/bin/python3 -m unittest tools/verify/tests/test_stems_gain.py`
Expected: `ModuleNotFoundError: No module named 'stems_gain'`.

- [ ] **Step 3: Write the model**

`tools/verify/stems_gain.py`:
```python
#!/usr/bin/env python3
"""Core 0's MAIN-gain arithmetic, as payload A runs it (docs/firmware/
STEM_REC.md 18.2-18.3), for STEM REC's stems after the fader.

    python3 tools/verify/stems_gain.py validate

Every value is a 24-bit DSP word held as a signed int. mpy is the DSP's
fractional multiply (a*b*2, the top 24 bits of 48: floor(a*b / 2^23));
lim24 is the limiting move to memory. A page is the 64 halfwords the
ColdFire hands core 0 through X:$205: per slot k four words at 4k (cue
send, level, MAIN table index, split), the MAIN level at 0x29.

The hook (modules/stems/stems.s) does the same arithmetic on the ColdFire;
verify_stems compares the hook with core 0, and `validate` this model."""
import re

NSLOTS = 8          # the tracks; slots 8 and 9 are the inputs, recorded raw
PAGES, NPAGES, PAGE, SENT = 0x80005460, 5, 0x80, 0x80004804
WATCH = re.compile(r"\s*\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \((\d)\)")


def sext24(v):
    v &= 0xffffff
    return v - 0x1000000 if v & 0x800000 else v


def lim24(v):
    return max(-0x800000, min(0x7fffff, v))


def mpy(a, b):
    return (a * b) >> 23


def target(w1, w2, w29, table):
    """One slot's MAIN target: P:0xf5-0x10a (w1 times 0x80, the low word
    kept, squared), then P:0x115-0x130 (the MAIN level squared, times
    T[w2], times the slot's square)."""
    x = sext24(w1 << 8)
    w1sq = lim24(mpy(x, x))
    m = sext24((w29 & 0xff) << 16)
    m2 = lim24(mpy(m, m))
    idx = sext24(w2 << 8) >> 15
    t = table[idx] if 0 <= idx < len(table) else 0
    return lim24(mpy(w1sq, lim24(mpy(m2, t))))


class Mirror:
    """The MAIN chain of P:0x203-0x237 for each track slot. state[k] =
    [split, increment, gain], zero at boot as payload A uploads X:0x3dd."""

    def __init__(self, table):
        self.table = table
        self.state = [[0, 0, 0] for _ in range(NSLOTS)]

    def step(self, page):
        out = []
        for k in range(NSLOTS):
            sp, inc, cur = self.state[k]
            s = page[4 * k + 3] & 15
            tgt = target(page[4 * k + 1], page[4 * k + 2], page[0x29], self.table)
            m = min(s, sp)
            g = []
            for _ in range(m):
                g.append(cur)
                cur += inc
            g += [cur] * (s - m)
            inc = lim24((tgt - cur) >> 4)
            for _ in range(16 - s):
                g.append(cur)
                cur += inc
            self.state[k] = [s, inc, cur]
            out.append(g)
        return out


def stem24(g, x24):
    """One track's share of MAIN for one sample: the mixdown's product,
    times 4 (asl #2), limited (P:0x259-0x28f)."""
    return lim24((g * x24) >> 21)


def main24(gains, xs):
    return lim24(sum(g * x for g, x in zip(gains, xs)) >> 21)


def sent_pages(log):
    """Every page channel 0 sent, in order, from a --watch-mem log of the
    sent index and the page ring (the port's line: `[sample] [addr] <- value
    (bytes) at pc ...`). The index is written once per core, so a repeat of
    the same value is the same frame; a page is taken when the index moves
    past it, with every write of its frame in it."""
    ring, out, cur = bytearray(NPAGES * PAGE), [], None
    for line in log.splitlines():
        m = WATCH.match(line)
        if not m:
            continue
        addr, val, nb = int(m.group(2), 16), int(m.group(3), 0), int(m.group(4))
        if addr == SENT:
            if val != cur:
                if cur is not None:
                    p = ring[cur * PAGE:(cur + 1) * PAGE]
                    out.append([int.from_bytes(p[i:i + 2], "big") for i in range(0, PAGE, 2)])
                cur = val
        elif PAGES <= addr < PAGES + NPAGES * PAGE:
            o = addr - PAGES
            ring[o:o + nb] = (val & ((1 << 8 * nb) - 1)).to_bytes(nb, "big")
    return out


def dsp_peeks(log, space, addr):
    m = re.search(rf"core 0 {space}:{addr:#07x}:((?: [0-9a-f]{{6}})+)", log)
    return [sext24(int(w, 16)) for w in m.group(1).split()] if m else []


def validate(fixture="out/stems_fixture_thru1.json", frames=420):
    """One port run with T1's LEVEL stepped at frames 150 (64), 151 (100),
    200 (20) and 260 (127) -- two steps one frame apart cut a ramp -- every
    page write and sent index logged. Every sent page replayed through
    Mirror must leave core 0's ramp state (X:0x3dd) and its last frame's
    MAIN gains (Y:0x4a + 20j + k for j >= 2; the cue mix rewrites
    Y:0x40-0x5f) as the DSP has them. The run can end inside core 0's frame,
    so either of the model's last two frames may be the DSP's."""
    import json
    import pathlib
    import subprocess
    root = pathlib.Path(__file__).resolve().parents[2]
    fx = json.loads((root / fixture).read_text())
    mover = (root / "out/stems_runs/lv_mover.txt").read_text().split()
    args = [str(root / "out/emu/ot_emu"), "--image", str(root / "out/mainos_bus.bin"), "--card", fx["card"],
            "--set", fx["set"], "--project", fx["project"], "--sequencer", "--internal-clock",
            "--frames", str(frames), "--load-ms", "20000", "--dsp", "--main-level", "64",
            "--pre-roll", "40", "--poke-trig", "2", "--audio-in", fx["audio_in"],
            "--watch-mem", f"0x{SENT:x},4;0x{PAGES:x},{NPAGES * PAGE}",
            "--dsp-peek", "0:X:0x3dd,50;0:Y:0x40,320"]
    steps = ((150, 64), (151, 100), (200, 20), (260, 127))
    if mover[0] == "poke":
        for f, v in steps:
            args += ["--step", f"{f}:poke:{mover[1]}={v}"]
    else:
        mid = root / "out/stems_runs/gainval_midi.txt"
        mid.write_text("".join(f"{f} B0 2E {v:02X}\n" for f, v in steps))
        args += ["--midi", str(mid)]
    r = subprocess.run(args, capture_output=True, text=True)
    log = r.stdout + r.stderr
    (root / "out/stems_runs/gainval.log").write_text(log)
    img = (root / "out/raw/section_3_MAIN_OS.bin").read_bytes()
    off = 0x400ea18a - 0x40000400
    table = [int.from_bytes(img[off + 3 * i:off + 3 * i + 3], "little") for i in range(258)]
    pages = sent_pages(log)
    mirror, gains, states = Mirror(table), [], []
    for p in pages:
        gains.append(mirror.step(p))
        states.append([list(s) for s in mirror.state])
    x, y = dsp_peeks(log, "X", 0x3dd), dsp_peeks(log, "Y", 0x40)
    if len(x) != 50 or len(y) != 320 or len(pages) < 300:
        print(f"incomplete run: {len(pages)} pages, {len(x)} X words, {len(y)} Y words")
        return False
    dsp_state = [[x[5 * k], x[5 * k + 2], x[5 * k + 4]] for k in range(8)]
    dsp_main = [[y[20 * j + 10 + k] for j in range(2, 16)] for k in range(8)]
    # The run can end inside core 0's per-slot loop: each slot may be at the
    # model's last frame or the one before.
    ok = all(any(dsp_state[k] == states[-back][k] and dsp_main[k] == gains[-back][k][2:16] for back in (1, 2))
             for k in range(8))
    if ok:
        print(f"the model equals core 0 in every track slot: {len(pages)} pages replayed")
        return True
    print("MISMATCH")
    print("core 0 : T1 state", dsp_state[0], "MAIN gains j=2..5", dsp_main[0][:4])
    for back in (1, 2):
        print(f"model -{back}: T1 state", states[-back][0], "MAIN gains j=2..5", gains[-back][0][2:6])
    return False


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["validate"]:
        sys.exit(0 if validate() else 1)
    print(__doc__)
```

- [ ] **Step 4: Run the unit tests**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-gain-green .venv/bin/python3 -m unittest tools/verify/tests/test_stems_gain.py`
Expected: `OK` (10 tests). A failure here is a finding about the model or the reading of the disassembly: re-read the instructions it names before changing either.

- [ ] **Step 5: The one-THRU fixture**

In `tools/verify/stems_fixture.py`, make `build_thru` end with `return result` if it doesn't, and add after it:
```python
THRU1_JSON = ROOT / "out" / "stems_fixture_thru1.json"
THRU1_CARD = ROOT / "out" / "stems_fixture_thru1_card.img"


def build_thru1(project_dir=DEFAULT_PROJECT):
    """T1 alone sounds, a THRU machine on inputs A|B in stereo; T2-T8 are
    THRU with both input pairs off, so MAIN is T1's share alone and a
    post-fader stem must equal it sample for sample (piece 5)."""
    inputs = {t: (0, 0) for t in range(1, 9)}
    inputs[1] = (1, 0)
    res = build_thru(project_dir, inputs=inputs)
    THRU1_CARD.write_bytes(pathlib.Path(res["card"]).read_bytes())
    res = {**res, "card": str(THRU1_CARD)}
    THRU1_JSON.write_text(json.dumps(res, indent=2) + "\n")
    print(f"-> {THRU1_JSON}")
    return res
```
In the `__main__` block, before the `--thru` branch:
```python
    elif len(sys.argv) > 1 and sys.argv[1] == "--thru1":
        build_thru1(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROJECT)
```
and the docstring's usage line becomes `[--eight | --fat32 | --thru | --thru1]`. The `--thru1` build rewrites `out/stems_fixture_thru_card.img` on the way: rebuild `--thru` after it whenever both are needed (Task 5 Step 2 makes `fixtures()` do that in order).

- [ ] **Step 6: The model against core 0**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-fixture1 bash -c '.venv/bin/python3 tools/verify/stems_fixture.py --thru1 && .venv/bin/python3 tools/verify/stems_fixture.py --thru' && bash .superpowers/v2/wslrun-5 p5-gain-val .venv/bin/python3 tools/verify/stems_gain.py validate`
Expected: `the model equals core 0 in every track slot`, with about 450 pages replayed. Also run `stems_levels_probe.py thru1` once and check T1's w1 moved and T2-T8 sound nowhere (their read-back slots silent in the block dump of the validate run).

**STOP if it prints `MISMATCH`.** Record the printed values in the ledger and bring them to Yves (the stop condition).

- [ ] **Step 7: Commit**

```bash
git add tools/verify/stems_gain.py tools/verify/tests/test_stems_gain.py tools/verify/stems_fixture.py
git commit -m "stems_gain: core 0's MAIN-gain arithmetic as a reference model -- unit tests from the disassembly, and a replay of every page core 0 received that leaves its ramp state and per-sample gains exactly as the DSP has them, through LEVEL steps and a cut ramp; the one-THRU fixture

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The hook's view: offsets, the inputs, MASTER TRACK (probes 3-6)

**Files:**
- Modify: `modules/stems/stems.s` (a test seam, `stems_trace`), `tools/verify/stems_levels_probe.py` (a `trace` mode), `docs/firmware/STEM_REC.md` (18.5-18.8)

**Interfaces:**
- Consumes: Task 3's model and `sent_pages`.
- Produces, recorded in STEM_REC.md 18.5 and the ledger: `GAIN_LAG` (how many frames before the newest mirrored page the gains of the MAIN found in `0x80005e60` were), `TRACK_HALF` (0: the read-back half `PING` names, 1: the other half) and `TRACK_DELAY` (0 or 1 extra frame); `IN_AB_OFF`, `IN_CD_OFF` (the inputs' offsets from `0x80005e60`, expected `0x100`, `0x180`) and `IN_A_IS_LEFT` (expected 1); the MASTER TRACK ruling.

- [ ] **Step 1: A trace seam in the hook**

In `stems.s`, among the constants: `.equ TRACE_N, 64` and `.equ TRACE_B, 32`. After `stems_hold:`:
```asm
        .global stems_trace, stems_trace_buf
stems_trace:     .long   0          | test seam: 1..TRACE_N records that frame into stems_trace_buf, then counts on
stems_trace_buf: .space  TRACE_N*TRACE_B
```
At the top of `stems_frame_hook`, before `tst.l stems_state`:
```asm
        tst.l   stems_trace
        beq.s   .Lh_notrace
        bsr.w   stems_trace_frame
.Lh_notrace:
```
After `stems_layout`:
```asm
| ---- test seam: one frame of what the hook sees (STEM_REC.md 18.5) -----
| 32 bytes a frame: PING, the written and sent page indexes, T1's first
| read-back long in the half PING names and in the other half, MAIN's first
| L and R, and the first long at +0x100 of channel 6's buffer.
stems_trace_frame:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        move.l  stems_trace,%d0
        subq.l  #1,%d0
        cmpi.l  #TRACE_N,%d0
        bcc.s   .Lr_out
        lsl.l   #5,%d0
        movea.l %d0,%a1
        adda.l  #stems_trace_buf,%a1
        move.l  PING,%d1
        move.l  %d1,(%a1)+
        move.l  0x80004800,(%a1)+
        move.l  0x80004804,(%a1)+
        eori.l  #PING_XOR,%d1
        andi.l  #1,%d1
        moveq   #10,%d0
        lsl.l   %d0,%d1
        movea.l %d1,%a0
        adda.l  #READBACK,%a0
        move.l  (%a0),(%a1)+
        move.l  %a0,%d1
        eori.l  #0x400,%d1
        movea.l %d1,%a0
        move.l  (%a0),(%a1)+
        move.l  0x80005e60,(%a1)+
        move.l  0x80005e64,(%a1)+
        move.l  0x80005f60,(%a1)+
        addq.l  #1,stems_trace
.Lr_out:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        rts
```
Build (`make bus REMIX=stems`) and disassemble `stems_trace_frame` (`scripts/disasm.sh emac <addr> 140`): every absolute access is the long form, and the memory-to-memory moves are `movel 0x80004800,%a1@+`.

- [ ] **Step 2: A trace mode in the probe**

Add to `stems_levels_probe.py`:
```python
def syms():
    out = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                         capture_output=True, text=True).stdout
    return {p[2]: int(p[0], 16) for p in (l.split() for l in out.splitlines()) if len(p) == 3}


def readback24(dump):
    """T1's 24-bit samples per frame from a --block-dump, both halves:
    {(ram, frame): [L0, R0, L1, R1, ...]}."""
    sys.path.insert(0, str(ROOT / "tools/harness"))
    import blockdump
    out = {}
    for d, frame, ch, core, ram, w in blockdump.read(dump):
        if ram in (0x80003190, 0x80003590) and d == "<":
            out[(ram, frame)] = [sext((w[2 * i] << 8) | (w[2 * i + 1] >> 8)) for i in range(32)]
    return out


def sext(v):
    return v - 0x1000000 if v & 0x800000 else v


def trace(fixture_json, start=150):
    """The hook's view for TRACE_N frames from `start`, against the model:
    for each traced frame N, which mirrored frame's gains and which
    read-back long (this half, the other half, either one frame older)
    give MAIN's first L sample (STEM_REC.md 18.5). T1 must sound alone."""
    sys.path.insert(0, str(ROOT / "tools/verify"))
    import stems_gain as sg
    s = syms()
    fx = json.loads(pathlib.Path(fixture_json).read_text())
    buf = WORK / "lv_trace.buf"
    args = [str(EMU), "--image", str(IMAGE), "--card", fx["card"], "--set", fx["set"],
            "--project", fx["project"], "--sequencer", "--internal-clock", "--frames", str(start + 80),
            "--load-ms", "20000", "--dsp", "--main-level", "64", "--pre-roll", "40", "--poke-trig", "2",
            "--audio-in", fx["audio_in"],
            "--step", f"{start}:poke:0x{s['stems_trace'] + 3:x}=1",
            "--mem-dump", f"0x{s['stems_trace_buf']:x},{64 * 32}={buf}",
            "--watch-mem", f"0x80004804,4;0x{PAGES:x},{NPAGES * PAGE}"]
    r = subprocess.run(args, capture_output=True, text=True)
    log = r.stdout + r.stderr
    (WORK / "lv_trace.log").write_text(log)
    raw = buf.read_bytes()
    rows = [[int.from_bytes(raw[32 * f + 4 * i:32 * f + 4 * i + 4], "big") for i in range(8)] for f in range(64)]
    img = STOCK.read_bytes()
    mirror = sg.Mirror(table_words(img))
    pages = sg.sent_pages(log)
    frames = [mirror.step(p) for p in pages]
    print("frame  ping  wr sent  T1:this   T1:other  MAIN-L    MAIN-R    +0x100")
    found = {}
    for f, (ping, wr, sent, this, other, ml, mr, ab) in enumerate(rows):
        print(f"{f:5d}  {ping:4d} {wr:3d} {sent:4d}  {this:08x}  {other:08x}  {ml:08x}  {mr:08x}  {ab:08x}")
        want = sext(ml >> 8)
        if f < 2 or not ml:
            continue
        cands = {"this": sext(this >> 8), "other": sext(other >> 8),
                 "this-1": sext(rows[f - 1][3] >> 8), "other-1": sext(rows[f - 1][4] >> 8)}
        for lag in range(4):
            # the newest mirrored frame at hook frame f is the one for `sent`; count back `lag`
            g = frames[-(len(rows) - f) - lag - 1][0][0] if len(frames) > len(rows) + lag else None
            for name, x in cands.items():
                if g is not None and sg.stem24(g, x) == want:
                    found[(lag, name)] = found.get((lag, name), 0) + 1
    print("matches of MAIN's first L sample, by (gain lag, sample):", sorted(found.items(), key=lambda kv: -kv[1]))
```
and in `main()`: `if which == "trace": trace(ROOT / "out/stems_fixture_thru1.json"); return` before the fixture lookup. (The index arithmetic `frames[-(len(rows) - f) - lag - 1]` assumes the run's last traced frame is the newest mirrored page; the printout's (lag, sample) table is what decides, and Step 3 checks it against the sent indexes in the rows.)

- [ ] **Step 3: Run the trace**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-trace .venv/bin/python3 tools/verify/stems_levels_probe.py trace`
Expected: the `sent` column advances by one each frame (mod 5); one (lag, sample) pair matches in nearly every traced frame with sound, and no other pair comes close. Write down `GAIN_LAG` (the lag) and, from the sample name, `TRACK_HALF` (`this` → 0, `other` → 1) and `TRACK_DELAY` (`-1` → 1). If the indexing assumption above is wrong, the sent indexes in the rows say by how much: fix the index, rerun, and record the fix. The USB track-out module's measurement predicts MAIN one block behind the previous half, that is `TRACK_HALF = 1`, `TRACK_DELAY = 1`.

- [ ] **Step 4: The inputs**

Read the stock recorder's source setup (`scripts/disasm.sh emac 0x400068e4 400`, and the caller in the per-frame dispatcher `0x4000d2a0`): which addresses go into the four source pointers for INAB and INCD. Then confirm under the port: in the trace rows, the `+0x100` long against the THRU fixture's input WAV (`out/test_audio/stems_in4.wav`; `ot_emu --audio-in` channels 0-3 = C, D, A, B) at the run's audio offset, for A (`+0x100`), B (`+0x104`), C (`+0x180`) and D (`+0x184`); extend the trace row with `0x80005f64`, `0x80005fe0` and `0x80005fe4` if the four aren't settled by the first.
Expected: `+0x100` A (left) and B (right), `+0x180` C and D; the recorder's INAB/INCD pointers name the same addresses. Record `IN_AB_OFF`, `IN_CD_OFF` and `IN_A_IS_LEFT` with the disassembly lines. If the recorder reads elsewhere, record where; Task 8 takes the offsets as constants.

- [ ] **Step 5: MASTER TRACK**

Make a variant of the one-THRU fixture with `MASTER_TRACK=1` in the project's `[SETTINGS]` (edit the staged `project.work` the way `stems_fixture.py` edits it; the key as `ot_project.py` spells it), run `stems_gain.py validate` against it, and read payload A `P:0x292`-`0x2d3` beside it.
Expected (from the disassembly): T1-T7 reach T8's input with the first pass's gains `Y:0x40 + 20j + k` (the cue chain), and MAIN is T8 alone with `Y:0x51 + 20j`. Ruling for Task 6, recorded: with MASTER TRACK on, a stem T1-T7 is its post-fader share of what the stems compute (the MAIN chain's gains), not of T8's input; STEM_REC.md 18.8 and `modules/stems/README.md` say so. Task 6's `master` checks only that the take is whole and aligned, never a level.

- [ ] **Step 6: Write STEM_REC.md 18.5-18.8 and commit**

Sections: `### 18.5 What the hook sees each frame ✅` (the trace, the three constants), `### 18.6 MAIN and CUE at hook time ✅` (complete, which frame), `### 18.7 The inputs ✅` (the recorder's pointers, the measured channels), `### 18.8 MASTER TRACK ✅` (the gains, the ruling).
```bash
git add modules/stems/stems.s tools/verify/stems_levels_probe.py docs/firmware/STEM_REC.md
git commit -m "STEM_REC 18.5-18.8: what the hook sees each frame -- the gain lag, the track half and delay that align a stem with MAIN, the inputs at 0x80005e60+0x100/+0x180 as the stock recorder reads them, MASTER TRACK; stems_trace, a test seam

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The gain mirror in the hook (gate 1)

**Files:**
- Modify: `modules/stems/stems.s` (the mirror, its state, the EMAC save), `tools/verify/verify_stems.py` (`port()`, check `gains`, `fixtures()`)

**Interfaces:**
- Consumes: Task 2's facts and `lv_mover.txt`, Task 4's `GAIN_LAG`, Task 2's `MAIN_LEVEL_SRC`.
- Produces: in `stems.s`: `stems_emac_in` / `stems_emac_out` (save the caller's MACSR, ACC0, ACC1 and ACCEXT01 in integer mode, set `MACSR_FRAC`; and the reverse), `stems_mirror` (every frame), `stems_gstate` (8 slots × `[split, increment, gain]` longs: core 0's `X:0x3dd + 5k` words 0, 2, 4), `stems_gstate_prev`, `stems_gq` (`GQ_N` frames × 8 slots × 16 gains), `stems_gqn`, `stems_lvskip`. In `verify_stems.py`: `dsp_state(log)`, `gain_of(log, k)`, `level_steps(pairs)`, the check `gains`, `port(..., midi_lines=())`.

- [ ] **Step 1: The EMAC forms stock runs, and its save sequence**

Run in WSL: `bash .superpowers/v2/wslrun-5 p5-emac bash -c 'm68k-elf-objdump -D -b binary -m m68k:cfv4e --adjust-vma=0x40000400 out/raw/section_3_MAIN_OS.bin > /tmp/os.dis; grep -cE "macl %d[0-7],%d[0-7],%acc[0-3]$" /tmp/os.dis; grep -c "movclrl %acc[01],%d" /tmp/os.dis; grep -cE "movel %macsr,|movel %d[0-7],%macsr" /tmp/os.dis; grep -cE "movel %acc[01],%d|movel %d[0-7],%acc[01]|accext01" /tmp/os.dis; scripts/disasm.sh emac 0x4000ac80 64; scripts/disasm.sh emac 0x4000d950 48'`
Expected: every count above 0, and the two disassemblies show the frame interrupt reading MACSR, writing integer mode, and moving ACC and ACCEXT. Record the counts and the sequence in the ledger. If plain register `macl` or `movclrl` has no stock site, STOP: the hook would run a form the chip has never run (AGENTS.md), and that goes to Yves.

- [ ] **Step 2: Write the failing check**

In `tools/verify/verify_stems.py`, beside the constants:
```python
FIXTURE_THRU1 = pathlib.Path("out/stems_fixture_thru1.json")
GQ_N = 4                                   # stems.s: frames of per-sample gains kept
MOVER = pathlib.Path("out/stems_runs/lv_mover.txt")     # Task 2: "poke 0x80000c50" or "midi"
MAIN_LEVEL_SRC = None                      # Task 2 Step 3's address, or None when the port can't drive it
LEVEL_STEPS = ((150, 64), (151, 100), (200, 20), (260, 127))   # two steps a frame apart cut a ramp
```
(write `MAIN_LEVEL_SRC` as Task 2 measured it), and after `rebuilt_peak`:
```python
def dsp_state(log):
    """Core 0's MAIN ramp state at the run's end, from --dsp-peek
    "0:X:0x3dd,50": per track slot [split, increment, gain] (words 0, 2, 4
    of each five; STEM_REC.md 18.3)."""
    m = re.search(r"core 0 X:0x003dd:((?: [0-9a-f]{6})+)", log)
    if not m:
        return []
    w = [int(x, 16) for x in m.group(1).split()]
    sx = lambda v: v - 0x1000000 if v & 0x800000 else v  # noqa: E731
    return [[sx(w[5 * k]), sx(w[5 * k + 2]), sx(w[5 * k + 4])] for k in range(8)]


def gain_of(log, k):
    """Track k's settled MAIN gain at the run's end (a run that holds its levels)."""
    st = dsp_state(log)
    return st[k][2] if st else None


def level_steps(pairs, addr=0x80000c50):
    """(steps, midi_lines) that move a level at the given frames: pokes of the
    level byte, or CC 46 on channel 1 when Task 2 found the poke doesn't move
    the page (lv_mover.txt)."""
    mover = MOVER.read_text().split() if MOVER.exists() else ["poke", hex(addr)]
    if mover[0] == "poke":
        return [f"{f}:poke:0x{addr:x}={v}" for f, v in pairs], ()
    return [], tuple(f"{f} B0 2E {v:02X}" for f, v in pairs)


def gains(s):
    """Gate 1: the hook's mirror of core 0's MAIN ramp equals the DSP's own
    at the run's end, on the one-THRU fixture with T1's LEVEL stepped four
    times and, when the port can drive it, the MAIN level once; from a clean
    boot and from dirty DSP RAM. The run may end inside core 0's frame, so
    each slot matches the hook's last mirrored frame or the one before."""
    steps, midi = level_steps(LEVEL_STEPS)
    if MAIN_LEVEL_SRC:
        steps.append(f"300:poke:0x{MAIN_LEVEL_SRC:x}=100")
    else:
        print("  [SKIP] gains: the MAIN level move (the port can't drive it, STEM_REC.md 18.1)")
    for tag, extra in (("gains", ()), ("gainsdirty", ("--dsp-dirty", "7"))):
        log, *_ = port(s, 420, tag=tag, calls_before=(), fixture=FIXTURE_THRU1, mask=None,
                       dump_blocks=False, extra=extra, steps=steps, midi_lines=midi,
                       mems=((s["stems_gstate"], 96, "gs"), (s["stems_gstate_prev"], 96, "gp"),
                             (s["stems_lvskip"], 4, "skip")))
        dsp = dsp_state(log)

        def longs(name):
            p = run_path(tag, name)
            raw = p.read_bytes() if p.exists() else b""
            return [int.from_bytes(raw[i:i + 4], "big", signed=True) for i in range(0, len(raw), 4)]
        now, prev = longs("gs"), longs("gp")
        mine = [now[3 * k:3 * k + 3] for k in range(8)]
        before = [prev[3 * k:3 * k + 3] for k in range(8)]
        check(f"{tag}: core 0's state was read", len(dsp) == 8, f"{len(dsp)} slots")
        check(f"{tag}: the mirror equals core 0's MAIN ramp in every track slot",
              len(dsp) == 8 and all(d in (m, b) for d, m, b in zip(dsp, mine, before)),
              f"core 0 T1 {dsp[0] if dsp else None}, mirror {mine[0]}, the frame before {before[0]}")
        check(f"{tag}: T1's gain moved off its start", len(dsp) == 8 and dsp[0][2] not in (0, 0x1f7fe0),
              f"{dsp[0] if dsp else None}")
        check(f"{tag}: the sent page index never jumped", longs("skip") == [0], f"{longs('skip')}")
```
In `port()`: add the parameter `midi_lines=()`, and before `subprocess.run`:
```python
    if "--dsp-peek" not in extra:
        args += ["--dsp-peek", "0:X:0x3dd,50"]          # the gains the stems used (dsp_state)
    if midi_lines:
        mid = work / f"{tag}.midi.txt"
        mid.write_text("".join(l + "\n" for l in midi_lines))
        args += ["--midi", str(mid)]
```
In `fixtures()`, build `--thru1` first and `--thru` after it (the `--thru1` build passes through the THRU card). Add `gains` to `main()`'s run list after `full`, and to the names `--only` accepts.

The spec's gate 1 also names a crossfader sweep and a scene change. Probe first whether the one-THRU fixture's scenes move a level: write `out/stems_runs/xf.txt` with the lines `120 BA 30 00`, `140 BA 30 40` and `160 BA 30 7F` (CC 48, the crossfader, on the AUTO channel 11; `docs/firmware/MIDI.md`), and run `stems_levels_probe.py thru1 midi:out/stems_runs/xf.txt`. If page slot 0's w1 (or any slot's) moves, add those three lines to `gains`' run after the LEVEL steps (`midi_lines`; with a MIDI LEVEL mover, append them to its lines) and add the check `f"{tag}: the crossfader moved a level"`. If no word moves, the template's scenes lock no level: record in the ledger that the crossfader and scenes reach the hook only through these same words, which the LEVEL steps move, and tell Yves before Task 6 that this part of gate 1 isn't exercised by the fixture.

- [ ] **Step 3: Run it to see it fail**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-gains-red VS --only=gains` (VS spelled out as in Conventions)
Expected: `KeyError: 'stems_gstate'`.

- [ ] **Step 4: The mirror**

In `stems.s`, among the stock facts:
```asm
        .equ    LV_PAGES,      0x80005460   | the level pages, 0x80 bytes each (STEM_REC.md 18.1)
        .equ    LV_SENT,       0x80004804   | long: the page channel 0 sends this frame (18.1)
        .equ    GTAB,          0x400ea18a   | X:0x6c00's words in the image, 3 bytes LE (18.4)
```
among the constants (write `GAIN_LAG` as Task 4 measured it):
```asm
        .equ    GAIN_LAG,      1            | frames before the newest mirrored page: the MAIN in 0x80005e60 (18.5)
        .equ    GQ_N,          4            | frames of per-sample gains kept; GAIN_LAG < GQ_N
        .equ    GQ_FRAME,      8*16*4       | one frame of gains: 8 slots x 16 longs
        .equ    GQ_ALWAYS,     GAIN_LAG >= 2 | gains in IDLE too, so a take started while playing has them
        .equ    MACSR_FRAC,    0x20         | fractional, truncating: the frame interrupt's own mode
```
in the state block:
```asm
        .global stems_gstate, stems_gstate_prev, stems_gq, stems_gqn, stems_lvskip
stems_lvlast:    .long   -1         | the last page index mirrored
stems_lvskip:    .long   0          | test seam: page-index steps other than +1 or a wrap to 0
stems_gw29:      .long   -1         | the MAIN level the cached targets were computed with
stems_gm2:       .long   0          | its square
stems_gcache:    .space  8*8        | per slot: w1 << 16 | w2, then its target
stems_gstate:    .space  8*12       | per slot: split, increment, gain (core 0's X:0x3dd+5k words 0, 2, 4)
stems_gstate_prev: .space 8*12      | the same, one frame earlier
stems_gqn:       .long   0          | frames written to stems_gq
stems_gq:        .space  GQ_N*GQ_FRAME
stems_emac_save: .space  16         | the caller's MACSR, ACC0, ACC1, ACCEXT01
```
After `stems_layout`:
```asm
| ---- the caller's EMAC state, saved and put back ---------------------------
| The moves run in integer mode, as the frame interrupt's own save does
| (Task 5 Step 1); the work runs in MACSR_FRAC. d0 is preserved.
stems_emac_in:
        move.l  %d0,-(%sp)
        move.l  %macsr,%d0
        move.l  %d0,stems_emac_save
        moveq   #0,%d0
        move.l  %d0,%macsr
        move.l  %acc0,%d0
        move.l  %d0,stems_emac_save+4
        move.l  %acc1,%d0
        move.l  %d0,stems_emac_save+8
        move.l  %accext01,%d0
        move.l  %d0,stems_emac_save+12
        moveq   #MACSR_FRAC,%d0
        move.l  %d0,%macsr
        move.l  (%sp)+,%d0
        rts
stems_emac_out:
        move.l  %d0,-(%sp)
        moveq   #0,%d0
        move.l  %d0,%macsr
        move.l  stems_emac_save+4,%d0
        move.l  %d0,%acc0
        move.l  stems_emac_save+8,%d0
        move.l  %d0,%acc1
        move.l  stems_emac_save+12,%d0
        move.l  %d0,%accext01
        move.l  stems_emac_save,%d0
        move.l  %d0,%macsr
        move.l  (%sp)+,%d0
        rts

| ---- the gain mirror: core 0's MAIN gains from the level pages -----------
| Every frame: the page channel 0 sends (LV_SENT), through core 0's
| arithmetic (docs/firmware/STEM_REC.md 18.2-18.3), so stems_gstate equals
| core 0's MAIN ramp state. While a take is armed or recording (always with
| GQ_ALWAYS), also each track slot's 16 gains into stems_gq. In the audio
| interrupt; every register is preserved.
stems_mirror:
        move.l  %d0,-(%sp)
        move.l  LV_SENT,%d0
        cmp.l   stems_lvlast,%d0
        bne.s   .Lg_new
        move.l  (%sp)+,%d0
        rts                                 | no new page this frame
.Lg_new:
        lea     -56(%sp),%sp
        movem.l %d1-%d7/%a0-%a6,(%sp)
        move.l  stems_lvlast,%d1
        move.l  %d0,stems_lvlast
        tst.l   %d1
        bmi.s   .Lg_seq                     | the first page
        addq.l  #1,%d1
        cmp.l   %d1,%d0
        beq.s   .Lg_seq
        tst.l   %d0
        beq.s   .Lg_seq                     | the ring wrapped to page 0
        addq.l  #1,stems_lvskip
.Lg_seq:
        bsr.w   stems_emac_in
        lea     stems_gstate,%a0            | this frame's state becomes the previous one
        lea     stems_gstate_prev,%a1
        moveq   #24,%d1
.Lg_prev:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne.s   .Lg_prev
        lsl.l   #7,%d0
        movea.l %d0,%a0
        adda.l  #LV_PAGES,%a0               | a0: the page
        moveq   #0,%d0
        move.w  0x52(%a0),%d0               | the MAIN level, halfword 0x29
        cmp.l   stems_gw29,%d0
        beq.s   .Lg_m2
        move.l  %d0,stems_gw29
        andi.l  #0xff,%d0
        ror.l   #8,%d0                      | m << 8: (W29 & 0xff) << 24
        mac.l   %d0,%d0,%acc0
        movclr.l %acc0,%d0
        asr.l   #8,%d0                      | M2 = floor(m*m / 2^23)
        cmpi.l  #0x7fffff,%d0
        ble.s   .Lg_m2ok
        move.l  #0x7fffff,%d0               | -1.0 squared, limited
.Lg_m2ok:
        move.l  %d0,stems_gm2
        lea     stems_gcache,%a1            | every target is stale
        moveq   #-1,%d2
        moveq   #8,%d1
.Lg_inval:
        move.l  %d2,(%a1)
        addq.l  #8,%a1
        subq.l  #1,%d1
        bne.s   .Lg_inval
.Lg_m2:
        suba.l  %a4,%a4                     | a4: where the gains go, 0 = nowhere
        .if     GQ_ALWAYS == 0
        tst.l   stems_state
        beq.s   .Lg_noq                     | IDLE: the state only
        .endif
        move.l  stems_gqn,%d0
        moveq   #GQ_N-1,%d1
        and.l   %d1,%d0
        move.l  #GQ_FRAME,%d1
        mulu.l  %d1,%d0
        movea.l %d0,%a4
        adda.l  #stems_gq,%a4
.Lg_noq:
        lea     stems_gstate,%a2
        lea     stems_gcache,%a3
        lea     2(%a0),%a5                  | slot 0's w1
        moveq   #0,%d6                      | slot k
.Lg_slot:
        moveq   #0,%d1
        move.w  (%a5),%d1                   | w1: the track level
        moveq   #0,%d2
        move.w  2(%a5),%d2                  | w2: the MAIN table index
        moveq   #15,%d3
        and.w   4(%a5),%d3                  | s: the split sample
        move.l  %d1,%d4
        swap    %d4
        or.l    %d2,%d4                     | the cache key: w1 << 16 | w2
        cmp.l   (%a3),%d4
        beq.w   .Lg_cached
        move.l  %d4,(%a3)
        move.l  %d1,%d0
        swap    %d0                         | x << 8 = w1 << 16, signed
        mac.l   %d0,%d0,%acc0
        movclr.l %acc0,%d0
        asr.l   #8,%d0                      | w1sq = floor(x*x / 2^23)
        cmpi.l  #0x7fffff,%d0
        ble.s   .Lg_sqok
        move.l  #0x7fffff,%d0
.Lg_sqok:
        move.l  %d2,%d5
        swap    %d5
        moveq   #23,%d4
        asr.l   %d4,%d5                     | idx = sext24(w2 << 8) >> 15
        moveq   #0,%d4                      | T = 0 below the table (a w2 of 0x8000 or more)
        tst.l   %d5
        bmi.s   .Lg_t
        movea.l %d5,%a6
        adda.l  %d5,%a6
        adda.l  %d5,%a6                     | 3 * idx
        adda.l  #GTAB,%a6
        move.b  2(%a6),%d4
        lsl.l   #8,%d4
        move.b  1(%a6),%d4
        lsl.l   #8,%d4
        move.b  (%a6),%d4                   | T: 24 bits, little-endian in the image
.Lg_t:
        move.l  stems_gm2,%d5
        lsl.l   #8,%d5
        lsl.l   #8,%d4
        mac.l   %d5,%d4,%acc0
        movclr.l %acc0,%d4
        asr.l   #8,%d4                      | tM = floor(M2 * T / 2^23)
        lsl.l   #8,%d0
        lsl.l   #8,%d4
        mac.l   %d0,%d4,%acc0
        movclr.l %acc0,%d0
        asr.l   #8,%d0                      | the target = floor(w1sq * tM / 2^23)
        move.l  %d0,4(%a3)
.Lg_cached:
        move.l  4(%a3),%d0                  | d0: the target
        movem.l (%a2),%d1/%d4-%d5           | d1: last split, d4: increment, d5: gain
        cmp.l   %d1,%d3
        bcc.s   .Lg_m                       | s >= last split: m = last split
        move.l  %d3,%d1                     | m = s
.Lg_m:
        move.l  %a4,%d2
        beq.s   .Lg_fast
        move.l  %d1,%d2                     | the old ramp: m samples
        beq.s   .Lg_h0
.Lg_old:
        move.l  %d5,(%a4)+
        add.l   %d4,%d5
        subq.l  #1,%d2
        bne.s   .Lg_old
.Lg_h0:
        move.l  %d3,%d2
        sub.l   %d1,%d2                     | the hold: s - m samples
        beq.s   .Lg_new2
.Lg_hold:
        move.l  %d5,(%a4)+
        subq.l  #1,%d2
        bne.s   .Lg_hold
.Lg_new2:
        move.l  %d0,%d4
        sub.l   %d5,%d4
        asr.l   #4,%d4                      | the new increment
        moveq   #16,%d2
        sub.l   %d3,%d2                     | the new ramp: 16 - s samples, 1..16
.Lg_ramp:
        move.l  %d5,(%a4)+
        add.l   %d4,%d5
        subq.l  #1,%d2
        bne.s   .Lg_ramp
        bra.s   .Lg_store
.Lg_fast:                                   | the state only: the same sums, multiplied
        move.l  %d4,%d2
        muls.l  %d1,%d2
        add.l   %d2,%d5                     | gain += m * increment
        move.l  %d0,%d4
        sub.l   %d5,%d4
        asr.l   #4,%d4
        moveq   #16,%d2
        sub.l   %d3,%d2
        muls.l  %d4,%d2
        add.l   %d2,%d5                     | gain += (16 - s) * the new increment
.Lg_store:
        movem.l %d3-%d5,(%a2)               | split, increment, gain
        lea     12(%a2),%a2
        addq.l  #8,%a3
        addq.l  #8,%a5
        addq.l  #1,%d6
        moveq   #8,%d0
        cmp.l   %d0,%d6
        bne.w   .Lg_slot
        move.l  %a4,%d0
        beq.s   .Lg_done
        addq.l  #1,stems_gqn
.Lg_done:
        bsr.w   stems_emac_out
        movem.l (%sp),%d1-%d7/%a0-%a6
        lea     56(%sp),%sp
        move.l  (%sp)+,%d0
        rts
```
`movem.l (%a2),%d1/%d4-%d5` loads the lowest-numbered register from the lowest address (d1 = split, d4 = increment, d5 = gain); `movem.l %d3-%d5,(%a2)` stores in the same order. The hook's top becomes:
```asm
stems_frame_hook:
        bsr.w   stems_mirror
```
followed by Task 4's trace test and the existing `tst.l stems_state`.

- [ ] **Step 5: Assemble and check the forms**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-mirror-build bash -c 'make bus REMIX=stems > /tmp/b.log 2>&1; tail -3 /tmp/b.log; for f in stems_mirror stems_emac_in stems_emac_out; do a=$(m68k-elf-nm out/platform/runtime/runtime.elf | awk "/ $f\$/{print \$1}"); echo "== $f 0x$a"; scripts/disasm.sh emac 0x$a 760 | grep -E "mac|movclr|acc|movem" | head -30; done'`
Expected: the build passes; the disassembly shows `macl %d0,%d0,%acc0`, `macl %d5,%d4,%acc0`, `movclrl %acc0,%d0`, `movel %macsr,%d0`, `movel %d0,%macsr`, `movel %acc0,%d0`, `movel %accext01,%d0` and their restores, each the form Step 1 found in stock. Any other form is a finding: fix the source, never the check.

- [ ] **Step 6: Run the check**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-gains-green VS --only=gains,full,stream`
Expected: every `gains` and `gainsdirty` check PASS; `full` and `stream` still PASS (the stems are still pre-fader here). **STOP if the mirror can't be made to equal core 0's state** in the clean run: record the first slot and field that differ and bring it to Yves. If only `gainsdirty` differs, record by how much (in gain LSB, at most 15 by the arithmetic of STEM_REC.md 18.3): that is the hardware risk of `X:0x4800` not being uploaded, and it goes to Yves with the measured size before Task 6.

- [ ] **Step 7: Commit**

```bash
git add modules/stems/stems.s tools/verify/verify_stems.py
git commit -m "stems: the gain mirror -- core 0's MAIN-gain arithmetic on the ColdFire every frame, from the level page channel 0 sends; equal to core 0's ramp state through LEVEL steps, a cut ramp and dirty DSP RAM (gate 1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Stems after the fader (gates 2 and 3, one track)

**Files:**
- Modify: `modules/stems/stems.s` (the hook's copy, the edge rule, the track delay), `tools/verify/verify_stems.py` (the read-back helpers, every check that compares a stem with a track; checks `postfader`, `postmove`, `clip`, `master`), `tools/verify/stems_fixture.py` (`write_input_wav`'s `amp`, the hot and MASTER TRACK variants)

**Interfaces:**
- Consumes: `stems_gq`, `stems_gqn`, `stems_emac_in`/`out`, Task 4's `GAIN_LAG`, `TRACK_HALF`, `TRACK_DELAY`.
- Produces: in `stems.s`: `stems_half` (d4 = T1's block in the half `PING` names), `stems_track_src`, `stems_track_gains`, `stems_track16`, `stems_tdelay_step`, `stems_tdelay`, the macro `LIM16`; the edge rule (the frame that latches records nothing; the next frame is the take's first). In `verify_stems.py`: `t1_frames(dump, g=None)`, `slot_frames(dump, k, g=None)`, `post16(g, x24)`, `main_capture(prefix)`, `take16(data)`, `STEM_LAG`.

- [ ] **Step 1: Write the failing checks**

In `verify_stems.py`, replace `t1_frames` and `slot_frames` with one reader that can apply a gain:
```python
def slot_frames(dump_path, k, g=None):
    """Track k's stereo frames from a --block-dump, in frame order: each
    sample a host-port long split in two words, its top 16 bits, then its low
    8 bits shifted up (STEM_REC.md 9.2). g=None: the top 16 bits, as the tap
    was before piece 5; a gain: the 16-bit stem after the fader, post16."""
    import blockdump
    ram_for = (0x80003190, 0x80003590) if k < 4 else (0x80003390, 0x80003790)
    base = (k % 4) * 0x40
    out = []
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram in ram_for and d == READBACK_DIR:
            if g is None:
                fr = [x - 65536 if x >= 32768 else x for x in w[base:base + 64:2]]
            else:
                fr = []
                for i in range(32):
                    v = (w[base + 2 * i] << 8) | (w[base + 2 * i + 1] >> 8)
                    fr.append(post16(g, v - 0x1000000 if v & 0x800000 else v))
            out.append((frame, fr))
    return [s for _, s in sorted(out)]


def t1_frames(dump_path, g=None):
    return slot_frames(dump_path, T1_OFFSET // 0x80, g)


def post16(g, x24):
    """A 16-bit stem sample: the top 16 bits of the track's 24-bit share of
    MAIN (STEM_REC.md 18.2), limited as core 0 limits MAIN."""
    return max(-0x8000, min(0x7fff, (g * x24) >> 29))


def main_capture(prefix):
    """MAIN from `--audio-out PREFIX`: TX0 ring words 2 and 3 of core 0's
    24-bit WAV, as L R L R ..."""
    import wave
    with wave.open(f"{prefix}_core0.wav") as w:
        n, c = w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    return [int.from_bytes(raw[(i * c + ch) * 3:(i * c + ch) * 3 + 3], "little", signed=True)
            for i in range(n) for ch in (2, 3)]


def take16(data):
    return list(struct.unpack_from(f"<{(len(data) - 44) // 2}h", data, 44))


FIXTURE_THRU1_HOT = pathlib.Path("out/stems_fixture_thru1hot.json")
FIXTURE_THRU1_MASTER = pathlib.Path("out/stems_fixture_thru1master.json")


def against_main(tag, card, fixture, aud):
    """T1.wav of the take against the captured MAIN's top 16 bits: found once,
    then equal at every sample. Returns (T1 samples, MAIN segment) or None."""
    files = dict(take_files(card, fixture))
    data = files.get("T1.wav") or files.get("T1.WAV")
    check(f"{tag}: T1.wav exists", data is not None, f"{sorted(files)}")
    if not data:
        return None
    got = take16(data)
    main = [m >> 8 for m in main_capture(aud)]
    loud = next((i for i, v in enumerate(got) if v), None)
    check(f"{tag}: the take holds sound", loud is not None)
    if loud is None:
        return None
    key = got[loud:loud + 64]
    pos = next((i for i in range(len(main) - 64) if main[i:i + 64] == key), None)
    check(f"{tag}: T1.wav's first sound is found in MAIN", pos is not None)
    if pos is None:
        return None
    seg = main[pos - loud:pos - loud + len(got)] if pos >= loud else []
    bad = next((i for i, (a, b) in enumerate(zip(got, seg)) if a != b), None)
    check(f"{tag}: every sample of T1.wav equals MAIN", bad is None and len(seg) == len(got),
          f"{len(got)} samples" if bad is None else f"first difference at sample {bad}: {got[bad]} vs {seg[bad]}")
    return got, seg


def postfader(s):
    """Gates 2-3, one track: on the one-THRU fixture (T1 alone sounds) a take
    armed before play with T1's LEVEL stepped during it. MAIN is T1's share
    alone, so T1.wav equals MAIN's top 16 bits at every sample -- through
    every step, the cut ramp included."""
    steps, midi = level_steps(LEVEL_STEPS)
    aud = run_path("postfader", "aud")
    log, dump, card, words, _ = port(s, 520, stop_at=340, tag="postfader", fixture=FIXTURE_THRU1,
                                     steps=steps, midi_lines=midi, extra=("--audio-out", str(aud)))
    against_main("postfader", card, FIXTURE_THRU1, aud)


def postmove(s):
    """Review Focus 1: the take starts while playing (REC at frame 148), two
    frames before the first LEVEL step: equal to MAIN from its first frame."""
    steps, midi = level_steps(LEVEL_STEPS)
    aud = run_path("postmove", "aud")
    log, dump, card, words, _ = port(s, 520, stop_at=340, tag="postmove", fixture=FIXTURE_THRU1,
                                     calls_before=(), calls=((148, s["stems_action"]),),
                                     steps=steps, midi_lines=midi, extra=("--audio-out", str(aud)))
    against_main("postmove", card, FIXTURE_THRU1, aud)


def clip(s):
    """Review Focus 2: T1 at LEVEL 127, the MAIN level at 127, a full-scale
    input: the stem clips exactly where MAIN does."""
    if not MAIN_LEVEL_SRC:
        print("  [SKIP] clip: the MAIN level can't be driven under the port (STEM_REC.md 18.1)")
        return
    aud = run_path("clip", "aud")
    log, dump, card, words, _ = port(s, 420, stop_at=300, tag="clip", fixture=FIXTURE_THRU1_HOT,
                                     pokes_before=[(MAIN_LEVEL_SRC, 127)], extra=("--audio-out", str(aud)))
    res = against_main("clip", card, FIXTURE_THRU1_HOT, aud)
    if res:
        got, seg = res
        rails = sum(1 for v in got if v in (32767, -32768))
        check("clip: the take clips, at the same samples as MAIN",
              rails > 0 and rails == sum(1 for v in seg if v in (32767, -32768)), f"{rails} samples at full scale")


def master(s):
    """Review Focus 5: MASTER TRACK on (STEM_REC.md 18.8): the take is whole --
    T1.wav as long as the frames recorded, and the task ends IDLE with no error."""
    log, dump, card, words, _ = port(s, 520, stop_at=340, tag="master", fixture=FIXTURE_THRU1_MASTER)
    st, status, _, wr, rd, nfr = words
    files = dict(take_files(card, FIXTURE_THRU1_MASTER))
    data = files.get("T1.wav") or files.get("T1.WAV")
    check("master: IDLE, no error, T1.wav holds every frame",
          st == ST_IDLE and status == 0 and data is not None and len(data) == 44 + 64 * nfr,
          f"state {st}, status {status}, {len(data) if data else None} bytes for {nfr} frames")
```
In `stems_fixture.py`: give `write_input_wav` an `amp=8192` parameter (used as the noise amplitude) and `build_thru` an `input_wav=INPUT_WAV, amp=8192` pair passed through to it; add
```python
def build_thru1_variant(name, amp=8192, master_track=False, project_dir=DEFAULT_PROJECT):
    """A one-THRU fixture variant: a full-scale input (amp 32767) or MASTER
    TRACK on (the project's [SETTINGS], as Task 4 Step 5 wrote it), in its own
    card and JSON, out/stems_fixture_<name>.json."""
```
written as `build_thru1` is, with the WAV written to `out/test_audio/stems_in4_<name>.wav`, `MASTER_TRACK=1` written into the staged `project.work` when asked (the exact edit Task 4 Step 5 used), and `--thru1hot` / `--thru1master` branches in `__main__`; `verify_stems.fixtures()` builds both. Add `postfader`, `postmove`, `clip` and `master` to the run list and to `--only`.

- [ ] **Step 2: Run them to see them fail**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-post-red VS --only=postfader`
Expected: `postfader: every sample of T1.wav equals MAIN` FAIL (the stems are still pre-fader).

- [ ] **Step 3: The copy after the fader**

In `stems.s`, among the constants (as Task 4 measured):
```asm
        .equ    TRACK_HALF,    1            | the samples core 0 mixes: the half PING doesn't name (18.5)
        .equ    TRACK_DELAY,   1            | ... one frame older than that half holds (18.5)
```
In the state block: `stems_tdelay: .space 8*0x80` (per track slot, the block one frame older). The macro, after `RAWCALL`:
```asm
| A value limited to 16 bits: one compare on the common path. Uses d0.
        .macro  LIM16 reg
        move.l  \reg,%d0
        addi.l  #0x8000,%d0
        cmpi.l  #0xffff,%d0
        bls.s   .Ll16\@
        tst.l   \reg
        smi     \reg
        extb.l  \reg                        | -1 below the range, 0 above
        eori.l  #0x7fff,\reg                | 0x7fff above, -0x8000 below
.Ll16\@:
        .endm
```
The routines, after `stems_mirror`:
```asm
| ---- d4 = T1's block in the read-back half PING names (Task 3 of piece 1) --
stems_half:
        move.l  PING,%d4
        eori.l  #PING_XOR,%d4
        andi.l  #1,%d4
        moveq   #10,%d0
        lsl.l   %d0,%d4
        addi.l  #READBACK,%d4
        rts

| ---- a2 = the 16 samples core 0 mixed for track k (d5 = k * 0x80) --------
stems_track_src:
        .if     TRACK_DELAY
        lea     stems_tdelay,%a2
        adda.l  %d5,%a2
        .else
        movea.l %d4,%a2
        .if     TRACK_HALF
        move.l  %a2,%d0
        eori.l  #0x400,%d0
        movea.l %d0,%a2
        .endif
        adda.l  %d5,%a2
        .endif
        rts

| ---- a3 = track k's 16 gains for the MAIN now in 0x80005e60 (d5 = k * 0x80)
stems_track_gains:
        move.l  stems_gqn,%d0
        subq.l  #1+GAIN_LAG,%d0
        moveq   #GQ_N-1,%d1
        and.l   %d1,%d0
        move.l  #GQ_FRAME,%d1
        mulu.l  %d1,%d0
        move.l  %d5,%d1
        lsr.l   #1,%d1                      | k * 0x40: the slot's 16 longs
        add.l   %d1,%d0
        movea.l %d0,%a3
        adda.l  #stems_gq,%a3
        rts

| ---- one track's ring frame after the fader, 16-bit (d5 = k * 0x80, a1 = the
| ring). Each sample: floor(g*x / 2^15) on the EMAC (MACSR_FRAC, set by the
| caller), its top 16 bits as floor(g*x / 2^29), limited to 16 bits as
| core 0 limits MAIN to 24 (STEM_REC.md 18.2). Uses d0-d3, a2, a3.
stems_track16:
        bsr.w   stems_track_src
        bsr.w   stems_track_gains
        moveq   #16,%d3
.Lp_s:
        move.l  (%a3)+,%d0
        lsl.l   #8,%d0                      | g << 8
        move.l  (%a2)+,%d1                  | L, left-justified 24 bits
        move.l  (%a2)+,%d2                  | R
        mac.l   %d0,%d1,%acc0
        mac.l   %d0,%d2,%acc1
        movclr.l %acc0,%d1                  | floor(g*x / 2^15)
        movclr.l %acc1,%d2
        moveq   #14,%d0
        asr.l   %d0,%d1                     | floor(g*x / 2^29)
        asr.l   %d0,%d2
        LIM16   %d1
        LIM16   %d2
        swap    %d1
        move.w  %d2,%d1                     | L : R, big-endian halves, as before
        move.l  %d1,(%a1)+
        subq.l  #1,%d3
        bne.s   .Lp_s
        rts

| ---- the one-frame track delay (TRACK_DELAY, STEM_REC.md 18.5) -----------
| Each latched track's block in the half the copy takes is kept for the next
| frame. Uses d0-d2, d4, d6, a0, a2.
stems_tdelay_step:
        .if     TRACK_DELAY
        bsr.w   stems_half
        .if     TRACK_HALF
        eori.l  #0x400,%d4
        .endif
        move.l  stems_mask,%d6
        moveq   #0,%d1                      | k * 0x80
.Lt_k:
        lsr.l   #1,%d6
        bcc.s   .Lt_n
        movea.l %d4,%a2
        adda.l  %d1,%a2
        lea     stems_tdelay,%a0
        adda.l  %d1,%a0
        moveq   #32,%d2
.Lt_c:
        move.l  (%a2)+,(%a0)+
        subq.l  #1,%d2
        bne.s   .Lt_c
.Lt_n:
        addi.l  #0x80,%d1
        cmpi.l  #0x400,%d1
        bne.s   .Lt_k
        .endif
        rts
```
The hook (replace `stems_frame_hook` from its IDLE test to its end):
```asm
        tst.l   stems_state
        beq.w   .Lh_stock           | IDLE
        lea     -48(%sp),%sp
        movem.l %d0-%d7/%a0-%a3,(%sp)
        move.l  stems_state,%d0
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        beq.w   .Lh_out             | FINISHING: the hook adds nothing
        move.l  TRANSPORT,%d2       | running iff exactly 1 (Task 2)
        subq.l  #TRANSPORT_RUNNING,%d2
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .Lh_rec
        tst.l   %d2                 | ARMED
        bne.w   .Lh_out             | still stopped (0 or 2)
        bsr.w   stems_layout        | latch the layout
        moveq   #ST_RECORDING,%d0
        move.l  %d0,stems_state
        bsr.w   stems_tdelay_step   | the take's first frame is the next one: its older blocks
        bra.w   .Lh_out
.Lh_rec:                            | RECORDING
        tst.l   %d2
        beq.s   .Lh_copy
        moveq   #ST_FINISHING,%d0   | the sequencer stopped: 0 (end, rewind) or 2 (STOP key)
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_copy:
        move.l  stems_wr,%d0
        sub.l   stems_rd,%d0        | frames in the ring
        cmp.l   stems_rframes,%d0
        bcs.s   .Lh_room            | fewer than capacity: one more fits
        moveq   #ERR_OVERFLOW,%d0   | the card fell behind: stop at the last whole frame
        move.l  %d0,stems_status
        moveq   #ST_FINISHING,%d0
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_room:
        addq.l  #1,%d0              | frames in the ring with this one
        cmp.l   stems_peak,%d0
        bls.s   .Lh_nopeak
        move.l  %d0,stems_peak      | the take's largest fill (the menu's PEAK row)
.Lh_nopeak:
        movea.l stems_wr_off,%a1
        adda.l  #stems_ring,%a1
        bsr.w   stems_emac_in
        bsr.w   stems_half          | d4
        move.l  stems_mask,%d6
        moveq   #0,%d5              | k * 0x80
.Lh_trk:
        lsr.l   #1,%d6              | C = track k's bit
        bcc.s   .Lh_next
        bsr.w   stems_track16
.Lh_next:
        addi.l  #0x80,%d5
        tst.l   %d6
        bne.s   .Lh_trk
        bsr.w   stems_emac_out
        bsr.w   stems_tdelay_step
        move.l  stems_wr_off,%d0
        add.l   stems_fbytes,%d0
        cmp.l   stems_rlimit,%d0
        bcs.s   .Lh_nowrap
        moveq   #0,%d0
.Lh_nowrap:
        move.l  %d0,stems_wr_off
        move.l  stems_wr,%d0
        addq.l  #1,%d0
        move.l  %d0,stems_wr        | publish after the data
        move.l  %d0,stems_frames
        cmpi.l  #MAX_FRAMES,%d0
        bcs.s   .Lh_out
        moveq   #ST_FINISHING,%d0   | the 60-minute cap
        move.l  %d0,stems_state
.Lh_out:
        movem.l (%sp),%d0-%d7/%a0-%a3
        lea     48(%sp),%sp
.Lh_stock:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts
```
(The edge rule moves every take's first frame one frame later than piece 3's; the menu's state machine is unchanged.)

- [ ] **Step 4: Assemble, disassemble, run**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-post-green bash -c 'make bus REMIX=stems > /dev/null && a=$(m68k-elf-nm out/platform/runtime/runtime.elf | awk "/ stems_track16\$/{print \$1}") && scripts/disasm.sh emac 0x$a 160 | grep -E "mac|movclr|smi|extb" && env STEMS_TEMPLATE="/home/yvez/stemrec5/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems.py stems --only=postfader,postmove,clip,master'`
Expected: `macl %d0,%d1,%acc0`, `macl %d0,%d2,%acc1`, `movclrl %acc0,%d1`, `movclrl %acc1,%d2`, `smi`, `extbl`; then every check PASS. A difference of exactly one frame means `GAIN_LAG` or `TRACK_DELAY` is off by one: rerun Task 4's trace, never shift the check.

- [ ] **Step 5: The checks that compared stems with the read-back**

Each run that compares a take with a track now passes that track's settled gain, read at the run's end (each of these runs holds its levels):
- `tap`: `want = t1_frames(dump, gain_of(log, 0))`, and `got` from the ring as before.
- `wav_check(card_path, nfr, dump, tag, lag_want=STEM_LAG, g=None)`: `want = t1_frames(dump, g)`; every caller passes `g=gain_of(log, 0)` from its own `port()` call.
- `eight`: `want = slot_frames(dump, k, gain_of(log, k))`.
- `mask_take`: `ref = slot_frames(dump, k, gain_of(log, k))`.
With, beside `PRE_ROLL`: `STEM_LAG = PRE_ROLL + 1 - TRACK_DELAY - TRACK_HALF` (the edge rule's frame later, the samples' frames older; Task 4's constants copied here), and in each lag check's detail the lag found. `thru` still checks the read-back itself (g=None).

- [ ] **Step 6: The quick runs, then the whole verifier**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-post-quick VS --only=tap,full,stream,wrap,cap,labels,thru,eight,mask07,maskff`
Expected: all PASS. Commit (Step 7), then `bash .superpowers/v2/wslrun-5 p5-post-check make check-remix REMIX=stems` on the committed tree (tell Yves the log path; about 70 minutes).
Expected: `# exit 0`, every check PASS, `verify_set`'s SKIP only; the counts beside piece 3's 209 in the ledger.

- [ ] **Step 7: Commit**

```bash
git add modules/stems/stems.s tools/verify/verify_stems.py tools/verify/stems_fixture.py
git commit -m "stems: every stem after the fader -- each sample times core 0's own gain on the EMAC, limited as MAIN is; T1.wav equals MAIN sample for sample through LEVEL steps, a take started mid-sweep and a clipped input; the read-back checks compare post-fader

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The take from a file table, the 8 MiB ring, buffers for 14 files

**Files:**
- Modify: `modules/stems/stems.s` (state, `stems_layout`, the hook's copy loop, `stems_start`, `stems_make_file`, the header, `stems_drain`, `stems_flush`, `stems_finish`, `stems_tdelay_step`), `modules/stems/manifest.py` (the regions, the docstring), `tools/verify/verify_stems.py` (`RING_SIZE`, the overflow sizes, check `layout`)

**Interfaces:**
- Consumes: Task 6's hook.
- Produces: `stems_tracks` becomes the source word (bits 0-7 T1-T8, 8 MAIN, 9 CUE, 10 AB, 11 CD; default `0xFF`); `stems_fmt` (bit 0 24 BIT, bit 1 AB STEREO, bit 2 CD STEREO; default 6); latched at the start: `stems_lsrc`, `stems_lfmt`, `stems_nf`, `stems_ftab` (per file: kind << 24 | channels << 16 | bytes per frame; kinds 0-7 T1-T8, 8 MAIN, 9 CUE, 10 AB, 11 CD, 12 A, 13 B, 14 C, 15 D), `stems_fbytes`, `stems_rframes`, `stems_rlimit` (consecutive); `stems_copy_frame`, `stems_hdr_fill`; `RING_SIZE` 0x800000, `SBUF_SIZE` 49,664. In this task the source word's bits 8-11 are masked off at the latch; Task 8 lets them through.

- [ ] **Step 1: Write the failing check**

```python
RING_SIZE = 0x800000
FILE_NAMES = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "MAIN", "CUE", "AB", "CD", "A", "B", "C", "D"]
LAYOUT_CASES = [  # (sources, format, files, ring frame bytes)
    (0x001, 0b110, ["T1"], 64),
    (0x0ff, 0b110, [f"T{k}" for k in range(1, 9)], 512),
    (0x0a5, 0b110, ["T1", "T3", "T6", "T8"], 256),
]


def layout(s):
    """The file table the hook latches at the start edge, for each case: the
    files in order, the ring frame, and the ring's capacity, RING_SIZE //
    frame bytes, with its wrap point."""
    for src, fmt, names, fb in LAYOUT_CASES:
        tag = f"layout{src:03x}{fmt}"
        log, _, _, _, _ = port(s, 120, stop_at=80, tag=tag, mask=None, dump_blocks=False,
                               pokes_before=[(s["stems_tracks"] + 2, src >> 8), (s["stems_tracks"] + 3, src & 0xff),
                                             (s["stems_fmt"] + 3, fmt)],
                               mems=((s["stems_nf"], 4 + 4 * 14, "ftab"), (s["stems_fbytes"], 12, "geom")))
        raw = run_path(tag, "ftab").read_bytes()
        nf = int.from_bytes(raw[:4], "big")
        ftab = [int.from_bytes(raw[4 + 4 * i:8 + 4 * i], "big") for i in range(nf)]
        kinds = [FILE_NAMES[d >> 24] for d in ftab]
        geom = run_path(tag, "geom").read_bytes()
        fbytes, rframes, rlimit = (int.from_bytes(geom[i:i + 4], "big") for i in (0, 4, 8))
        check(f"{tag}: the files", kinds == names, f"{kinds}")
        check(f"{tag}: the ring frame", fbytes == fb == sum(d & 0xffff for d in ftab), f"{fbytes}")
        check(f"{tag}: the capacity", rframes == RING_SIZE // fb and rlimit == rframes * fb,
              f"{rframes} frames, wrap at {rlimit}")
```
Remove the old `RING_SIZE = 0x400000`; double `OVERFLOW_STOP` and `OVERFLOW_FRAMES` (the ring takes twice the frames to fill); add `layout` to the run list and `--only`.

- [ ] **Step 2: Run it to see it fail**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-layout-red VS --only=layout`
Expected: `KeyError: 'stems_fmt'`.

- [ ] **Step 3: The state and the regions**

`stems.s` constants (replacing `RING_SIZE`, `TRACK_BYTES`, `SBUF_SIZE`, `SEC0_BASE`):
```asm
        .equ    RING_SIZE,     0x800000     | = DramRegion stems_ring (piece 5: 8 MiB)
        .equ    MAX_FILES,     14
        .equ    FB_MAX,        96           | one file's frame at most: 16 stereo 24-bit samples
        .equ    SBUF_SIZE,     CHUNK_FRAMES*FB_MAX+512  | one file's stream buffer: a chunk plus a carry
        .equ    SEC0_BASE,     MAX_FILES*SBUF_SIZE      | the sector-0 copies follow the stream buffers
        .equ    K_MAIN,        8            | the kinds after the tracks: MAIN, CUE, AB, CD, then A B C D
        .equ    K_AB,          10
        .equ    K_A,           12
```
State (replacing `stems_mask`, `stems_nt`, `stems_fbytes`, `stems_rframes`, `stems_rlimit`, the three per-file arrays and the tables `rframes_tab`/`rlimit_tab`):
```asm
        .global stems_tracks, stems_fmt, stems_nf, stems_ftab, stems_fbytes
stems_tracks:    .long   0xFF       | the sources: bits 0-7 T1-T8, 8 MAIN, 9 CUE, 10 AB, 11 CD
stems_fmt:       .long   6          | bit 0 24 BIT, bit 1 AB STEREO, bit 2 CD STEREO
stems_lsrc:      .long   0          | the sources latched at the start
stems_lfmt:      .long   0          | the format latched at the start
stems_nf:        .long   0          | files in the take
stems_ftab:      .space  4*MAX_FILES  | per file: kind << 24 | channels << 16 | bytes per frame
stems_fbytes:    .long   0          | a ring frame: the sum of the files' frames
stems_rframes:   .long   0          | the ring's capacity in frames
stems_rlimit:    .long   0          | stems_rframes x stems_fbytes: offsets wrap here
stems_handle:    .space  4*MAX_FILES
stems_slen:      .space  4*MAX_FILES
stems_fpos:      .space  4*MAX_FILES
```
Every `stems_mask` becomes `stems_lsrc`, every `stems_nt` becomes `stems_nf`. In `manifest.py`: `DramRegion("stems_ring", 0x800000)`, `DramRegion("stems_buf", 14 * (512 * 96 + 512) + 14 * 512, align=512)` (702,464 bytes), and in its docstring "a 4 MiB ring" becomes "an 8 MiB ring" and "eight 33,280-byte stream buffers and eight 512-byte sector-0 copies" becomes "fourteen 49,664-byte stream buffers and fourteen 512-byte sector-0 copies".

- [ ] **Step 4: The latch**

Replace `stems_layout`:
```asm
| ---- the layout, latched at the start edge (in the hook) ---------------
| The sources and the format, then the file table in file order (T1..T8,
| MAIN, CUE, AB or A B, CD or C D), the ring frame and the ring's capacity.
| Uses d0-d3 and a0. Offsets past this layout's wrap go to 0.
stems_layout:
        move.l  stems_tracks,%d0
        andi.l  #SRC_BITS,%d0
        bne.s   .Ll_some
        moveq   #1,%d0              | no source: T1
.Ll_some:
        move.l  %d0,stems_lsrc
        move.l  stems_fmt,%d2
        andi.l  #7,%d2
        move.l  %d2,stems_lfmt
        moveq   #32,%d3             | one channel's frame: 16 samples of 2 bytes,
        btst    #0,%d2
        beq.s   .Ll_w
        moveq   #48,%d3             | or of 3 with 24 BIT
.Ll_w:
        lea     stems_ftab,%a0
        moveq   #0,%d1              | the kind
.Ll_src:
        btst    %d1,%d0
        beq.s   .Ll_next
        cmpi.l  #K_AB,%d1
        bcs.s   .Ll_stereo          | a track, MAIN or CUE: stereo
        move.l  %d1,%d2
        subi.l  #K_AB-1,%d2         | the format bit: 1 for AB, 2 for CD
        btst    %d2,stems_lfmt+3
        bne.s   .Ll_stereo          | the pair as one stereo file
        move.l  %d1,%d2             | two mono files: A B (or C D)
        subi.l  #K_AB,%d2
        add.l   %d2,%d2
        addi.l  #K_A,%d2
        swap    %d2
        lsl.l   #8,%d2
        ori.l   #0x10000,%d2
        add.l   %d3,%d2
        move.l  %d2,(%a0)+
        addi.l  #0x01000000,%d2     | the pair's second input
        move.l  %d2,(%a0)+
        bra.s   .Ll_next
.Ll_stereo:
        move.l  %d1,%d2
        swap    %d2
        lsl.l   #8,%d2              | kind << 24
        ori.l   #0x20000,%d2        | two channels
        add.l   %d3,%d2
        add.l   %d3,%d2
        move.l  %d2,(%a0)+
.Ll_next:
        addq.l  #1,%d1
        cmpi.l  #K_AB+2,%d1
        bne.s   .Ll_src
        move.l  %a0,%d0
        subi.l  #stems_ftab,%d0
        lsr.l   #2,%d0
        move.l  %d0,stems_nf
        moveq   #0,%d2              | the ring frame
        lea     stems_ftab,%a0
.Ll_sum:
        moveq   #0,%d1
        move.w  2(%a0),%d1
        add.l   %d1,%d2
        addq.l  #4,%a0
        subq.l  #1,%d0
        bne.s   .Ll_sum
        move.l  %d2,stems_fbytes
        move.l  #RING_SIZE,%d0
        divu.l  %d2,%d0
        move.l  %d0,stems_rframes
        mulu.l  %d2,%d0
        move.l  %d0,stems_rlimit
        cmp.l   stems_wr_off,%d0
        bhi.s   .Ll_wr
        clr.l   stems_wr_off
.Ll_wr:
        cmp.l   stems_rd_off,%d0
        bhi.s   .Ll_rd
        clr.l   stems_rd_off
.Ll_rd:
        rts
```
with `.equ SRC_BITS, 0xff` among the constants (Task 8 makes it `0xfff`). The kind loop's bound `K_AB+2` stops after CD (kind 11).

- [ ] **Step 5: The hook's copy loop, the names, the header, the writer, the finish**

In the hook, replace the loop from `bsr.w stems_half` to `tst.l %d6 / bne.s .Lh_trk` with `bsr.w stems_copy_frame`, and add after `stems_track16`:
```asm
| ---- one ring frame: every file of the table, in order ------------------
| a1 = the ring frame. The caller set the EMAC. Uses d0-d7, a0, a2, a3.
stems_copy_frame:
        bsr.w   stems_half                  | d4
        moveq   #0,%d6                      | file j
.Lc_file:
        cmp.l   stems_nf,%d6
        bcc.s   .Lc_done
        move.l  %d6,%d0
        lsl.l   #2,%d0
        lea     stems_ftab,%a0
        move.l  (%a0,%d0.l),%d7
        move.l  %d7,%d5
        moveq   #24,%d0
        lsr.l   %d0,%d5                     | the kind: a track in this task
        lsl.l   #7,%d5                      | k * 0x80
        bsr.w   stems_track16
        addq.l  #1,%d6
        bra.s   .Lc_file
.Lc_done:
        rts
```
`stems_tdelay_step` reads `stems_lsrc` (its low byte: the tracks). `stems_make_file` takes the file index in d3 and names it from the table:
```asm
| ---- a file path: stems_path + the name of file d3 ----------------------
stems_make_file:
        lea     stems_path,%a0
        lea     stems_fpath,%a1
.Lm_copy:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lm_copy
        subq.l  #1,%a1
        move.l  %d3,%d0
        lsl.l   #2,%d0
        lea     stems_ftab,%a0
        move.l  (%a0,%d0.l),%d0
        moveq   #24,%d1
        lsr.l   %d1,%d0                     | the kind
        cmpi.l  #K_MAIN,%d0
        bcc.s   .Lm_named
        addq.l  #1,%d0                      | T<k+1>
        move.l  %d0,-(%sp)
        pea     fmt_file
        move.l  %a1,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        rts
.Lm_named:
        subq.l  #K_MAIN,%d0
        lsl.l   #2,%d0
        lea     bus_names,%a0
        movea.l (%a0,%d0.l),%a0
.Lm_name:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lm_name
        rts
```
with, beside `fmt_file` (after a `.balign 4`):
```asm
bus_names:  .long   nm_main, nm_cue, nm_ab, nm_cd, nm_a, nm_b, nm_c, nm_d
nm_main:    .asciz  "/MAIN.wav"
nm_cue:     .asciz  "/CUE.wav"
nm_ab:      .asciz  "/AB.wav"
nm_cd:      .asciz  "/CD.wav"
nm_a:       .asciz  "/A.wav"
nm_b:       .asciz  "/B.wav"
nm_c:       .asciz  "/C.wav"
nm_d:       .asciz  "/D.wav"
```
`stems_start`'s loop, from `move.l stems_mask,%d2` to its `bne.w .Ls_trk`, becomes:
```asm
        moveq   #0,%d3              | file j
.Ls_file:
        cmp.l   stems_nf,%d3
        bcc.s   .Ls_all
        bsr.w   stems_make_file
        pea     MODE_W
        pea     stems_fpath
        RAWCALL RAW_OPEN_PTR
        addq.l  #8,%sp
        tst.l   %d0
        ble.w   .Ls_open
        lea     stems_handle,%a0
        move.l  %d0,(%a0,%d3.l*4)
        lea     stems_fpos,%a0
        clr.l   (%a0,%d3.l*4)
        lea     stems_slen,%a0
        moveq   #HDR_SIZE,%d0
        move.l  %d0,(%a0,%d3.l*4)   | the stream starts with the placeholder header
        move.l  %d3,%d1
        bsr.w   stems_sbuf          | a2: stream buffer j
        bsr.w   stems_hdr_fill
        addq.l  #1,stems_nopen
        addq.l  #1,%d3
        bra.s   .Ls_file
.Ls_all:
```
and the header routine:
```asm
| ---- file d3's header into a2: the template with its channels, its bytes a
| second, its block align and its bits, little-endian as RIFF wants -------
stems_hdr_fill:
        lea     stems_hdr,%a0
        movea.l %a2,%a1
        moveq   #HDR_SIZE/4,%d0
.Lf_cp:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   .Lf_cp
        move.l  %d3,%d0
        lsl.l   #2,%d0
        lea     stems_ftab,%a0
        move.l  (%a0,%d0.l),%d1
        swap    %d1
        andi.l  #0xff,%d1                   | channels
        moveq   #2,%d2                      | bytes a sample
        btst    #0,stems_lfmt+3
        beq.s   .Lf_w
        moveq   #3,%d2
.Lf_w:
        move.b  %d1,22(%a2)                 | channels
        move.l  %d1,%d0
        mulu.l  %d2,%d0                     | block align
        move.b  %d0,32(%a2)
        lsl.l   #3,%d2
        move.b  %d2,34(%a2)                 | bits
        move.l  #44100,%d1
        mulu.l  %d1,%d0                     | bytes a second
        BYTEREV 0
        move.l  %d0,28(%a2)
        rts
```
`stems_drain`'s per-frame loop (from `.Ld_frame` to `bcs.s .Ld_trk`) becomes:
```asm
.Ld_frame:
        movea.l stems_rd_off,%a3
        adda.l  #stems_ring,%a3
        moveq   #0,%d4              | file j
.Ld_file:
        move.l  %d4,%d1
        bsr.w   stems_sbuf          | a2 = stream buffer j
        lea     stems_slen,%a0
        move.l  (%a0,%d4.l*4),%d0
        adda.l  %d0,%a2
        lea     stems_ftab,%a1
        move.l  (%a1,%d4.l*4),%d1
        andi.l  #0xffff,%d1         | this file's bytes in the frame
        add.l   %d1,%d0
        move.l  %d0,(%a0,%d4.l*4)
        lsr.l   #2,%d1              | longs: two 16-bit samples each
.Ld_s:                              | [L1 L0 R1 R0] -> [L0 L1 R0 R1]
        move.l  (%a3)+,%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a2)+
        subq.l  #1,%d1
        bne.s   .Ld_s
        addq.l  #1,%d4
        cmp.l   stems_nf,%d4
        bcs.s   .Ld_file
```
`stems_flush` and `stems_close_all` read `stems_nf`. In `stems_finish`, replace `andi.l #-4,%d3` with:
```asm
        move.l  %d4,%d0
        lsl.l   #2,%d0
        lea     stems_ftab,%a0
        move.l  (%a0,%d0.l),%d1
        swap    %d1
        andi.l  #0xff,%d1                   | channels
        moveq   #2,%d0
        btst    #0,stems_lfmt+3
        beq.s   .Lz_al
        moveq   #3,%d0
.Lz_al:
        mulu.l  %d0,%d1                     | block align
        move.l  %d3,%d0
        divu.l  %d1,%d0
        mulu.l  %d1,%d0
        move.l  %d0,%d3                     | whole frames of this file only
```

- [ ] **Step 6: Run, then commit**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-layout-green bash -c 'make bus REMIX=stems | grep -iE "stems_ring|stems_buf|reserve|refus"; env STEMS_TEMPLATE="/home/yvez/stemrec5/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems.py stems --only=layout,full,stream,wrap,overflow,eight,mask07,maskff,postfader'`
Expected: the build's DRAM lines show `stems_ring` 8 MiB and `stems_buf` 702,464 B inside the reserve, no refusal; every check PASS.
```bash
git add modules/stems/stems.s modules/stems/manifest.py tools/verify/verify_stems.py
git commit -m "stems: the take from a file table latched at the start -- sources, format, files in order, the ring frame and its capacity by division; the ring 8 MiB, the writer's buffers for 14 files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: MAIN, CUE and the inputs, stereo or mono (gate 4)

**Files:**
- Modify: `modules/stems/stems.s` (`SRC_BITS`, `stems_bus16`, the copy dispatch), `tools/verify/verify_stems.py` (checks `sources`, `mono`, `all14`; `LAYOUT_CASES`)

**Interfaces:**
- Consumes: Task 4's `IN_AB_OFF`, `IN_CD_OFF`, `IN_A_IS_LEFT`; Task 7's file table.
- Produces: `stems_bus16` (d5 = the kind 8-15, a1 = the ring), `bus_src` (the first long of each kind in channel 6's buffer); in `verify_stems.py`: `capture(prefix, chans)`, `wav16(data)`, `wav_fmt(data)`, `find_at(got, ref)`.

- [ ] **Step 1: Write the failing checks**

```python
def capture(prefix, chans):
    """TX0 ring words `chans` of core 0's 24-bit --audio-out WAV, interleaved."""
    import wave
    with wave.open(f"{prefix}_core0.wav") as w:
        n, c = w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    return [int.from_bytes(raw[(i * c + ch) * 3:(i * c + ch) * 3 + 3], "little", signed=True)
            for i in range(n) for ch in chans]


def wav_fmt(data):
    """(channels, bytes a second, block align, bits, data bytes) of a WAV header."""
    ch, rate, brate, align, bits = struct.unpack_from("<HIIHH", data, 22)
    return ch, brate, align, bits, struct.unpack_from("<I", data, 40)[0]


def wav16(data):
    return list(struct.unpack_from(f"<{(len(data) - 44) // 2}h", data, 44))


def find_at(got, ref, width=64):
    """The offset of `got` inside `ref`, found from got's first sound and then
    required at every sample; None when either fails."""
    loud = next((i for i, v in enumerate(got) if v), None)
    if loud is None:
        return None
    key = got[loud:loud + width]
    pos = next((i for i in range(len(ref) - width) if ref[i:i + width] == key), None)
    if pos is None or pos < loud or ref[pos - loud:pos - loud + len(got)] != got:
        return None
    return pos - loud


def sources(s):
    """Gate 4: on the one-THRU fixture with T1 sent to CUE, a take of T1,
    MAIN, CUE and AB: four files in that order; MAIN.wav equals T1.wav sample
    for sample (only T1 reaches MAIN), and both are aligned in time by
    construction; CUE.wav is the cue bus (TX0 words 0 and 1) at one offset;
    AB.wav carries inputs A and B (the input WAV's channels 2 and 3), each a
    fixed gain of its own input at one lag."""
    aud = run_path("sources", "aud")
    log, dump, card, words, _ = port(s, 520, stop_at=340, tag="sources", fixture=FIXTURE_THRU1, mask=None,
                                     pokes_before=[(s["stems_tracks"] + 2, 0x07), (s["stems_tracks"] + 3, 0x01),
                                                   (CUE_T1, 127)],
                                     extra=("--audio-out", str(aud)))
    files = take_files(card, FIXTURE_THRU1)
    names = [n.upper() for n, _ in files]
    check("sources: T1, MAIN, CUE and AB, nothing else", sorted(names) == ["AB.WAV", "CUE.WAV", "MAIN.WAV", "T1.WAV"],
          f"{names}")
    f = {n.upper(): d for n, d in files}
    if len(f) != 4:
        return
    check("sources: every header is 16-bit stereo",
          all(wav_fmt(d)[:4] == (2, 176400, 4, 16) for d in f.values()), f"{[wav_fmt(d)[:4] for d in f.values()]}")
    check("sources: MAIN.wav equals T1.wav, every sample (only T1 reaches MAIN)",
          wav16(f["MAIN.WAV"]) == wav16(f["T1.WAV"]) and any(wav16(f["T1.WAV"])))
    cue = [v >> 8 for v in capture(aud, (0, 1))]
    off = find_at(wav16(f["CUE.WAV"]), cue)
    check("sources: CUE.wav equals the cue bus at one offset, and holds sound",
          off is not None and any(wav16(f["CUE.WAV"])), f"offset {off}")
    ab = wav16(f["AB.WAV"])
    import wave
    with wave.open(json.loads(FIXTURE_THRU1.read_text())["audio_in"]) as w:
        raw = w.readframes(w.getnframes())
    ins = list(struct.unpack(f"<{len(raw) // 2}h", raw))
    for side, ch in (("A", 2), ("B", 3)):
        got = ab[0 if side == "A" else 1::2]
        src = ins[ch::4]
        r = best_corr(got, src)
        check(f"sources: AB.wav's {'left' if side == 'A' else 'right'} channel is input {side}", r > 0.999, f"r {r:.6f}")


def best_corr(got, src, lags=range(0, 4000)):
    """The highest normalised correlation of `got` (its loud middle 4,096
    samples) against `src` over the lags: 1.0 for a scaled copy."""
    import math
    loud = next((i for i, v in enumerate(got) if v), 0)
    g = got[loud + 512:loud + 512 + 4096]
    if len(g) < 4096:
        return 0.0
    gn = math.sqrt(sum(x * x for x in g)) or 1.0
    best = 0.0
    for L in lags:
        seg = src[L:L + 4096]
        if len(seg) < 4096:
            break
        sn = math.sqrt(sum(x * x for x in seg)) or 1.0
        best = max(best, sum(a * b for a, b in zip(g, seg)) / (gn * sn))
    return best


def mono(s):
    """AB STEREO off: A.wav and B.wav, mono, equal to the stereo take's left
    and right channels of the same deterministic run."""
    log, dump, card, words, _ = port(s, 520, stop_at=340, tag="mono", fixture=FIXTURE_THRU1, mask=None,
                                     pokes_before=[(s["stems_tracks"] + 2, 0x04), (s["stems_tracks"] + 3, 0x01),
                                                   (s["stems_fmt"] + 3, 0b100)])
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU1)}
    check("mono: T1, A and B", sorted(f) == ["A.WAV", "B.WAV", "T1.WAV"], f"{sorted(f)}")
    sf = {n.upper(): d for n, d in take_files(run_path("sources", "img"), FIXTURE_THRU1)}
    if len(f) != 3 or "AB.WAV" not in sf:
        return
    ab = wav16(sf["AB.WAV"])
    check("mono: A.wav and B.wav are one channel, 16 bits",
          wav_fmt(f["A.WAV"])[:4] == wav_fmt(f["B.WAV"])[:4] == (1, 88200, 2, 16))
    check("mono: A.wav is AB.wav's left, B.wav its right, every sample",
          wav16(f["A.WAV"]) == ab[0::2] and wav16(f["B.WAV"]) == ab[1::2])


def all14(s):
    """Review Focus 4: every source on, both pairs mono, on the eight-track
    THRU fixture: 14 files in order, each header its own, each length its
    frames; and the eight stems sum to MAIN within one step per track."""
    log, dump, card, words, _ = port(s, THRU_FRAMES, stop_at=THRU_STOP, tag="all14", fixture=FIXTURE_THRU,
                                     mask=None, pokes_before=[(s["stems_tracks"] + 2, 0x0f),
                                                              (s["stems_tracks"] + 3, 0xff),
                                                              (s["stems_fmt"] + 3, 0b000)])
    st, status, _, wr, rd, nfr = words
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU)}
    want = [f"T{k}.WAV" for k in range(1, 9)] + ["MAIN.WAV", "CUE.WAV", "A.WAV", "B.WAV", "C.WAV", "D.WAV"]
    check("all14: fourteen files", sorted(f) == sorted(want), f"{sorted(f)}")
    check("all14: IDLE, no error", st == ST_IDLE and status == 0, f"state {st}, status {status}")
    for n, d in f.items():
        ch = 1 if n in ("A.WAV", "B.WAV", "C.WAV", "D.WAV") else 2
        check(f"all14: {n}'s header and length", wav_fmt(d) == (ch, 88200 * ch, 2 * ch, 16, 32 * ch * nfr)
              and len(d) == 44 + 32 * ch * nfr, f"{wav_fmt(d)}, {len(d)} bytes, {nfr} frames")
    if len(f) == 14:
        stems = [wav16(f[f"T{k}.WAV"]) for k in range(1, 9)]
        main = wav16(f["MAIN.WAV"])
        worst = max(abs(m - sum(t[i] for t in stems)) for i, m in enumerate(main))
        check("all14: the eight stems sum to MAIN within 8 steps at 16 bits", worst <= 8, f"worst {worst}")
```
with `CUE_T1 = 0x80000c51` (T1's cue level byte, `docs/firmware/MIDI.md`: CC 47) beside the constants. Add `(0x701, 0b110, ["T1", "MAIN", "CUE", "AB"], 256)`, `(0x401, 0b100, ["T1", "A", "B"], 128)` and `(0xfff, 0b000, [f"T{k}" for k in range(1, 9)] + ["MAIN", "CUE", "A", "B", "C", "D"], 768)` to `LAYOUT_CASES`, and `sources`, `mono`, `all14` to the run list (`mono` after `sources`: it reads `sources`' card) and to `--only`.

- [ ] **Step 2: Run them to see them fail**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-src-red VS --only=layout,sources`
Expected: the three new `layout` cases FAIL (bits 8-11 are masked off: the file lists have tracks only) and `sources: T1, MAIN, CUE and AB` FAIL.

- [ ] **Step 3: The bus copy**

`stems.s`, among the stock facts (as Task 4 measured):
```asm
        .equ    BUS,           0x80005e60   | channel 6's buffer: MAIN +0x00, CUE +0x80 (STEM_REC.md 18.6)
        .equ    IN_AB_OFF,     0x100        | inputs A and B (18.7)
        .equ    IN_CD_OFF,     0x180        | inputs C and D (18.7)
        .equ    IN_A_IS_LEFT,  1            | A (and C) in the pair's first long (18.7)
        .equ    IN_A_OFF,      4-4*IN_A_IS_LEFT
        .equ    IN_B_OFF,      4*IN_A_IS_LEFT
```
`SRC_BITS` becomes `0xfff`. After `stems_track16`:
```asm
| ---- MAIN, CUE or an input, 16-bit: d5 = the kind (8-15), a1 = the ring.
| From channel 6's buffer as this frame holds it (STEM_REC.md 18.6-18.7):
| 16 samples of left-justified 24-bit longs, L then R. Uses d0-d3, a0, a2.
stems_bus16:
        move.l  %d5,%d0
        subq.l  #K_MAIN,%d0
        lsl.l   #2,%d0
        lea     bus_src,%a0
        movea.l (%a0,%d0.l),%a2             | the first long to take
        moveq   #16,%d3
        cmpi.l  #K_A,%d5
        bcc.s   .Lb_mono
.Lb_st:
        move.l  (%a2)+,%d1                  | L
        move.l  (%a2)+,%d2                  | R
        swap    %d2
        move.w  %d2,%d1                     | L's top 16 : R's top 16
        move.l  %d1,(%a1)+
        subq.l  #1,%d3
        bne.s   .Lb_st
        rts
.Lb_mono:
        move.l  (%a2),%d1
        swap    %d1
        move.w  %d1,(%a1)+                  | the channel's top 16
        addq.l  #8,%a2
        subq.l  #1,%d3
        bne.s   .Lb_mono
        rts
```
and with the other tables (after a `.balign 4`):
```asm
bus_src:    .long   BUS, BUS+0x80, BUS+IN_AB_OFF, BUS+IN_CD_OFF
            .long   BUS+IN_AB_OFF+IN_A_OFF, BUS+IN_AB_OFF+IN_B_OFF, BUS+IN_CD_OFF+IN_A_OFF, BUS+IN_CD_OFF+IN_B_OFF
```
In `stems_copy_frame`, after `lsr.l %d0,%d5`:
```asm
        cmpi.l  #K_MAIN,%d5
        bcc.s   .Lc_bus
        lsl.l   #7,%d5                      | k * 0x80
        bsr.w   stems_track16
        bra.s   .Lc_next
.Lc_bus:
        bsr.w   stems_bus16
.Lc_next:
```
(replacing its two lines `lsl.l #7,%d5` and `bsr.w stems_track16`; `addq.l #1,%d6` follows `.Lc_next`).

- [ ] **Step 4: Run, then commit**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-src-green VS --only=layout,sources,mono,all14,postfader,full`
Expected: every check PASS. `CUE.wav … holds sound` failing means the cue byte didn't send T1 to the cue bus: find the cue mover as Task 2 Step 4 found the LEVEL mover (CC 47, or the cue key), record it, and rerun; never drop the sound requirement.
```bash
git add modules/stems/stems.s tools/verify/verify_stems.py
git commit -m "stems: MAIN, CUE and the inputs -- from channel 6's buffer, the inputs stereo (AB.wav, CD.wav) or mono (A, B, C, D); MAIN.wav equals T1.wav when T1 alone sounds, CUE.wav the cue bus, AB.wav inputs A and B; fourteen files in one take (gate 4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: 24 bits (gate 5, and gate 2 at full precision)

**Files:**
- Modify: `modules/stems/stems.s` (`LIM24`, `PACK6`, `stems_track24`, `stems_bus24`, the copy dispatch, the writer's 24-bit order), `tools/verify/verify_stems.py` (checks `w24`, `w16v24`, `all14w`, `overflow24`)

**Interfaces:**
- Consumes: the file table's widths (Task 7), `stems_bus16`'s source table.
- Produces: `stems_track24`, `stems_bus24`; in `verify_stems.py`: `wav24(data)`.

- [ ] **Step 1: Write the failing checks**

```python
def wav24(data):
    n = (len(data) - 44) // 3
    return [int.from_bytes(data[44 + 3 * i:47 + 3 * i], "little", signed=True) for i in range(n)]


def w24(s):
    """Gate 5: a 24-bit take on the one-THRU fixture with T1's LEVEL stepped:
    T1.wav is 24-bit stereo and equals MAIN's 24 bits at every sample."""
    steps, midi = level_steps(LEVEL_STEPS)
    aud = run_path("w24", "aud")
    log, dump, card, words, _ = port(s, 520, stop_at=340, tag="w24", fixture=FIXTURE_THRU1,
                                     pokes_before=[(s["stems_fmt"] + 3, 0b111)], steps=steps, midi_lines=midi,
                                     extra=("--audio-out", str(aud)))
    st, status, _, wr, rd, nfr = words
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU1)}
    d = f.get("T1.WAV")
    check("w24: T1.wav is 24-bit stereo, its length its frames",
          d is not None and wav_fmt(d) == (2, 264600, 6, 24, 96 * nfr), f"{wav_fmt(d) if d else None}, {nfr} frames")
    if d:
        off = find_at(wav24(d), capture(aud, (2, 3)))
        check("w24: every sample of T1.wav equals MAIN's 24 bits", off is not None, f"offset {off}")


def w16v24(s):
    """The same deterministic run at 16 bits: every sample is the 24-bit
    take's top 16 bits."""
    steps, midi = level_steps(LEVEL_STEPS)
    log, dump, card, words, _ = port(s, 520, stop_at=340, tag="w16", fixture=FIXTURE_THRU1,
                                     steps=steps, midi_lines=midi)
    a = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU1)}.get("T1.WAV")
    b = {n.upper(): d for n, d in take_files(run_path("w24", "img"), FIXTURE_THRU1)}.get("T1.WAV")
    check("w16v24: the 16-bit take is the 24-bit take's top 16 bits, every sample",
          a is not None and b is not None and wav16(a) == [v >> 8 for v in wav24(b)])


def all14w(s):
    """Review Focus 4 at 24 bits, and gate 2 at full precision: fourteen
    24-bit files; MAIN minus the sum of the eight stems is 0 to 7 at every
    sample (each stem's floor against the mix's one floor)."""
    log, dump, card, words, _ = port(s, THRU_FRAMES, stop_at=THRU_STOP, tag="all14w", fixture=FIXTURE_THRU,
                                     mask=None, pokes_before=[(s["stems_tracks"] + 2, 0x0f),
                                                              (s["stems_tracks"] + 3, 0xff),
                                                              (s["stems_fmt"] + 3, 0b001)])
    st, status, _, wr, rd, nfr = words
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU)}
    check("all14w: fourteen files, IDLE, no error", len(f) == 14 and st == ST_IDLE and status == 0,
          f"{sorted(f)}, state {st}, status {status}")
    for n, d in f.items():
        ch = 1 if n in ("A.WAV", "B.WAV", "C.WAV", "D.WAV") else 2
        check(f"all14w: {n}'s header and length", wav_fmt(d) == (ch, 132300 * ch, 3 * ch, 24, 48 * ch * nfr)
              and len(d) == 44 + 48 * ch * nfr, f"{wav_fmt(d)}, {len(d)} bytes")
    if len(f) == 14:
        stems = [wav24(f[f"T{k}.WAV"]) for k in range(1, 9)]
        diffs = [m - sum(t[i] for t in stems) for i, m in enumerate(wav24(f["MAIN.WAV"]))]
        check("all14w: MAIN minus the stems' sum is 0 to 7, every sample",
              diffs and min(diffs) >= 0 and max(diffs) <= 7, f"{min(diffs) if diffs else None}..{max(diffs) if diffs else None}")


def overflow24(s):
    """Everything on at 24 bits on a slow emulated card: the ring fills, the
    take stops with RING FULL, and every file holds a whole number of frames
    under a header that says so."""
    log, dump, card, words, _ = port(s, 6000, tag="overflow24", fixture=FIXTURE_THRU, mask=None, dump_blocks=False,
                                     pokes_before=[(s["stems_tracks"] + 2, 0x0f), (s["stems_tracks"] + 3, 0xff),
                                                   (s["stems_fmt"] + 3, 0b111)],
                                     extra=("--ata-latency", str(SLOW_LATENCY)), load_ms=60000)
    st, status, _, wr, rd, nfr = words
    check("overflow24: RING FULL", status == ERR_OVERFLOW, f"status {status}")
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU)}
    check("overflow24: every file whole, its header its length",
          len(f) == 12 and all(wav_fmt(d)[4] == len(d) - 44 and (len(d) - 44) % wav_fmt(d)[2] == 0
                               for d in f.values()), f"{len(f)} files")
```
Add `(0x001, 0b111, ["T1"], 96)` and `(0xfff, 0b001, [f"T{k}" for k in range(1, 9)] + ["MAIN", "CUE", "A", "B", "C", "D"], 1152)` to `LAYOUT_CASES`; `w24`, `w16v24` (after `w24`), `all14w` and `overflow24` to the run list and `--only` (`overflow24` with the `--long` runs).

- [ ] **Step 2: Run them to see them fail**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-w24-red VS --only=w24`
Expected: `w24: T1.wav is 24-bit stereo` FAIL (the header says 24 bits, the data is 16-bit samples).

- [ ] **Step 3: The 24-bit paths**

Macros, after `LIM16`:
```asm
| A value limited to 24 bits. Uses d0.
        .macro  LIM24 reg
        move.l  \reg,%d0
        addi.l  #0x800000,%d0
        cmpi.l  #0xffffff,%d0
        bls.s   .Ll24\@
        tst.l   \reg
        smi     \reg
        extb.l  \reg
        eori.l  #0x7fffff,\reg              | 0x7fffff above, -0x800000 below
.Ll24\@:
        .endm
| Two 24-bit values (right-justified) as six bytes, big-endian, at (a1)+:
| three word stores, so every store stays word-aligned. Uses d0; changes a.
        .macro  PACK6 a, b
        move.l  \a,%d0
        asr.l   #8,%d0
        move.w  %d0,(%a1)+                  | a's top 16
        lsl.l   #8,\a
        move.l  \b,%d0
        swap    %d0                         | b's top byte, in the low byte
        move.b  %d0,\a
        move.w  \a,(%a1)+                   | a's low 8 : b's top 8
        move.w  \b,(%a1)+                   | b's low 16
        .endm
```
Routines, after `stems_bus16`:
```asm
| ---- one track's ring frame after the fader, 24-bit: as stems_track16, but
| the whole 24-bit share, floor(g*x / 2^21), limited as MAIN is.
stems_track24:
        bsr.w   stems_track_src
        bsr.w   stems_track_gains
        moveq   #16,%d3
.Lq_s:
        move.l  (%a3)+,%d0
        lsl.l   #8,%d0
        move.l  (%a2)+,%d1
        move.l  (%a2)+,%d2
        mac.l   %d0,%d1,%acc0
        mac.l   %d0,%d2,%acc1
        movclr.l %acc0,%d1
        movclr.l %acc1,%d2
        asr.l   #6,%d1                      | floor(g*x / 2^21)
        asr.l   #6,%d2
        LIM24   %d1
        LIM24   %d2
        PACK6   %d1,%d2
        subq.l  #1,%d3
        bne.s   .Lq_s
        rts

| ---- MAIN, CUE or an input, 24-bit (d5 = the kind) ----------------------
stems_bus24:
        move.l  %d5,%d0
        subq.l  #K_MAIN,%d0
        lsl.l   #2,%d0
        lea     bus_src,%a0
        movea.l (%a0,%d0.l),%a2
        cmpi.l  #K_A,%d5
        bcc.s   .Lu_mono
        moveq   #16,%d3
.Lu_st:
        move.l  (%a2)+,%d1
        move.l  (%a2)+,%d2
        asr.l   #8,%d1                      | 24 bits, right-justified
        asr.l   #8,%d2
        PACK6   %d1,%d2
        subq.l  #1,%d3
        bne.s   .Lu_st
        rts
.Lu_mono:
        moveq   #8,%d3                      | two samples to six bytes
.Lu_mo:
        move.l  (%a2),%d1
        move.l  8(%a2),%d2
        asr.l   #8,%d1
        asr.l   #8,%d2
        PACK6   %d1,%d2
        lea     16(%a2),%a2
        subq.l  #1,%d3
        bne.s   .Lu_mo
        rts
```
`stems_copy_frame`'s dispatch picks the width (replace from `cmpi.l #K_MAIN,%d5` to `.Lc_next:`):
```asm
        btst    #0,stems_lfmt+3
        bne.s   .Lc_24
        cmpi.l  #K_MAIN,%d5
        bcc.s   .Lc_bus
        lsl.l   #7,%d5
        bsr.w   stems_track16
        bra.s   .Lc_next
.Lc_bus:
        bsr.w   stems_bus16
        bra.s   .Lc_next
.Lc_24:
        cmpi.l  #K_MAIN,%d5
        bcc.s   .Lc_bus24
        lsl.l   #7,%d5
        bsr.w   stems_track24
        bra.s   .Lc_next
.Lc_bus24:
        bsr.w   stems_bus24
.Lc_next:
```
`stems_drain`, before `lsr.l #2,%d1` in the per-file loop:
```asm
        btst    #0,stems_lfmt+3
        beq.s   .Ld_16
        moveq   #6,%d0
        divu.l  %d0,%d1                     | groups of two 24-bit samples
.Ld_g:                                      | [a2 a1 a0 b2 b1 b0] -> [a0 a1 a2 b0 b1 b2]
        move.b  2(%a3),(%a2)+
        move.b  1(%a3),(%a2)+
        move.b  (%a3),(%a2)+
        move.b  5(%a3),(%a2)+
        move.b  4(%a3),(%a2)+
        move.b  3(%a3),(%a2)+
        addq.l  #6,%a3
        subq.l  #1,%d1
        bne.s   .Ld_g
        bra.s   .Ld_fnext
.Ld_16:
```
with `.Ld_fnext:` placed before `addq.l #1,%d4` (the 16-bit loop falls through to it). The header (`stems_hdr_fill`) and the finish's rounding already follow the width (Task 7).

- [ ] **Step 4: Assemble, disassemble, run**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-w24-green bash -c 'make bus REMIX=stems > /dev/null && a=$(m68k-elf-nm out/platform/runtime/runtime.elf | awk "/ stems_track24\$/{print \$1}") && scripts/disasm.sh emac 0x$a 200 | grep -E "mac|movclr|asrl|movew" | head -20 && env STEMS_TEMPLATE="/home/yvez/stemrec5/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems.py stems --only=layout,w24,w16v24,all14w,all14,postfader'`
Expected: the forms as intended (`asrl #6`, three `movew` stores per sample pair); every check PASS. Then `--long --only=overflow24`: PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/stems/stems.s tools/verify/verify_stems.py
git commit -m "stems: 24-bit takes -- the whole 24-bit share of MAIN and the buses' 24 bits, six bytes a pair in the ring, little-endian on the card; T1.wav equals MAIN's 24 bits, the 16-bit take is its top 16, the stems sum to MAIN within 0..7, and RING FULL keeps every file whole (gates 2 and 5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: The STEMS list's new rows (gate 6)

**Files:**
- Modify: `modules/stems/stems.s` (the rows, the labels, `stems_source_action`, `stems_switch_action`, `ROW_PEAK`, `MENU_ROWS`), `tools/verify/verify_stems.py` (`menu_static`, `MENU_ROWS`, `ROW_PEAK`), `tools/verify/verify_stems_menu.py` (the walk, `TEXTS`)

**Interfaces:**
- Consumes: `stems_tracks` (the source word) and `stems_fmt` from Task 7.
- Produces: rows 0 REC, 1 status, 2-9 T1-T8, 10 MAIN, 11 CUE, 12 AB, 13 CD, 14 AB STEREO, 15 CD STEREO, 16 24 BIT, 17 PEAK; `ROW_SRC0 = 2`, `ROW_SW0 = 14`, `ROW_PEAK = 17`, `MENU_ROWS = 18`; `stems_source_action` (rows 2-13), `stems_switch_action` (rows 14-16).

- [ ] **Step 1: Write the failing checks**

`verify_stems.py`: `MENU_ROWS = 18`, `ROW_PEAK = 17`, and in `menu_static`:
```python
    check("the STEMS list ships filled in: 18 rows, 7 visible, its rows",
          lst == [MENU_ROWS, 0, 0, 0, MENU_VISIBLE, MENU_ROWS, s["stems_rows"]], f"{[hex(x) for x in lst]}")
    rows = [[lng(s["stems_rows"] + ROW_LEN * r + 4 * k) for k in range(6)] for r in range(MENU_ROWS)]
    check("REC runs stems_action; T1-T8 and MAIN to CD stems_source_action; the three switches "
          "stems_switch_action; the status and PEAK are headings",
          [r[2] for r in rows] == [s["stems_action"], 0] + [s["stems_source_action"]] * 12
          + [s["stems_switch_action"]] * 3 + [0], f"{[hex(r[2]) for r in rows]}")
    texts = [txt(r[0]) for r in rows]
    check("the rows ship with the boot defaults",
          texts == ["REC", "READY"] + [f"T{k} [X]" for k in range(1, 9)]
          + ["MAIN [ ]", "CUE [ ]", "AB [ ]", "CD [ ]", "AB STEREO [X]", "CD STEREO [X]", "24 BIT [ ]", "PEAK 0%"],
          f"{texts}")
```
(the two old checks they replace go). `verify_stems_menu.py`: add to `TEXTS` every new label, on and off (`MAIN [X]`, `MAIN [ ]`, `CUE [X]`, `CUE [ ]`, `AB [X]`, `AB [ ]`, `CD [X]`, `CD [ ]`, `AB STEREO [X]`, `AB STEREO [ ]`, `CD STEREO [X]`, `CD STEREO [ ]`, `24 BIT [X]`, `24 BIT [ ]`); in `walk()` replace the "DOWN reaches T8" block with:
```python
        walked = []
        for _ in range(16):
            p.press("down")
            walked.append(sel(lst))
        shot("last")
        last = 16
        vs.check(f"{model}: DOWN reaches 24 BIT and stays there, never on the PEAK row",
                 walked == list(range(vs.ROW_TRK0, last + 1)) + [last], f"{walked}")
        for _ in range(last - vs.ROW_TRK0):
            p.press("up")                               # back to T1
```
and after "turning every track off leaves the last one on":
```python
        p.press("down")                                 # T8 -> MAIN (row 10)
        p.press(ENTER)                                  # MAIN on
        p.press("up")                                   # T8
        p.press(ENTER)                                  # T8 off: MAIN keeps a source
        p.press("down")                                 # MAIN
        p.press(ENTER)                                  # MAIN off: refused, the last source
        left = p.long(s["stems_tracks"]) & 0xFFF
        vs.check(f"{model}: with MAIN on, T8 can go off, and the last source stays on",
                 left == 0x100, f"sources {left:#05x}")
        p.press("up")                                   # T8
        p.press(ENTER)                                  # T8 on again; MAIN stays on for the take
        for _ in range(7):
            p.press("down")                             # T8 (row 9) -> 24 BIT (row 16)
        p.press(ENTER)
        p.press(ENTER)                                  # 24 BIT on, then off
        p.press("up")                                   # CD STEREO (row 15)
        p.press(ENTER)                                  # off
        fmt = p.long(s["stems_fmt"]) & 7
        t = texts(p, s)
        vs.check(f"{model}: the switches flip and say so",
                 fmt == 0b010 and t[14:17] == ["AB STEREO [X]", "CD STEREO [ ]", "24 BIT [ ]"],
                 f"fmt {fmt:03b}, {t[14:17]}")
        p.press(ENTER)                                  # CD STEREO on again
        for _ in range(6):
            p.press("up")                               # CD STEREO (row 15) -> T8 (row 9)
```
The take's file check at the end becomes `names == ["MAIN.WAV"] + [f"T{k}.WAV" for k in (1, 2, 4, 5, 6, 7, 8)]` (`take_files` sorts by name) and its label says "seven tracks and MAIN, T3's missing". Update the module docstring's list to match.

- [ ] **Step 2: Run them to see them fail**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-menu-red VS --static`
Expected: the list and rows checks FAIL (11 rows).

- [ ] **Step 3: The rows and the actions**

`stems.s`: `MENU_ROWS` 18, `ROW_PEAK` 17, and `.equ ROW_SRC0, 2`, `.equ ROW_SW0, 14`, `.equ NSRC, 12`. The rows:
```asm
stems_rows:                                 | label, window, action, getter, child, page id
        .long   lbl_rec,   0, stems_action, 0, 0, 0
        .long   lbl_ready, 0, 0, 0, 0, 0    | the status: action 0, a heading the cursor skips
        .long   trk1_on, 0, stems_source_action, 0, 0, 0
        .long   trk2_on, 0, stems_source_action, 0, 0, 0
        .long   trk3_on, 0, stems_source_action, 0, 0, 0
        .long   trk4_on, 0, stems_source_action, 0, 0, 0
        .long   trk5_on, 0, stems_source_action, 0, 0, 0
        .long   trk6_on, 0, stems_source_action, 0, 0, 0
        .long   trk7_on, 0, stems_source_action, 0, 0, 0
        .long   trk8_on, 0, stems_source_action, 0, 0, 0
        .long   main_off, 0, stems_source_action, 0, 0, 0
        .long   cue_off, 0, stems_source_action, 0, 0, 0
        .long   ab_off, 0, stems_source_action, 0, 0, 0
        .long   cd_off, 0, stems_source_action, 0, 0, 0
        .long   abst_on, 0, stems_switch_action, 0, 0, 0
        .long   cdst_on, 0, stems_switch_action, 0, 0, 0
        .long   b24_off, 0, stems_switch_action, 0, 0, 0
        .long   lbl_peak0, 0, 0, 0, 0, 0    | PEAK: a heading, the last row, which the cursor never reaches
```
The label tables (replacing `trk_on`/`trk_off`):
```asm
src_on:   .long   trk1_on, trk2_on, trk3_on, trk4_on, trk5_on, trk6_on, trk7_on, trk8_on
          .long   main_on, cue_on, ab_on, cd_on
src_off:  .long   trk1_off, trk2_off, trk3_off, trk4_off, trk5_off, trk6_off, trk7_off, trk8_off
          .long   main_off, cue_off, ab_off, cd_off
sw_bit:   .long   1, 2, 0                   | rows 14-16: AB STEREO, CD STEREO, 24 BIT in stems_fmt
sw_on:    .long   abst_on, cdst_on, b24_on
sw_off:   .long   abst_off, cdst_off, b24_off
main_on:  .asciz "MAIN [X]"
main_off: .asciz "MAIN [ ]"
cue_on:   .asciz "CUE [X]"
cue_off:  .asciz "CUE [ ]"
ab_on:    .asciz "AB [X]"
ab_off:   .asciz "AB [ ]"
cd_on:    .asciz "CD [X]"
cd_off:   .asciz "CD [ ]"
abst_on:  .asciz "AB STEREO [X]"
abst_off: .asciz "AB STEREO [ ]"
cdst_on:  .asciz "CD STEREO [X]"
cdst_off: .asciz "CD STEREO [ ]"
b24_on:   .asciz "24 BIT [X]"
b24_off:  .asciz "24 BIT [ ]"
```
`stems_track_action` becomes `stems_source_action`, and `stems_switch_action` follows it:

```asm
        .global stems_source_action
stems_source_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  stems_list+LIST_SEL,%d3
        subq.l  #ROW_SRC0,%d3               | source k, 0..11
        moveq   #NSRC,%d0
        cmp.l   %d0,%d3
        bcc.s   .Lk_out
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        move.l  stems_state,%d1
        moveq   #ST_RECORDING,%d0
        cmp.l   %d0,%d1
        bcc.s   .Lk_keep                    | RECORDING or FINISHING: locked
        moveq   #1,%d0
        lsl.l   %d3,%d0                     | the source's bit
        move.l  stems_tracks,%d1
        eor.l   %d0,%d1
        movea.l %d1,%a0                     | the new word
        andi.l  #0xfff,%d1
        beq.s   .Lk_keep                    | the last source on: it stays on
        move.l  %a0,stems_tracks
        move.w  %d2,%sr
        lea     src_off,%a1
        move.l  %a0,%d1
        and.l   %d0,%d1
        beq.s   .Lk_label
        lea     src_on,%a1
.Lk_label:
        movea.l (%a1,%d3.l*4),%a0           | the label
        move.l  %d3,%d1
        addq.l  #ROW_SRC0,%d1
        moveq   #ROW_LEN,%d0
        mulu.l  %d0,%d1
        movea.l %d1,%a1
        adda.l  #stems_rows,%a1
        move.l  %a0,(%a1)                   | the row's label pointer
        bra.s   .Lk_out
.Lk_keep:
        move.w  %d2,%sr
.Lk_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- a switch row's action (AB STEREO, CD STEREO, 24 BIT): action(0) -------
        .global stems_switch_action
stems_switch_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  stems_list+LIST_SEL,%d3
        subi.l  #ROW_SW0,%d3                | switch k, 0..2
        moveq   #3,%d0
        cmp.l   %d0,%d3
        bcc.s   .Lw_out
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        move.l  stems_state,%d1
        moveq   #ST_RECORDING,%d0
        cmp.l   %d0,%d1
        bcc.s   .Lw_keep                    | locked while a take records or saves
        lea     sw_bit,%a0
        move.l  (%a0,%d3.l*4),%d1
        moveq   #1,%d0
        lsl.l   %d1,%d0                     | the format's bit
        move.l  stems_fmt,%d1
        eor.l   %d0,%d1
        move.l  %d1,stems_fmt
        move.w  %d2,%sr
        lea     sw_off,%a1
        and.l   %d0,%d1
        beq.s   .Lw_label
        lea     sw_on,%a1
.Lw_label:
        movea.l (%a1,%d3.l*4),%a0
        move.l  %d3,%d1
        addi.l  #ROW_SW0,%d1
        moveq   #ROW_LEN,%d0
        mulu.l  %d0,%d1
        movea.l %d1,%a1
        adda.l  #stems_rows,%a1
        move.l  %a0,(%a1)
        bra.s   .Lw_out
.Lw_keep:
        move.w  %d2,%sr
.Lw_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts
```
In `manifest.py` the docstring's menu sentence lists the new rows.

- [ ] **Step 4: Run, then commit**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-menu-green bash -c 'env STEMS_TEMPLATE="/home/yvez/stemrec5/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems.py stems --static && env STEMS_TEMPLATE="/home/yvez/stemrec5/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems_menu.py stems'` (tell Yves the log path: the menu gate takes about 35 minutes for both panels)
Expected: every static check PASS; on both panels every menu check PASS, including the widths. A label that ends past the clip goes to its short form (`AB ST [X]`, `CD ST [X]`, `24B [X]`) in both `stems.s` and the checks, and the ledger records the measured edge.
```bash
git add modules/stems/stems.s modules/stems/manifest.py tools/verify/verify_stems.py tools/verify/verify_stems_menu.py
git commit -m "stems: the STEMS list's new rows -- MAIN, CUE, AB and CD as sources beside T1-T8, the last source kept; AB STEREO, CD STEREO and 24 BIT as switches; locked while a take records; every label inside the pane on both panels (gate 6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: The cost, the whole gate, the records, STEMS3 (gates 7 and 8)

**Files:**
- Modify: `tools/verify/verify_stems.py` (check `cost`), `docs/firmware/STEM_REC.md` (18.9), `modules/stems/README.md`, `remixes/stems/README.md`, `modules/stems/manifest.py` (`doc`), `modules/stems/FLASH.md` (flash C), `CHANGELOG.md`

**Interfaces:**
- Consumes: everything above.
- Produces: `hook_cost(s, cov) -> (per_frame, frames)`; STEMS3 (`BUILD=3`).

- [ ] **Step 1: Write the cost check**

```python
HOOK_SIDE = ("stems_frame_hook", "stems_mirror", "stems_emac_in", "stems_emac_out", "stems_half",
             "stems_track_src", "stems_track_gains", "stems_track16", "stems_track24", "stems_bus16",
             "stems_bus24", "stems_copy_frame", "stems_tdelay_step", "stems_layout", "stems_trace_frame")
HOOK_CEILING = 5000


def hook_cost(s, cov):
    """Instructions the hook runs a frame, from a --coverage file (one
    `hexaddr count` line per instruction from the transport start): the
    counts inside the hook's routines (each from its symbol to the next
    symbol), over the times its first instruction ran (STEM_REC.md 10.0)."""
    starts = sorted(set(s.values()))
    spans = []
    for name in HOOK_SIDE:
        a = s[name]
        nxt = next((x for x in starts if x > a), a + 0x1000)
        spans.append((a, nxt))
    total, frames = 0, 0
    for line in pathlib.Path(cov).read_text().splitlines():
        a, n = line.split()
        a, n = int(a, 16), int(n)
        if a == s["stems_frame_hook"]:
            frames = n
        if any(lo <= a < hi for lo, hi in spans):
            total += n
    return (total // frames if frames else None), frames


def cost(s):
    """Gate 7: everything on at 24 bits, the eight-track THRU fixture, a take
    armed before play: at most HOOK_CEILING instructions a frame; and the
    cost with the recorder idle (the mirror alone), recorded."""
    for tag, before, src, fmt in (("costrec", None, 0xfff, 0b001), ("costidle", (), 0x0ff, 0b110)):
        cov = run_path(tag, "cov")
        log, *_ = port(s, 400, tag=tag, fixture=FIXTURE_THRU, mask=None, dump_blocks=False, calls_before=before,
                       pokes_before=[(s["stems_tracks"] + 2, src >> 8), (s["stems_tracks"] + 3, src & 0xff),
                                     (s["stems_fmt"] + 3, fmt)],
                       extra=("--coverage", str(cov)))
        per, frames = hook_cost(s, cov)
        if tag == "costrec":
            check(f"cost: at most {HOOK_CEILING} hook instructions a frame, everything on at 24 bits",
                  per is not None and per <= HOOK_CEILING, f"{per} a frame over {frames} frames")
        else:
            check("cost: the hook with the recorder idle (the mirror) is measured", per is not None,
                  f"{per} a frame over {frames} frames")
```
Add `cost` to the run list and `--only`.

- [ ] **Step 2: Run it**

Run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-cost VS --only=cost`
Expected: PASS, with the two per-frame counts in the details; record both in the ledger beside piece 3's 743 (eight tracks, 16-bit). Above 5,000: STOP and bring the measured split (mirror, multiply, buses, packing) to Yves; the spec's fallback is the multiply in the writer task, at the cost of a ring twice as big per track frame.

- [ ] **Step 3: The records**

- `docs/firmware/STEM_REC.md` `### 18.9 The gates ✅`: each check of section 6 of the spec with its run, its log and its numbers; the two costs; what the port can't see (the card's speed, the null test on the unit, real inputs, the hardware risk of `X:0x4800` measured by `gainsdirty`).
- `modules/stems/README.md`: "How to use it" with the new rows and the files; "Limits": the rates of spec section 3, the ring's cover, MASTER TRACK (18.8), the inputs recorded raw.
- `remixes/stems/README.md` and the manifest's `doc`: "every track after its fader, MAIN, CUE and the inputs, 16 or 24 bits".
- `CHANGELOG.md` Unreleased, Modules: one line for piece 5.
Then run: `bash .superpowers/v2/sync-p5.sh && bash .superpowers/v2/wslrun-5 p5-docs bash -c 'make docs && python3 tools/verify/verify_docs.py && git status --porcelain'`; copy back the re-rendered `README.md` and `remixes/README.md` the way the session that built STEMS2 did (`git diff > patch` in WSL, `git apply` on Windows), and commit:
```bash
git add docs/firmware/STEM_REC.md modules/stems/README.md remixes/stems/README.md modules/stems/manifest.py CHANGELOG.md README.md remixes/README.md
git commit -m "STEM REC piece 5 recorded: STEM_REC 18.9 (every gate, the costs, what the port can't see), how to use the new rows, the limits, the index

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: The whole gate, and Sam's procedure**

Run on the committed tree: `bash .superpowers/v2/wslrun-5 p5-check make check-remix REMIX=stems` (about 90 minutes: tell Yves the log path).
Expected: `# exit 0`, every check PASS, `verify_set`'s SKIP only. Then `make reach BASE=363861e` (the gates the diff reaches) and `STRESS_SOURCE=… STEMS_TEMPLATE=… make reach BASE=363861e RUN=1 KEEP=1 JOBS=1`; record each command and its result in the ledger, as the PR body will need them.

- [ ] **Step 5: STEMS3 and flash C**

Run: `bash .superpowers/v2/wslrun-5 p5-image bash -c 'make image REMIX=stems BUILD=3 VERSION=STEMS3 && sha256sum out/*STEMS3* && mkdir -p /home/yvez/xcheck/stems3 && cp out/OCTATRACK_STEMS3.bin out/OCTATRACK_OS1.40C_STEMS3.syx /home/yvez/xcheck/stems3/'`
Then add `## Flash C — stems: after the fader, the buses, 24 bits` at the top of `modules/stems/FLASH.md`, in flash B's form: the image (commit, sizes, hashes), every gate passed (the counts), and the tests in order:
1. **The level, after the fader.** A take of T1 alone with MAIN on, LEVEL moved during it: in a DAW, `T1.wav` and `MAIN.wav` null to silence (one inverted, summed).
2. **The null test, all tracks.** All eight tracks and MAIN, a pattern with every track playing: the sum of `T1`-`T8` minus `MAIN` is near silence (the inputs' direct mix aside).
3. **The inputs.** Gear on A to D: `AB.wav` and `CD.wav` stereo, then mono (`A`, `B`, `C`, `D`): each holds its input.
4. **24 bits.** The same take at 24 bits: the files open as 24-bit in a DAW.
5. **The card's speed with more files.** 60-second takes at 8 tracks 16-bit, 8 tracks 24-bit, and everything at 24 bits: PEAK after each, and any `RING FULL`.
6. **The first boot** (as flash B's test 1).
Commit:
```bash
git add modules/stems/FLASH.md
git commit -m "FLASH.md: flash C's image -- STEMS3, BUILD=3: stems after the fader, MAIN, CUE and the inputs, 24 bits; every gate passed; the tests: the null test, the inputs, 24 bits, the card's speed with more files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
