#!/usr/bin/env python3
"""STEM REC -- the row, the tap and the file, checked without hardware.

    python3 tools/verify/verify_stems.py [remix] [--long] [--fat32]   (default: stems)

Static, from the built image: CONTROL has seven rows, the six stock ones
byte for byte, the seventh labelled STEM REC with the module's action and
id 0; the frame site jumps to the hook; the ring and the stack sit at the
top of the platform reserve, above the runtime's stage. Then, when the
port is built and the fixture exists (tools/verify/stems_fixture.py), the
port runs of the proof of concept and of the streaming plan. `--long` adds
a 20-second take, which takes about 20 minutes under the port and stays
out of `make check`. `--fat32` runs the take checks again on a FAT32 card
(`stems_fixture.py --fat32`), after checking the firmware mounted it; it
stays out of `make check` too.
"""
import json
import os
import pathlib
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
RUNTIME_ELF = pathlib.Path("out/platform/runtime/runtime.elf")
LAYOUT_DIR = pathlib.Path("out/platform")      # platform_build.LAYOUT lives here, by name
CONTROL_DESC, CONTROL_ROWS, ROW_LEN, STOCK_N = 0x400cbd54, 0x400cc5a8, 24, 6
FRAME_SITE = 0x40004b12
ATA_FIRST_SITE = 0x40014cfe  # the stock PIO write's first sector (STEM_REC.md 11.7)

# Task 11's interface (STEM_REC.md section 9.4): T1's slot in the read-back
# half, and the direction char blockdump.py's summary prints for that class.
# Track k is at k * 0x80 (stock NEIGHBOR 0x400046dc); 0x100 was T3, which the
# old fixture's NEIGHBOR chain filled with a copy of T1 (STEM_REC.md 9.2).
READBACK_DIR = "<"
T1_OFFSET = 0x00

EMU = pathlib.Path("out/emu/ot_emu")
FIXTURE = pathlib.Path("out/stems_fixture.json")   # written by tools/verify/stems_fixture.py
KEY_STOP = 0x4000a1e0
STOP_GATE = 0x80000029     # the STOP handler returns early while this byte is 0 (STEM_REC.md 1.6)
PRE_ROLL = 40              # frames before the transport start; the dump includes them
ST_IDLE, ST_ARMED, ST_RECORDING, ST_FINISHING = 0, 1, 2, 3   # stems.s
STACK_SIZE, STACK_FILL = 0x2000, 0x5354454d                   # stems.s: DramRegion stems_stack, "STEM"
STACK_LIMIT = 6 * 1024     # above this, the plan raises the stack to 16 KB before a flash
RING_SIZE_T1 = 0x400000            # T1 only: 65,536 frames of 64 bytes
MAX_FRAMES = 9922500               # 60 minutes
CHUNK_FRAMES = 512

fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def syms():
    out = subprocess.run(["m68k-elf-nm", str(RUNTIME_ELF)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def rd32(img, a):
    return int.from_bytes(img[a - BASE:a - BASE + 4], "big")


def static(img, stock, s):
    check("CONTROL count is 7", rd32(img, CONTROL_DESC) == 7, f"{rd32(img, CONTROL_DESC)}")
    rows = rd32(img, CONTROL_DESC + 0x18)
    check("CONTROL rows moved", rows != CONTROL_ROWS, f"0x{rows:08x}")
    a, b = rows - BASE, CONTROL_ROWS - BASE
    check("the six stock rows came across byte for byte",
          img[a:a + ROW_LEN * STOCK_N] == stock[b:b + ROW_LEN * STOCK_N])
    r7 = [rd32(img, rows + ROW_LEN * STOCK_N + 4 * k) for k in range(6)]
    check("row 7 label is stems_label", r7[0] == s["stems_label"], f"0x{r7[0]:08x}")
    check("row 7 action is stems_action", r7[2] == s["stems_action"], f"0x{r7[2]:08x}")
    check("row 7 window, pad, child and id are 0", r7[1] == r7[3] == r7[4] == r7[5] == 0, f"{r7}")
    want = b"\x4e\xb9" + s["stems_frame_hook"].to_bytes(4, "big") + b"\x4e\x71"
    got = img[FRAME_SITE - BASE:FRAME_SITE - BASE + 8]
    check("0x40004b12 is jsr stems_frame_hook; nop", got == want, got.hex())
    want = bytes.fromhex("4ef9") + s["stems_ata_first"].to_bytes(4, "big")
    got = img[ATA_FIRST_SITE - BASE:ATA_FIRST_SITE - BASE + 6]
    check("0x40014cfe is jmp stems_ata_first", got == want, got.hex())


def regions(s):
    from remix import platform_build
    lay = json.loads((LAYOUT_DIR / platform_build.LAYOUT).read_text())
    ring, stack, buf = s["stems_ring"], s["stems_stack"], s["stems_buf"]
    check("ring is 4 MiB ending at the reserve ceiling", ring + 0x400000 == lay["ceiling"],
          f"0x{ring:08x} + 4 MiB vs ceiling 0x{lay['ceiling']:08x}")
    check("stack sits just below the ring", stack + 0x2000 <= ring, f"0x{stack:08x}")
    check("sector buffers sit below the stack, 512-aligned", buf + 270336 <= stack and buf % 512 == 0,
          f"0x{buf:08x}")
    check("the runtime's stage ends below the sector buffers", lay["stage_end"] <= buf,
          f"stage end 0x{lay['stage_end']:08x}")


def t1_frames(dump_path):
    """T1's 16-bit stereo frames from a --block-dump, in frame order: the even
    words of T1's 64-word block in each read-back. One entry per frame, each
    32 signed samples, L R L R ..."""
    import blockdump
    out = []
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram in (0x80003190, 0x80003590) and d == READBACK_DIR:
            base = T1_OFFSET // 2
            out.append((frame, [x - 65536 if x >= 32768 else x for x in w[base:base + 64:2]]))
    return [s for _, s in sorted(out)]


def core1_slot_peaks(dump_path):
    """The largest |sample| in each of core 1's four 0x80-byte slots (tracks
    1 to 4), over every read-back in a --block-dump."""
    import blockdump
    peaks = [0, 0, 0, 0]
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram in (0x80003190, 0x80003590) and d == READBACK_DIR:
            for k in range(4):
                for x in w[64 * k:64 * k + 64:2]:
                    peaks[k] = max(peaks[k], abs(x - 65536 if x >= 32768 else x))
    return peaks


def port(s, frames, stop_at=None, extra=(), tag="run", ring_bytes=0, calls=(), pokes=(),
         card_in=None, dump_blocks=True, stack=False, mems=(), calls_before=None, fixture=None,
         pokes_before=()):
    """One fixture run under the port: the module's action called before
    play (`--call-before-play`: the action arms, and the hook takes the
    ARMED-to-RECORDING edge on the first playing frame), STOP at `stop_at`
    (None = no STOP), any further `calls` as (frame, addr), any `pokes` as
    (addr, byte) applied after the load. A run that calls STOP also sets
    STOP_GATE to 1: the port starts the transport without the PLAY key, and
    on the fixture's project that leaves the STOP handler's gate shut, so
    the call would do nothing (Task 10). Dumps the six state words and, when
    `ring_bytes`, the start of the ring. Returns (log text, dump, card,
    state words, ring bytes). `card_in` replaces the fixture's card (Task 16:
    a second take on the first take's card). `dump_blocks=False` drops the
    block dump, which a run of tens of thousands of frames cannot afford.
    `stack=True` also dumps the writer task's 8 KB stack to <tag>.stack.
    `pokes_before` land after the action and before the transport start, so
    they are in force from the take's first frame; `pokes` land after the
    transport start, some 26 frames into play (main.cpp).

    `--call-before-play` beside `--pre-roll` needs the port fixed on 13 Sep
    2026 (`main.cpp` runs to main's spin before the call; STEM_REC.md 10.1).
    An older port refuses the call, prints the refusal and records nothing,
    so `tap()` checks the call's own report line before anything else."""
    tag = f"{tag}{SUFFIX}"
    fx = json.loads(pathlib.Path(fixture or FIXTURE).read_text())
    work = pathlib.Path("out/stems_runs"); work.mkdir(parents=True, exist_ok=True)
    dump, card = work / f"{tag}.dump", work / f"{tag}.img"
    mem, ring = work / f"{tag}.mem", work / f"{tag}.ring"
    dumps = f"0x{s['stems_state']:x},24={mem}"
    if ring_bytes:
        dumps += f";0x{s['stems_ring']:x},{ring_bytes}={ring}"
    if stack:
        dumps += f";0x{s['stems_stack']:x},{STACK_SIZE}={work / (tag + '.stack')}"
    for addr, length, name in mems:
        dumps += f";0x{addr:x},{length}={work / (tag + '.' + name)}"
    at = [f"{f}:0x{a:x}:0" for f, a in calls]
    pk = list(pokes)
    if stop_at is not None:
        at.append(f"{stop_at}:0x{KEY_STOP:x}:0")
        pk.append((STOP_GATE, 1))
    args = [str(EMU), "--image", str(IMAGE), "--card", card_in or fx["card"], "--set", fx["set"],
            "--project", fx["project"], "--sequencer", "--internal-clock",
            "--frames", str(frames), "--load-ms", "20000", "--dsp", "--main-level", "64",
            "--pre-roll", str(PRE_ROLL), "--poke-trig", "2",
            *(["--block-dump", str(dump)] if dump_blocks else []),
            "--call-before-play", ",".join(f"0x{a:x}:0" for a in (calls_before or (s["stems_action"],))),
            "--card-out", str(card), "--mem-dump", dumps, *extra]
    if at:
        args += ["--at", ",".join(at)]
    if pk:
        args += ["--poke", ";".join(f"0x{a:x}={b}" for a, b in pk)]
    if pokes_before:
        args += ["--poke-before-play", ";".join(f"0x{a:x}={b}" for a, b in pokes_before)]
    r = subprocess.run(args, capture_output=True, text=True)
    (work / f"{tag}.log").write_text(r.stdout + r.stderr)   # the port's report, for the call timing
    m = mem.read_bytes() if mem.exists() else b"\0" * 24
    words = [int.from_bytes(m[i:i + 4], "big") for i in range(0, 24, 4)]
    return (r.stdout + r.stderr, dump, card, words,
            ring.read_bytes() if ring_bytes and ring.exists() else b"")


def tap(s):
    log, dump, _, words, raw = port(s, 400, stop_at=300, tag="tap", ring_bytes=64 * 400)
    st, status, _, wr, rd, nfr = words
    armed = [l for l in log.splitlines() if l.startswith("call") and "before play" in l]
    check("the action was called before play", any("-> returned" in l for l in armed),
          armed[0].strip() if armed else "no call line in the port's report")
    check("the hook recorded frames", nfr > 200, f"{nfr} frames, wr {wr}")
    # Every check below needs frames: with none, "equal at a fixed lag" and
    # "64 bytes per frame" are true of an empty ring, which is how the first
    # RED run of this task passed three of them.
    check("wr counts frames", nfr > 0 and wr == nfr, f"wr {wr}, frames {nfr}")
    check("the stop moved RECORDING on", nfr > 0 and st in (ST_IDLE, ST_FINISHING),
          f"state {st}, status {status}")
    # The ring stays big-endian: the task swaps into its own buffers.
    got = [[int.from_bytes(raw[f * 64 + 2 * k:f * 64 + 2 * k + 2], "big", signed=True)
            for k in range(32)] for f in range(nfr)]
    peaks = core1_slot_peaks(dump)
    k1 = T1_OFFSET // 0x80
    check("T1's slot is the only core-1 slot with sound",
          peaks[k1] > 256 and all(p < 64 for i, p in enumerate(peaks) if i != k1),
          f"peaks by slot {peaks}, T1's slot {k1}")
    want = t1_frames(dump)
    lag = next((L for L in range(len(want) - nfr + 1) if want[L:L + nfr] == got), None)
    check("every ring frame equals T1's read-back at one fixed lag", nfr > 0 and lag is not None,
          f"lag {lag} frames (pre-roll {PRE_ROLL})" if lag is not None
          else f"no lag 0..{len(want) - nfr} matches")
    loud = any(any(x) for x in got)
    check("the signal is not silence", loud,
          "non-zero samples present" if loud else f"all {nfr} ring frames are zero")


def card_files(card_path):
    """Every file on a card image, {path: bytes}, paths as the card spells
    them, without a leading slash ('STEMS/AUDIO/000000-0000/T1.wav'). A
    folder with no file in it does not appear: emu_card.extract_image lists
    files (verify_card_reader.py pins that)."""
    import emu_card as ec
    return ec.extract_image(pathlib.Path(card_path).read_bytes())


def card_get(files, path):
    """The file at `path` (case-insensitive, leading slash optional), or None."""
    want = path.lstrip("/").lower()
    return next((d for p, d in files.items() if p.lower() == want), None)


def new_entries(files, fixture=None):
    """What this run added to <set>/AUDIO: the first path component under it
    of every file there, minus what the fixture staged, as the card spells
    it. An empty take folder cannot be seen, so it is not counted."""
    fx = json.loads(pathlib.Path(fixture or FIXTURE).read_text())
    audio = f"{fx['set']}/AUDIO/".lower()
    staged = {n.lower() for n in fx.get("staged", [])}
    names = {p[len(audio):].split("/", 1)[0] for p in files if p.lower().startswith(audio)}
    return sorted(n for n in names if n.lower() not in staged)


def wav_check(card_path, nfr, dump, tag, lag_want=PRE_ROLL):
    """The take on the card: one new folder in the set's AUDIO folder, its
    T1.wav with the header STEM REC writes, and every sample equal to T1's
    read-back at the lag a take armed before play starts at (the pre-roll).
    The file must also hold sound: under the port the fixture's kick sounds
    for four frames, and a silent file equals the read-back at almost any
    lag, which is how a wrap test once passed on a file of zeros."""
    files = card_files(card_path)
    fx = json.loads(FIXTURE.read_text())
    audio = f"/{fx['set']}/AUDIO"
    names = new_entries(files)
    check(f"{tag}: one new recording in {audio}", len(names) == 1, f"{names}")
    if not names:
        return
    path = f"{audio}/{names[0]}/T1.wav"
    data = card_get(files, path)
    check(f"{tag}: {path} exists", data is not None)
    if data is None:
        return
    if len(data) < 44:
        check(f"{tag}: the file holds a header", False, f"{len(data)} bytes")
        return
    riff, size, wave_, fmt, flen, pcm, ch, rate, brate, align, bits, dtag, dlen = \
        struct.unpack_from("<4sI4s4sIHHIIHH4sI", data, 0)
    check(f"{tag}: header fields", (riff, wave_, fmt, flen, pcm, ch, rate, brate, align, bits, dtag) ==
          (b"RIFF", b"WAVE", b"fmt ", 16, 1, 2, 44100, 176400, 4, 16, b"data"))
    check(f"{tag}: data size = frames x 64", nfr > 0 and dlen == 64 * nfr, f"{dlen} vs {64 * nfr}")
    check(f"{tag}: RIFF size = 36 + data", size == 36 + dlen, f"{size}")
    check(f"{tag}: file length = 44 + data", len(data) == 44 + dlen, f"{len(data)}")
    if len(data) < 44 + 64 * nfr:
        check(f"{tag}: every sample equals T1's read-back at one fixed lag", False, "file too short")
        return
    got = [list(struct.unpack_from("<32h", data, 44 + 64 * f)) for f in range(nfr)]
    want = t1_frames(dump)
    same = nfr > 0 and want[lag_want:lag_want + nfr] == got
    check(f"{tag}: every sample equals T1's read-back at lag {lag_want}", same,
          "" if same else f"matching lags {[L for L in range(len(want) - nfr + 1) if want[L:L + nfr] == got][:5]}")
    peak = max((abs(x) for f in got for x in f), default=0)
    check(f"{tag}: the file holds sound", peak > 0, f"peak {peak}")


def full(s):
    """Armed before play, STOP at 400, and 300 frames for the task to write
    the take."""
    log, dump, card, words, _ = port(s, 700, stop_at=400, tag="full", stack=True)
    st, status, made, wr, rd, nfr = words
    raw = run_path("full", "stack")
    if raw.exists():
        longs = [int.from_bytes(raw.read_bytes()[i:i + 4], "big") for i in range(0, STACK_SIZE, 4)]
        untouched = next((i for i, w in enumerate(longs) if w != STACK_FILL), len(longs))
        peak = STACK_SIZE - 4 * untouched
        check(f"full: the writer's stack peak is at most {STACK_LIMIT} bytes", 0 < peak <= STACK_LIMIT,
              f"{peak} of {STACK_SIZE} bytes used")
    check("full: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    check("full: the task drained every frame", rd == wr == nfr, f"rd {rd}, wr {wr}, frames {nfr}")
    wav_check(card, nfr, dump, "full")
    return log, words


def rowstop(s):
    """Armed before play, stopped from the row at frame 200 while the
    sequencer plays on to the STOP at 400: the task writes the take while
    the sequencer is still running."""
    log, dump, card, words, _ = port(s, 700, stop_at=400, tag="rowstop",
                                     calls=((200, s["stems_action"]),))
    st, status, made, wr, rd, nfr = words
    check("rowstop: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    check("rowstop: the task drained every frame", rd == wr == nfr, f"rd {rd}, wr {wr}, frames {nfr}")
    check("rowstop: the row stopped it near frame 200", 150 < nfr < 260, f"{nfr} frames")
    wav_check(card, nfr, dump, "rowstop")


def stream(s):
    """A take long enough to cross three chunks: the task must write while
    the take runs. The write watch logs the state words; a write to rd
    (word 4) before the first FINISHING is a write during the take."""
    log, dump, card, words, _ = port(s, 1900, stop_at=1700, tag="stream", extra=watched(s, span=24))
    st, status, _, wr, rd, nfr = words
    ws = writes(s, log, span=24)
    fin = next((x for x, w, v in ws if w == 0 and v == ST_FINISHING), None)
    mid = [x for x, w, v in ws if w == 4 and fin is not None and x < fin]
    check("stream: the task wrote during the take", len(mid) >= 2, f"{len(mid)} rd writes before FINISHING")
    check("stream: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    check("stream: the task drained every frame", nfr > 3 * CHUNK_FRAMES and rd == wr,
          f"rd {rd}, wr {wr}, frames {nfr}")
    wav_check(card, nfr, dump, "stream")


def wrap(s):
    """The ring's offsets set to three frames before its end (T1: frames
    are 64 bytes) after the action and before play, so they are in force
    from the take's first frame: frames 0 to 2 go at the ring's end, and
    frame 3 on from its start, just before the kick's four loud frames (4
    to 7). The hook and the task both wrap, the offsets end at the right
    place, and the file must equal the read-back at the pre-roll lag."""
    off = RING_SIZE_T1 - 3 * 64
    pokes = [(s[w] + i, (off >> (24 - 8 * i)) & 0xff)
             for w in ("stems_wr_off", "stems_rd_off") for i in range(4)]
    log, dump, card, words, _ = port(s, 400, stop_at=300, tag="wrap", pokes_before=pokes,
                                     mems=((s["stems_wr_off"], 8, "offs"),))
    st, status, _, wr, rd, nfr = words
    check("wrap: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    raw = run_path("wrap", "offs")
    offs = raw.read_bytes() if raw.exists() else b"\0" * 8
    wr_off, rd_off = int.from_bytes(offs[:4], "big"), int.from_bytes(offs[4:], "big")
    want = (off + 64 * nfr) % RING_SIZE_T1
    check("wrap: both offsets wrapped and end where the take does", nfr > 3 and wr_off == rd_off == want,
          f"wr_off {wr_off}, rd_off {rd_off}, want {want} ({nfr} frames)")
    wav_check(card, nfr, dump, "wrap")


def cap(s):
    """The 60-minute cap: wr and rd poked to 50 frames short of it after
    the action. The hook must end the take by itself, with no error."""
    v = MAX_FRAMES - 50
    pokes = [(s[w] + i, (v >> (24 - 8 * i)) & 0xff) for w in ("stems_wr", "stems_rd") for i in range(4)]
    log, _, card, words, _ = port(s, 300, tag="cap", pokes=pokes, dump_blocks=False, extra=watched(s))
    st, status, _, wr, rd, nfr = words
    check("cap: the hook ended the take at the cap", wr == MAX_FRAMES and st == ST_IDLE and status == 0,
          f"wr {wr}, state {st}, status {status}")
    data = take(card) or b""
    check("cap: the file holds the 50 frames", len(data) == 44 + 50 * 64, f"{len(data)} bytes")


def cut(s):
    """A take cut off mid-way, as a power cut or a card pull would: 1,500
    frames and no STOP, so the run ends while RECORDING, after the writer
    has streamed two chunks. What a computer would find on the card: the
    directory entry's length, and whether the take's data can be read."""
    log, _, card, words, _ = port(s, 1500, tag="cut", dump_blocks=False)
    st, status, _, wr, rd, nfr = words
    files = card_files(card)
    fx = json.loads(FIXTURE.read_text())
    names = new_entries(files)
    data = card_get(files, f"{fx['set']}/AUDIO/{names[0]}/T1.wav") if len(names) == 1 else None
    # Records a fact rather than a wish (26 Sep 2026): the file's length is
    # set only at the end, so a cut-off take is a 0-byte file even though
    # the writer had streamed most of it. A change here means the writer
    # started setting the length during the take.
    check("cut: a take cut off mid-way is a 0-byte T1.wav, its streamed audio unreachable (known)",
          st == ST_RECORDING and rd >= 2 * CHUNK_FRAMES and data is not None and len(data) == 0,
          f"state {st}, {nfr} frames recorded, {rd} streamed, T1.wav {None if data is None else len(data)} bytes")


FIXTURE8 = pathlib.Path("out/stems_fixture8.json")   # tools/verify/stems_fixture.py --eight
FIXTURE32 = pathlib.Path("out/stems_fixture32.json")   # tools/verify/stems_fixture.py --fat32
CARD_READY = 0x460d1cb8     # emu_card.FW_CARD_READY: := 1 after the firmware's card init and mount
SUFFIX = ""                 # appended to every run's tag: "32" while the FAT32 checks run


def run_path(tag, ext):
    """A file a run wrote: out/stems_runs/<tag><SUFFIX>.<ext>."""
    return pathlib.Path("out/stems_runs") / f"{tag}{SUFFIX}.{ext}"


def take_files(card_path, fixture=FIXTURE):
    """Every .wav in the one new take folder, as [(name, bytes)] sorted by
    name (T1 first), or [] when there is not exactly one new folder."""
    files = card_files(card_path)
    fx = json.loads(pathlib.Path(fixture).read_text())
    names = new_entries(files, fixture)
    if len(names) != 1:
        return []
    folder = f"{fx['set']}/AUDIO/{names[0]}/".lower()
    return sorted((p[len(folder):], d) for p, d in files.items()
                  if p.lower().startswith(folder) and "/" not in p[len(folder):]
                  and p.upper().endswith(".WAV"))


def slot_frames(dump_path, k):
    """Track k's (0-based) 16-bit stereo frames from a --block-dump, like t1_frames."""
    import blockdump
    ram_for = (0x80003190, 0x80003590) if k < 4 else (0x80003390, 0x80003790)
    base = (k % 4) * 0x40
    out = []
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram in ram_for and d == READBACK_DIR:
            out.append((frame, [x - 65536 if x >= 32768 else x for x in w[base:base + 64:2]]))
    return [s for _, s in sorted(out)]


def eight(s):
    """stems_tracks = 0xFF before the arm: eight files, each equal to its
    own read-back slot at one fixed lag, and no two alike. The hook latches
    the mask on the first playing frame, so the poke must land before play;
    the fixture's sounds play only their first four frames under the port
    (frames 44-47), so a take that starts later holds silence, which
    matches any slot at any lag. Each file must also be loud."""
    if not FIXTURE8.exists():
        check("eight: the 8-track fixture exists (stems_fixture.py --eight)", False)
        return
    log, dump, card, words, _ = port(s, 400, stop_at=300, tag="eight", fixture=FIXTURE8,
                                     pokes_before=[(s["stems_tracks"] + 3, 0xff)])
    st, status, _, wr, rd, nfr = words
    check("eight: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    files = take_files(card, FIXTURE8)
    check("eight: eight files, T1 to T8", [n.upper() for n, _ in files] == [f"T{i}.WAV" for i in range(1, 9)],
          f"{[n for n, _ in files]}")
    datas = []
    for k, (name, data) in enumerate(files[:8]):
        got = [[int.from_bytes(data[44 + f * 64 + 2 * j:44 + f * 64 + 2 * j + 2], "little", signed=True)
                for j in range(32)] for f in range((len(data) - 44) // 64)]
        want = slot_frames(dump, k)
        lag = next((L for L in range(len(want) - len(got) + 1) if want[L:L + len(got)] == got), None)
        peak = max((abs(x) for f in got for x in f), default=0)
        check(f"eight: {name} equals track {k + 1}'s read-back at one fixed lag, and is not silence",
              lag is not None and peak > 0, f"lag {lag}, {len(got)} frames, peak {peak}")
        datas.append(data[44:])
    check("eight: no two files alike", len(set(datas)) == len(datas), f"{len(set(datas))} distinct of {len(datas)}")


ERR_OVERFLOW, ERR_EXISTS, ERR_WRITE = 1, 4, 5
RING_SIZE = 0x400000
DRIVER_DRQ_POLL = 0x40014cf4             # the stock write command's wait for DRQ (STEM_REC.md 11.4)
OVERFLOW_FRAMES = 4000                   # the task writes the whole 4 MiB ring after the guard


def watched(s, extra=(), span=8):
    """--watch-mem on the state words from stems_state on, `span` bytes:
    every write, in order, so a run can see a value the next arm clears.
    8 covers the state and the status; 24 adds the write index and the
    frame count, which the hook writes every frame."""
    return ("--watch-mem", f"0x{s['stems_state']:x},{span}", *extra)


def writes(s, log, span=8):
    """(sample, word, value) for every watched write: word 0 = state,
    1 = status, 3 = stems_wr, 5 = stems_frames."""
    out = []
    for l in log.splitlines():
        if "] <- " not in l or "[0x" not in l:
            continue
        try:
            sample = float(l.split("[", 1)[1].split("]", 1)[0])
            addr = int(l.split("[0x", 1)[1].split("]", 1)[0], 16)
            val = int(l.split("<- ", 1)[1].split()[0], 0)
        except ValueError:
            continue
        if s["stems_state"] <= addr < s["stems_state"] + span:
            out.append((sample, (addr - s["stems_state"]) // 4, val))
    return out


CARD_OUT = re.compile(r"^card out\s*:.*\((\d+) bytes, (\d+) sector\(s\) written by the firmware\)")
CARD_OUT_UPSTREAM = ("card out   : out/stems_runs/cardfail.img "
                     "(67108864 bytes, 23 sector(s) written by the firmware)")
CARD_OUT_CROSSCHECK = "card out   : out/stems_runs/cardfail.img (23 sectors written in the run)"


def card_out_sectors(log):
    """The sector count on the port's `card out` line, or None when no line
    has upstream's form. crosscheck's port printed "(23 sectors written in
    the run)", and its parse -- the first word after "(" -- would read the
    BYTE count from upstream's line and pass cardfail whatever happened."""
    for line in log.splitlines():
        m = CARD_OUT.match(line)
        if m:
            return int(m.group(2))
    return None


def take(card_path):
    """The one new take's T1.wav on a card, or None."""
    files = card_files(card_path)
    fx = json.loads(FIXTURE.read_text())
    names = new_entries(files)
    return card_get(files, f"{fx['set']}/AUDIO/{names[0]}/T1.wav") if len(names) == 1 else None


LIMIT_FRAMES = 55300                     # the --long take: about 20 s, past the old cap of 41,344


def limit(s):
    """A 20-second take, stopped by STOP: past the old 15-second cap. T1's
    ring (65,536 frames) does not wrap in 20 s, so the file's data must equal
    the ring's first frames with each 16-bit word byte-swapped: the ring is
    big-endian, the file little-endian. A sector sent twice or lost keeps
    the size and fails this."""
    import array
    frames = PRE_ROLL + LIMIT_FRAMES + 200
    log, _, card, words, ring = port(s, frames, stop_at=PRE_ROLL + LIMIT_FRAMES, tag="limit",
                                     dump_blocks=False, extra=watched(s), ring_bytes=RING_SIZE_T1)
    st, status, _, wr, rd, nfr = words
    check("limit: past the old cap of 41,344 frames", nfr > 41344, f"{nfr} frames")
    check("limit: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    data = take(card)
    n = 64 * nfr
    dlen = int.from_bytes(data[40:44], "little") if data and len(data) >= 44 else None
    check("limit: the file holds every frame", dlen == n and len(data) == 44 + dlen,
          f"data {dlen}, file {len(data) if data else None}")
    want = array.array("H", ring[:n])
    want.byteswap()
    want = want.tobytes()
    same = data is not None and len(want) == n and data[44:] == want
    bad = None
    if data is not None and not same:
        bad = next((i for i in range(0, min(len(want), len(data) - 44), 512)
                    if data[44 + i:44 + i + 512] != want[i:i + 512]), None)
    check("limit: the file's data is the ring, byte for byte", same,
          "" if same else f"first differing 512-byte block at data offset {bad}")


def exists(s):
    """A second take on the first take's card, in the same minute: refused,
    and the first take is untouched. Every port take is 000000-0000 (the
    port's clock reads 0, STEM_REC.md 11.2), so the minute is the same."""
    first = run_path("full", "img")
    if not first.exists():
        print("  [SKIP] exists: needs the full run's card")
        return
    before = take(first)
    log, _, card, words, _ = port(s, 700, stop_at=400, tag="exists", card_in=str(first),
                                  dump_blocks=False)
    st, status, _, wr, rd, nfr = words
    check("exists: refused with ERR_EXISTS, state IDLE", st == ST_IDLE and status == ERR_EXISTS,
          f"state {st}, status {status}")
    after = take(card)
    check("exists: the first take is byte-identical", before is not None and after == before,
          f"{len(before) if before else None} bytes before, {len(after) if after else None} after")


def overflow(s):
    """The writer held (stems_hold, a test seam) and the ring made to look
    nearly full after the action: rd poked 65,436 frames behind wr, and
    rd_off 100 frames past wr_off. The hook stops with ERR_OVERFLOW once
    100 frames are in. FINISHING ignores the hold, so the task writes all
    65,536 frames and closes a playable file. A STOP, then the row, arms
    again: the task came back to IDLE."""
    used = 65536 - 100
    rd = (-used) & 0xffffffff
    rd_off = 100 * 64
    pokes = [(s["stems_hold"] + 3, 1)]
    pokes += [(s["stems_rd"] + i, (rd >> (24 - 8 * i)) & 0xff) for i in range(4)]
    pokes += [(s["stems_rd_off"] + i, (rd_off >> (24 - 8 * i)) & 0xff) for i in range(4)]
    log, _, card, words, _ = port(s, OVERFLOW_FRAMES, stop_at=OVERFLOW_FRAMES - 400, tag="overflow",
                                  pokes=pokes, dump_blocks=False,
                                  calls=((OVERFLOW_FRAMES - 200, s["stems_action"]),),
                                  extra=watched(s, span=24))
    st, status, _, wr, rd_end, _ = words
    ws = writes(s, log, span=24)
    statuses = [v for x, w, v in ws if w == 1]
    states = [v for x, w, v in ws if w == 0]
    wrs = [v for x, w, v in ws if w == 3]
    check("overflow: the hook stopped with ERR_OVERFLOW", ERR_OVERFLOW in statuses,
          f"status writes {statuses}")
    check("overflow: 100 frames, then the guard", 100 in wrs and 101 not in wrs, f"wr reached {max(wrs, default=0)}")
    data = take(card) or b""
    ok = len(data) >= 44 and int.from_bytes(data[40:44], "little") == len(data) - 44 == 65536 * 64
    check("overflow: the file holds the whole ring and its header agrees", ok,
          f"{len(data)} bytes")
    check("overflow: the task wrote and went IDLE, and the row armed again",
          states[-2:] == [ST_IDLE, ST_ARMED] and st == ST_ARMED, f"state writes {states}, state {st}")


def cardfail(s):
    """Every card write after the 20th is refused, as a card answers an
    aborted command: ERR and ABRT, no DRQ. The stock driver's write command
    waits for DRQ at 0x40014cf4 with no error check and no timeout, so the
    writer task hangs there, holding the file layer's lock (STEM_REC.md
    11.4). This run RECORDS that fact rather than expecting a recovery: a
    change here means the driver's answer, or the port's card model,
    changed."""
    work = pathlib.Path("out/stems_runs")
    cov = work / "cardfail.cov"
    log, _, card, words, _ = port(s, 700, stop_at=400, tag="cardfail", dump_blocks=False,
                                  extra=watched(s, ("--card-fail-after", "20", "--coverage", str(cov))))
    st, status, _, wr, rd, nfr = words
    polls = 0
    if cov.exists():
        polls = next((int(n) for a, n in (l.split() for l in cov.read_text().splitlines())
                      if int(a, 16) == DRIVER_DRQ_POLL), 0)
    sectors = card_out_sectors(log)
    # The port refuses a command that STARTS at or past the 20th sector; a
    # raw write of several sectors that starts below it completes.
    check("cardfail: a refused raw write hangs the writer in the stock driver's DRQ poll (known)",
          st == ST_FINISHING and sectors is not None and sectors >= 20 and polls > 100000,
          f"state {st}, {sectors if sectors is not None else 'no card-out line in upstream form:'} "
          f"sectors written, {polls} polls at 0x{DRIVER_DRQ_POLL:x}")


def probe(s):
    """The five raw file routines, measured (STEM_REC.md 12.1). The action
    is called twice before play (arm, then cancel), so the writer task
    exists and is IDLE; stems_probe = 1 makes it run the probe once. The
    probe writes <set>/PROBE.BIN: sectors 0xAA 0xAA 0xAA with one raw
    write, then 0xBB with a second (does the position advance?), then a
    seek to 0 and 0xCC over sector 0, then length 1000, then close."""
    res = s["stems_probe_res"]
    pokes = [(s["stems_probe"] + 3, 1)]
    log, _, card, _, _ = port(s, 300, tag="probe", pokes=pokes, dump_blocks=False,
                              mems=((res, 28, "res"),),
                              calls_before=(s["stems_action"], s["stems_action"]))
    raw = run_path("probe", "res").read_bytes() if \
        run_path("probe", "res").exists() else b"\0" * 28
    r = [int.from_bytes(raw[i:i + 4], "big", signed=True) for i in range(0, 28, 4)]
    check("probe: raw open returned a handle", 1 <= r[0] <= 511, f"d0 {r[0]}")
    check("probe: raw write of 3 sectors", r[1] >= 0, f"d0 {r[1]}")
    check("probe: raw write of 1 more sector", r[2] >= 0, f"d0 {r[2]}")
    check("probe: raw seek to 0", r[3] >= 0, f"d0 {r[3]}")
    check("probe: raw write over sector 0", r[4] >= 0, f"d0 {r[4]}")
    check("probe: set length 1000", r[5] >= 0, f"d0 {r[5]}")
    check("probe: raw close", r[6] >= 0, f"d0 {r[6]}")
    fx = json.loads(FIXTURE.read_text())
    data = card_get(card_files(card), f"{fx['set']}/PROBE.BIN")
    check("probe: the file is exactly 1000 bytes (set length, shorter than written)",
          data is not None and len(data) == 1000, f"{None if data is None else len(data)} bytes")
    if data is not None and len(data) == 1000:
        check("probe: sector 0 is the rewrite (seek + write)", data[:512] == b"\xcc" * 512,
              f"first bytes {data[:4].hex()}")
        check("probe: sector 1 survived the rewrite, and the position advanced",
              data[512:1000] == b"\xaa" * 488, f"bytes 512.. {data[512:516].hex()}")


def fat32(s):
    """The take checks on a FAT32 card (the unit's card is FAT32; every take
    before this ran on FAT16). First the mount byte, on the FAT16 card as a
    control and then on the FAT32 card: if the firmware did not mount the
    card, one check says so and no take check runs, since each would fail on
    'no new recording' for that one reason."""
    global FIXTURE, SUFFIX
    if not FIXTURE32.exists():
        check("fat32: the FAT32 fixture exists (stems_fixture.py --fat32)", False)
        return
    ready = {}
    for fixture, tag in ((FIXTURE, "mount16"), (FIXTURE32, "mount32")):
        port(s, 50, tag=tag, dump_blocks=False, fixture=fixture, mems=((CARD_READY, 4, "ready"),))
        raw = run_path(tag, "ready")
        ready[tag] = raw.read_bytes() if raw.exists() else b""
    # The flag is a 32-bit word (big-endian), 1 once mounted: its first
    # byte is 0 either way (27 Sep 2026, both cards read 00000001).
    word = {t: int.from_bytes(b[:4], "big") if len(b) >= 4 else None for t, b in ready.items()}
    check("fat32: control -- the FAT16 card reads as mounted", word["mount16"] == 1,
          ready["mount16"].hex())
    mounted = word["mount32"] == 1
    check("fat32: the firmware mounted the FAT32 card", mounted, ready["mount32"].hex())
    if not (mounted and word["mount16"] == 1):
        return
    saved = FIXTURE
    FIXTURE, SUFFIX = FIXTURE32, "32"
    try:
        print("  -- the take checks on FAT32 --")
        probe(s)
        full(s)
        rowstop(s)
        stream(s)
        wrap(s)
        cap(s)
        cut(s)
        exists(s)
        overflow(s)
    finally:
        FIXTURE, SUFFIX = saved, ""


def main():
    from remix import registry
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    name = args[0] if args else "stems"
    if "STEM REC" not in registry.remix(name).modules:
        print(f"  [ -- ] {name} does not carry STEM REC -- nothing to check")
        return 0
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], capture_output=True, text=True, env=env)
    if r.returncode:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    img, stock, s = IMAGE.read_bytes(), STOCK.read_bytes(), syms()
    static(img, stock, s)
    regions(s)
    check("the card-out parse reads upstream's line and refuses crosscheck's",
          card_out_sectors(CARD_OUT_UPSTREAM) == 23 and card_out_sectors(CARD_OUT_CROSSCHECK) is None)
    if EMU.exists() and FIXTURE.exists():
        probe(s)
        tap(s)
        full(s)
        rowstop(s)
        stream(s)
        wrap(s)
        cap(s)
        eight(s)
        cut(s)
        exists(s)
        overflow(s)
        cardfail(s)
        if "--long" in sys.argv:
            limit(s)
        if "--fat32" in sys.argv:
            fat32(s)
    else:
        print("  [SKIP] port runs: build the port (make emu-cf) and the fixture "
              "(python3 tools/verify/stems_fixture.py)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
