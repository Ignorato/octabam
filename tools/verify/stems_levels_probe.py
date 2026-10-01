#!/usr/bin/env python3
"""STEM REC piece 5, probes 1-2: the level words the ColdFire hands core 0.

    python3 tools/verify/stems_levels_probe.py one|thru [--poke ADDR=VAL@FRAME ...]

Runs the port on a fixture card and prints, at the run's end: the page
indexes 0x80004800 (written) and 0x80004804 (sent by channel 0), the four
level pages at 0x80005460 (and the page after them, which is not one), the DSP's copy at X:0x4800, core 0's targets
(Y:0x00-0x13), its ramp state (X:0x3dd, five words a slot), whether the
table words at 0x400ea18a still equal the image's (with a known string of
the image beside them, to tell memory reused from memory not mapped), and which instructions
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
PAGES, NPAGES, PAGE = 0x80005460, 4, 0x80   # four level pages; the index passes 4 and wraps inside one frame
TABLE = 0x400ea18a                      # X:0x6c00's words in the image, 3 bytes LE
NAME_FMT = 0x400b77bb                   # "%02d%02d%02d-%02d%02d", read by STEM REC at run time
WORK = ROOT / "out/stems_runs"
WATCH = re.compile(r"\s*\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \((\d)\) at pc (0x[0-9a-f]+)")


def table_words(img, n=258):
    off = TABLE - BASE
    return [int.from_bytes(img[off + 3 * i:off + 3 * i + 3], "little") for i in range(n)]


def peeks(log, space, addr):
    """The words of one --dsp-peek line. The port prints the address with
    %#07x, which writes address 0 as 0000000, not 0x00000."""
    for m in re.finditer(rf"core 0 {space}:(0x[0-9a-f]+|0+):((?: [0-9a-f]{{6}})+)", log):
        if int(m.group(1), 16) == addr:
            return [int(w, 16) for w in m.group(2).split()]
    return []


def run(fixture_json, frames=300, extra=()):
    fx = json.loads(pathlib.Path(fixture_json).read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    tag = pathlib.Path(fixture_json).stem
    sram, tab, idx = WORK / f"lv_{tag}.sram", WORK / f"lv_{tag}.tab", WORK / f"lv_{tag}.idx"
    fmt = WORK / f"lv_{tag}.fmt"
    w29 = ";".join(f"0x{PAGES + p * PAGE + 2 * 0x29:x},2" for p in range(NPAGES))
    args = [str(EMU), "--image", str(IMAGE), "--card", fx["card"], "--set", fx["set"],
            "--project", fx["project"], "--sequencer", "--internal-clock", "--frames", str(frames),
            "--load-ms", "20000", "--dsp", "--main-level", "64", "--pre-roll", "40", "--poke-trig", "2",
            "--mem-dump", f"0x80004800,8={idx};0x{PAGES:x},{(NPAGES + 1) * PAGE}={sram};"
                          f"0x{TABLE:x},{258 * 3}={tab};0x{NAME_FMT:x},24={fmt}",
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
            "image_string": fmt.read_bytes().split(b"\0")[0] if fmt.exists() else b"",
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
    for p in range(NPAGES + 1):
        pg = res["pages"][p * PAGE:(p + 1) * PAGE]
        print(f"page {p}: " + " ".join(f"{int.from_bytes(pg[i:i + 2], 'big'):04x}" for i in range(0, 0x58, 2)))
    print("X:0x4800 ", " ".join(f"{w:06x}" for w in res["dsp_x4800"]))
    print("Y targets", " ".join(f"{w:06x}" for w in res["dsp_targets"]))
    print("X:0x3dd  ", " ".join(f"{w:06x}" for w in res["dsp_state"]))
    print(f"table words unchanged at run end: {res['table_ok']}; the image's name format reads {res['image_string']!r}")
    print(f"writers of a page's MAIN level halfword: {sorted(res['w29_writers'])}")


if __name__ == "__main__":
    main()
