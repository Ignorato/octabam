# How the testing works

Every claim in this repository is checked on the developer's machine,
without hardware, against the developer's own copy of OS 1.40C. This page
says what runs, what each part proves, what none of it can see, and how to
run the right subset for a change. `CONTRIBUTING.md` is the contract;
this is the mechanism.

```
make check REMIX=<name>          one remix: build + cycles + the shared gates + the remix's own gates
make reach [RUN=1]               the gates THIS BRANCH'S DIFF reaches, in order; RUN=1 runs them
make accept REMIX=<name> ...     the same gates under a strict runner that writes a JSON report
make test-acceptance             the runner's and the classifier's own unit tests (no firmware, seconds)
scripts/refhash.sh check         a build change produced bit-identical images and reports
make ci                          what GitHub Actions runs (no firmware, so no remix)
```

## 1. What is being tested, and on what

Three instruments, all local:

| instrument | what it runs | built by | needed by |
|---|---|---|---|
| **the build** (`tools/build/build_bus.py`) | assembles every selected DSP module, links every ColdFire unit, places both, writes `out/mainos_bus.bin` and a build report; refuses on any collision, overrun or oracle drift | `make setup` (assembler + `elektron-firmware-tool`) | everything below |
| **`dsp_host`** (`tools/harness/dsp_host/`) | the assembled DSP code on a cycle-exact DSP56300 emulator: renders audio, meters instructions, polices memory; both cores in one process | `make setup` | the render gates, the bit-identity gates, the knob census |
| **the port** (`tools/emu/ot_emu`) | the whole machine: the ColdFire firmware booting the built image, a staged CF card with a real project, the sequencer, both DSP cores, MIDI, USB | `make emu-cf` (~1 min, per worktree) | the DRAM boot, the set gates, USB, every ColdFire module's behaviour gate |
| **Tier-0** (`tools/emu/emu_bringup.py`, Unicorn) | boots the firmware to its scheduler handoff and calls its draw and formatter code directly | `make emu-setup` (the `.venv`) | the label gates, CC MAP's gate, REPITCH's page gate |

Inputs every gate assumes: `out/raw/section_3_MAIN_OS.bin` (`make os && make
recon`, your own 1.40C), the submodules (`git submodule update --init`),
and for the set gates a real project directory in `OT_PROJECT` or
`~/.octabam_project`. A missing instrument prints a `[SKIP]` line and
`make check` still exits 0; `make accept` refuses the same run.

`docs/remixer/HARNESS.md` is `dsp_host` in depth, `docs/remixer/EMU.md`
the port and Tier-0.

## 2. `make check`: the two halves

`make check REMIX=<name>` is `bus`, `cycles`, then `verify`, and `verify`
is two halves (`Makefile`, `verify-shared` and `verify-remix`):

**The shared half** (`make check-shared REMIXES="a b c"`) does not depend
on which remix is selected, so a run over several remixes does it once:

| step | proves |
|---|---|
| `tools/remix/selftest.py` | the resource ledger refuses every collision it claims to (address, hook site, FX2 id, buffer, r7 slot ...), every shipped remix is clean, and the placer refuses an overrun |
| `verify_slots.py` | no dead store in BusVerb's per-instance state block |
| `verify_replaces.py` | no stock effect's id is taken over unless the module declares `replaces`; builds every remix to check it |
| `verify_docs.py` | the README module table and the remix index match the manifests (`make docs`), every remix has a README |
| `tools/build/label_fmt.py` | the select formatters re-derive from their sources (when `m68k-elf-as` is on PATH) |
| `verify_knob_clicks.py` | every continuous knob of the fixture remix's DSP modules moved mid-render, the block-rate step in dBFS; a garbage start stays quiet (~1.5 min, `dsp_host`) |
| `module_gates.py --shared` | every manifest gate declared `remix_arg=False` by any module in the selection, once: the bus bit-identity gates, the station render gates, the two port oracles, CC MAP |

**The per-remix half** (`make check-remix REMIX=<name>`), in recipe order:

| step | proves | needs |
|---|---|---|
| `bus`, `cycles` | the image builds; the static per-sample cycle count of every module and the worst load one core can be asked for, against the measured wall | |
| `verify_dirtystate.py` | each DSP module rendered from a garbage-filled instance block on silence is silent (`< -100 dBFS`) or identical to the zeroed render | `dsp_host` |
| `verify_initregs.py` | no module's `init` writes r1/n1/m1 (the dispatcher keeps the effect id in r1 across init) | |
| `verify_dram_boot.py` | the image boots under the port; the loader runs once, `fatal` never, every DRAM window reads back equal to the linked runtime | the port |
| `verify_labels.py`, `verify_modenames.py`, `verify_hidden.py` | the firmware's own formatter code prints each select's words; the MODE formatter renames its neighbours and restores them; a hidden engine is placed, dispatched, off the chooser and draws nothing | `.venv` |
| `module_gates.py --stage isolated --remix-only` | the manifest gates declared `remix_arg=True`: they take the remix name and build what they need | per gate |
| `verify_menu.py` | the built FX1/FX2 choosers and every cloned descriptor against the chooser logic decompiled from the firmware: row order, formatter vs value count, name-field lengths | |
| `verify_set.py` | a real project on the built image under the port: the load completes, the live effect ids equal the part's, every track's page-2 lane reaches the DSP record, every track with audio has chain output, CC 40 over MIDI moves T2's send, the load rewrote no project file, the firmware's log carries no error | the port, `.venv`, a project |
| `verify_usb.py` | the image enumerates as a USB device under the port with the descriptors the remix's USB modules declare; mass storage still answers (3 s) | the port |
| `module_gates.py --stage image` | the manifest gates that read the finished image (TEMPO BUS, EUCLID's playback, MINIVERB, TAPE ECHO's CPU port) | per gate |

`make bus` runs again between steps that leave a probe build at
`out/mainos_bus.bin`, and once more at the end, so the shipping image is
what is on disk after a green run.

Recorded timings (27 Sep 2026, one machine, 25 remixes): the shared half
475 s; the per-remix half 223 s on average, from 51 s (`lofi-amf-fix`) to
1,143 s (`bottleservice`). Timings under load are not comparable: two
concurrent runs on one machine each run slower and the port-based gates
that watch a device clock (USB overruns) can flake.

## 3. Module gates: a module carries its own tests

A module declares its gates in its manifest and `make check` runs them for
every remix that carries the module; a remix without the module never runs
them (`tools/remix/schema.py`, `Gate`; `tools/verify/module_gates.py`):

```python
gates=(Gate("tools/verify/verify_character.py", remix_arg=False),          # shared half, once
       Gate("tools/verify/verify_grains.py"),                              # per remix, gets the remix name
       Gate("tools/verify/verify_euclid.py", venv=True, stage="image"),    # per remix, after the image is final
)
```

- `remix_arg=False`: the gate builds its own fixture (`registry.fixture`,
  the smallest remix carrying what it needs) and runs once in the shared
  half. `True` (the default): it takes the remix name and runs in the
  per-remix half.
- `stage="isolated"` (default) runs before the menu and set gates;
  `"image"` runs last, on the finished `out/mainos_bus.bin`.
- `venv=True` runs it under `.venv/bin/python3` when the venv exists (the
  gate needs Unicorn or the panel's Python).
- A missing script is a `[FAIL]`, not a skip. The same script may not be
  listed twice.

The gates as declared on 28 Sep 2026 (`grep "Gate(" modules/*/manifest.py`):

| module | gate | half | proves |
|---|---|---|---|
| DELAY SERVER, REVERB SERVER | `verify_twocore` | shared | the servers on their real cores render bit-identical to the single-core DEV hatch, and under four instruction interleaves (~1 min) |
| | `verify_onebus` | shared | the one aux bus on both cores: the chain, each host's wet print, WET passthrough sample-exact, the T8 send refusal, stored old bytes inert, four skews (~2 min) |
| DELAY SERVER | `verify_grains`, `verify_tempo` | per remix | `Remix.grains` changes GRAIN only; the delay's tempo snap lands at the published tempo word |
| SEND | `verify_burn` | per remix | the RIG BURN probe image is the shipping engine plus an inert knob, bit-identical at 0 and 127 |
| CHARACTER, SPECTRUM, MODULATION | `verify_<module>` | shared | each station rendered through `dsp_host` against predictable arithmetic or a float reference: bypass bit-exact, every mode, bounded resonance, FX1-only promise |
| MODE DEFAULTS | `verify_modedefaults` | per remix | a MODE turn on the panel lands its view in the live lane under the port |
| SCENES P2 | `verify_scenesp2` | per remix | page-2 locks reach the DSP frame through the crossfader; the editor with a scene held writes the pool (three boots) |
| TEMPO BUS | `verify_tempobus` | image | the TEMPO key opens the bus screen, its rows edit the hosts, the window closes clean (on `verify_set`'s staged card) |
| CC MAP | `verify_ccmap` | shared | the CC cave re-assembles to its pinned bytes; CC 62-73 write page 2 and clamp to the count; page-1 CCs tail-call stock (Tier-0) |
| CC FEEDBACK | `verify_ccfeedback` | shared | the knob-change sweep enters the stock CC emitter once per changed byte, with the lane's value, gated as stock gates (Tier-0) |
| MIDI SCENES, OCTAKIT | `verify_midiscenes`, `verify_octakit` | shared | the two port oracles: the author's own build reproduced byte for byte |
| REPITCH | `verify_repitch` | per remix | the hooks, the page (Tier-0) and playback pitch/speed under the port on a project |
| EUCLID | `verify_euclid` | image | control math, hooks, renders, playback under the port |
| MINIVERB | `verify_miniverb` | image | eight instances isolated, dirty memory, buffer guards, audio gates |
| TAPE ECHO | `verify_tapeecho_cpu` | image | the C reference against the compiled ColdFire port of the echo |
| USB AUDIO IN AB / CD / ABCD | `verify_usb_in` | image | the host's channels land bit-exact on their RX slots under the port, the others zero, the recorder ring filled, the jacks back at alt 0 |
| USB AUDIO OUT TRACKS MAIN CUE | `verify_usb_align` | image | MAIN/CUE in the twenty-channel stream are in phase with the tracks (lag 0 samples) |

A gate whose instrument or project is absent prints `[SKIP]`; one whose
subject is absent from the remix prints `[ -- ]` or `[N/A]` and exits 0.
Two named skips are deliberate: `verify_repitch` and `verify_euclid` skip
their playback checks when the port's output carries no audio at all,
pointing at the port's voice-silence entry in `docs/remixer/EMU.md`; a run
with audio is measured in full.

## 4. `make reach`: which gates a change reaches

`tools/verify/reach.py` reads the branch's diff against `origin/main`
(`BASE=` for another base) and prints the gates in run order; `RUN=1` runs
them, `KEEP=1` runs every one and prints a table instead of stopping at
the first failure, `JOBS=n` runs the per-remix lines over n worktrees. It
refuses a tree that is not rebased onto the base: gates run before a
rebase are not a result.

| changed | reaches |
|---|---|
| `modules/<name>/` | `make check` and `make accept` for every remix that carries the module; its README alone reaches `verify_docs` |
| `remixes/<name>/remix.py` | `make check` and `make accept` for that remix; its README alone reaches `verify_docs` |
| the build (`build_bus.py`, `cycle_count.py`, `dsp/`) or anything it imports | `scripts/refhash.sh check`, `make identity`, `make test-acceptance`, `make check-shared` for the cover |
| a gate script of the shared half | one `make check-shared` for the cover |
| a gate script of the per-remix half | `make check-remix` for the cover |
| a manifest gate | its owners' remixes |
| the acceptance runner, the stress generator, `pressure.py` | `make test-acceptance`, the cover, `make accept` on the cover |
| `tools/harness/dsp_host/`, `tools/patches/`, `scripts/setup.sh` | `make ci-dsp`, then the cover (rebuild the toolchain first) |
| `tools/emu/ot_emu/` | `make ci-emu`, `make emu-cf`, the cover's per-remix half |
| `Makefile` | by which targets changed: the check graph reaches identity, the cover and `make ci`; the runner targets reach `test-acceptance`; other targets nothing |
| `*.md`, `docs/` | `verify_docs` |
| `.github/` | `make ci` |
| a file no gate depends on | nothing, and the listing says so |

Files under `tools/` are placed by dependency: the Python imports and the
`tools/x/y.py` paths the code runs or reads form a graph, and a change
reaches the gates that transitively depend on it. A path in a comment,
docstring or message is not an edge.

**The cover** is the fewest remixes that between them carry every module,
computed from the registry on each run, so every module's gates and every
kind of per-remix gate run at least once. `make reach REACHARGS=--all`
makes the floor every remix. **Identity** (`make identity`,
`tools/verify/image_identity.py`) builds every remix from the merge-base
(a kept worktree under `out/identity/base`) and from this tree with the
shipping flags and compares image and report byte for byte; after a build
change, `RUN=1` then checks only the remixes whose bytes moved.

With `STRESS_SOURCE=<a local project>` set, the accept lines can run and
they replace the check lines for the same remixes (accept runs both halves
itself). Without it, accept is listed as blocked and the check lines stay.

## 5. Running several remixes at once: shards

`tools/verify/check_shards.py` (`make check-remixes REMIXES="a b" JOBS=4`,
and what `make reach JOBS=4` uses) runs `make check-remix` for each remix
in its own worktree under `out/shards/<i>`: a detached checkout of HEAD
with this tree's uncommitted diff applied, `vendor/` and `.venv/`
symlinked, the stock slice copied in, submodules initialised, its own port
built. The shards are kept between runs and refreshed in place (a few
seconds; `--fresh` recreates them, `--rm` removes them). Remixes are handed
out from one queue so the expensive ones do not set the wall time. Logs:
`out/check_shards/<remix>.log`.

`make check-remix-gates REMIX=<name>` (`--by-gate`) splits one remix's
per-remix half into one job per gate over the shards; the wall is then the
longest gate. It refuses to run when the Makefile's recipe names a script
its job list does not cover.

Two shard runs, or a shard run beside another session's `make check`, on
one machine share nothing but CPU. They are safe; they are slow.

## 6. `make accept`: the strict runner

`make check` tolerates a missing instrument (a `[SKIP]` line, exit 0).
`make accept` (`tools/verify/acceptance.py`) runs the same gates and
refuses missing evidence: any `[SKIP]`, any swallowed non-zero exit, a
timeout or an over-budget cycle count fails or blocks the run, and it
writes a versioned JSON report (`out/acceptance/<timestamp>/report.json`,
schema `docs/remixer/acceptance.schema.json`).

```bash
make accept REMIX=bottleservice STRESS_SOURCE=<a local project>   # a fixture generated for the remix
make accept REMIX=bottleservice OT_PROJECT=<a project you prepared>
make accept REMIXES="a b c" STRESS_SOURCE=<dir>                   # the shared half once
```

Stages, serially per remix: preflight (provenance, instruments, the
pressure profile), fixture (generated from `STRESS_SOURCE` by
`tools/harness/stress_project.py`, or `OT_PROJECT` fingerprinted as is),
`check_shared` (once for every remix in the run), `check_remix`, cycles
(the image hashed; a static estimate above the wall fails), pressure price
(every selectable per-core layout priced against the wall), pressure
render (the dearest six and four random layouts per core rendered on all
eight tracks under `dsp_host -guard -dirty`, metered). A failed or blocked
stage leaves the dependent ones `not_run`. The pressure stages run only
when every DSP module in the selection declares its dearest settings
(`Module.dear`); a module without them blocks the remix by name, never a
render at defaults.

Every report carries `hardware_validated: false`. `passed` means the local
stages passed for these inputs. `docs/remixer/ACCEPTANCE.md` has the
report fields, the fixture and the coverage; `tools/harness/STRESS_PROJECT.md`
the generated project.

## 7. Bit-identity: proving a change changed nothing

- **`scripts/refhash.sh save` then `check`**: 24 build configurations of
  one two-server selection (the shipping flags, the plain build, the DEV
  hatch, the probes, the overrides), every artifact and every build report
  hashed and compared. Save the baseline on a tree you trust (main), then
  check on the branch. A path in the report is part of the report: moving
  a tool is a report change, re-saved only after the artifacts are shown
  identical. Local discipline: the hashes depend on your own stock image.
  Two of the 24 cases (`plain`, `marker`) refuse to build on main (28 Sep
  2026: the plain two-server selection overruns payload A); the gate
  compares the report as well as the artifacts, so a refusal is pinned too.
- **`make identity`**: every remix, base against head, image and report.
- **`make verify-bus`** (`SAVE=1` first): a bus-layout change is
  behaviour-preserving over every layout in its case list, stamp, edit,
  compare. Not part of `make check`.
- **`make verify-ident MOD=<station>`**, **`make verify-spectrum-ident`**,
  **`make verify-roll CAND=`**, **`make verify-delay CAND=`**: a rewritten
  station or an alternate engine is bit-identical to the saved reference
  across a knob matrix.

## 8. What GitHub Actions checks

`.github/workflows/ci.yml` runs on every PR, on `main` and by hand, on
Ubuntu and macOS. It has no Elektron bytes, so it checks only what needs
none (`make ci` runs the same four locally):

| job | target | proves |
|---|---|---|
| gates the PR reaches | `make reach` (dry run) | the diff classifies and the branch is rebased; the log carries the list the PR body must answer |
| acceptance runner tests | `make test-acceptance` | the runner refuses skipped, failed, incomplete and over-budget evidence; the classifier routes paths as documented; the shard runner's job list covers the recipe |
| dsp56300 + our patch | `make ci-dsp` | the vendored DSP emulator at its pin takes our patch, builds, passes upstream's test runner, and `dsp_asm` emits the one-word displaced move (`make check-asm`) |
| ColdFire port unit tests | `make ci-emu` | `ot_emu` builds against the pinned cores and passes its EMAC and peripheral unit tests (the tests that read the stock OS are excluded by name) |

**A green CI run says nothing about a remix.** Building, booting and
playing one needs 1.40C, which is why the gates above run on your machine
and their results go in the PR body.

## 9. What none of this can see

Every instrument has a blind spot, and each gate's own docstring names
its. The ones that have cost real work:

- **Hardware timing between the two DSP cores.** `dsp_host` runs the
  cores lock-step or under a chosen interleave (`-skew`); a local clean
  under every skew is not evidence a cross-core race is gone. A local red
  is a defect.
- **The cycle budget.** The emulator renders an engine the chip cannot
  afford. `make cycles` bounds it statically (instructions, not cycles, no
  contention); the unit proves it.
- **The dispatcher's facts.** `dsp_host` hands each effect an r7 and r6 it
  computes; module logic keyed on a dispatcher fact is measured under the
  port (`ot_emu --dsp-pcwatch`), never in the harness.
- **The panel.** `dsp_host` pokes knob values into the DSP directly. A slot
  can draw a knob and publish nothing; a formatter can outrank a value
  count. `verify_menu` and the Tier-0 label gates cover the descriptor
  side; the two mechanisms never validate each other.
- **Stored project data.** A part saved under an older slot layout feeds
  the new layout its old bytes; no gate reads your card. Stamp projects
  after a layout change (`tools/hw/ot_project.py stamp-defaults`).
- **Whatever the metric cannot represent.** A harmonic metric cannot see
  an inharmonic block-rate discontinuity; an AC-coupled capture cannot see
  DC; a reverb smears a per-sample fault into a tail. Before trusting a
  null result, ask what the instrument physically cannot see.
- **The stock DELAY's audio and the recorder's DMA** under the port: the
  ring arithmetic runs, the eDMA that moves audio through SDRAM is not
  modelled.
- **Ears.** GRAIN's right-channel hiss passed every gate and was found by
  listening. `docs/remixer/HARNESS.md` has the listening protocol.

`docs/remixer/FAILURE_MODES.md` is the register of what has gone wrong on
a unit and why; `AGENTS.md` lists the traps that produced clean assembly
of wrong machine code.

## 10. Before a pull request

```bash
git fetch upstream && git rebase upstream/main
make reach BASE=upstream/main                                   # the list
STRESS_SOURCE=<a local project> make reach BASE=upstream/main RUN=1 KEEP=1 JOBS=4
```

Paste each command and its result into the PR body (the template asks for
them). A remix whose DSP modules declare no `dear` makes `make accept`
report `blocked`; say so. A build change adds `scripts/refhash.sh check`
with the baseline saved on main first. Then flashing, on your own unit,
with `BUILD` bumped so the version string maps to a commit
(`docs/remixer/FLASHING.md`).
