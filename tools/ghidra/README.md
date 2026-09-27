# Ghidra: the MAIN OS and both DSP payloads, one project

```bash
make ghidra GHIDRA=~/ghidra_12.x          # or GHIDRA_INSTALL_DIR=... make ghidra
python3 tools/ghidra/ot_ghidra.py import --ghidra DIR [--project DIR] [--only DSP_A,DSP_B] [--no-analysis]
python3 tools/ghidra/ot_ghidra.py layout  # the memory images + layout files only, no Ghidra
```

Needs `out/raw/section_3_MAIN_OS.bin` (`make os && make recon`) and a
JDK that your Ghidra accepts. The project is `out/ghidra/octatrack.gpr`. A
worktree under `.claude/` gets it in the temp directory instead, because
Ghidra refuses any path element that starts with `.`. Each program's
headless log is `out/ghidra/<program>.log`. `DEBUG=1` streams Ghidra's
output and lists every layout directive as it is applied.

| program | language | what is in it |
|---|---|---|
| `MAIN_OS` | `68000:BE:32:Coldfire_EMAC_frac`, else `68000:BE:32:Coldfire` | the image at `0x40000400`; the board map (`ARCHITECTURE.md` §7) as blocks, including `0x48000000`, the uncached view of SDRAM, as an empty block of its own (a byte-mapped copy doubled the analysis); the peripheral registers the docs read; the interrupt handlers (`KERNEL.md`); the DSP boot routines; the four DSP blobs marked as data; every stock address a module names with `.set`/`.equ` (the source file is in a repeatable comment) |
| `DSP_A`, `DSP_B` | `DSP56300:LE:24:default` | P/X/Y as the ColdFire uploads them (`dsp_modmap.py`), each load record's source address commented; internal memory to the default map's extents (P 8K, X 36K, Y 48K words, `CHIP.md` §3); the shared window `0x30000`–`0x3FFFF` with both bootstraps and payload A's shared records, X and Y mapped onto P there (they alias on the chip); the X/Y I/O registers; the vectors; both dispatch tables with every effect's init and process named (`DSP.md` §5); payload A's named routines |

Nothing from the image is committed. The tool reads your image, writes
`out/ghidra/load/`, and `OtLayout.java` applies the layout as
`analyzeHeadless`'s pre-script, so analysis starts from the right map.
`OtReport.java` prints each program's function, instruction and
error-bookmark counts. A layout file is plain text: add a finding to the
tables in `ot_ghidra.py` and re-import.

## The processor modules

Stock Ghidra has no DSP56300 and decodes the ColdFire's EMAC wrongly. Both
are fixed on branches of a Ghidra fork, each with a PR on
`roblg/ghidra` (#1–#3) being prepared for upstream:

| branch of `roblg/ghidra` | what it adds |
|---|---|
| `ot-dsp56300` | the DSP56300 processor: P/X/Y word spaces, parallel moves, hardware loops, a loop-end analyzer |
| `ot-coldfire-fixes` | ColdFire ISA_C and EMAC decoding and semantics, and the `Coldfire_EMAC_frac` variant (`MACSR` fractional, as this firmware runs it) |
| `decomp-space-qualifier` | the decompiler prints `__Y(*p)` for a dereference outside the default data space; without it, X and Y reads print as plain `*p` |

Build a distribution from a merge of the branches you want (`gradle
buildGhidra`). Alternatively, copy `Ghidra/Processors/DSP56300` and the
68000 language files into an installed Ghidra and run `support/sleigh -a`
on each `data/languages`. With stock Ghidra the MAIN OS still imports, as
`68000:BE:32:Coldfire`, and the DSP programs are skipped with a message.

## What the import prints

With the processor modules above and OS 1.40C, each program reports
0 layout warnings. The error bookmarks are flows into memory the image
does not hold:

| program | functions | instructions | error bookmarks |
|---|---|---|---|
| `MAIN_OS` | 2,175 | 190,956 | 9: calls into flash (`jsr 0x0000eae0`) and into `0x40000000`, below the image |
| `DSP_A` | 109 | 6,921 | 1: `P:0`'s `jmp $fff000`, the boot ROM |
| `DSP_B` | 102 | 6,377 | 1: the same |

Measured 26 Sep 2026 with the three branches below merged into Ghidra
12.3-DEV. Every DSP function decompiles (108 in A, 101 in B, 20 s timeout each).

## Reading the DSP programs

- Addresses are words: `P:0x7d1` is word `0x7d1`. The DSP is little-endian,
  three bytes per word, as the payloads store it.
- `X:0x30000` is `P:0x30000` (byte-mapped). A write through Y shows up in
  P's listing at the same address, which is what the chip does.
- The DSP56300 names in the listing come from the DSP56362 register map,
  the same names `dsp56kDisassemble` prints. The DSP56720's ESAI and host
  port read correctly under them (`DSP.md` §6c); a register the docs have
  not read is unverified on this chip.
- The vectors are labelled `vec_XX` and not named. The DSP56720's vector
  map differs from the DSP56362's: the live vectors are `0x10`–`0x1c`, the
  host-port handlers (`DSP.md` §6c).
- `fx_null_init`/`fx_null_process` is the passthrough every unused id
  points at, DELAY (`0x08`) included: the stock DELAY runs on the ColdFire.
