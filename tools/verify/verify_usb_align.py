#!/usr/bin/env python3
"""MAIN/CUE aligned with the tracks in the twenty-channel USB stream, under the
ColdFire port: tools/harness/usb_align.py must read a lag of 0 samples.

Runs the tone project (usb_sig_project.py) on the `usb-audio` remix, whose
FX modules the project stamps, whatever remix is under test: the property
belongs to USB AUDIO OUT TRACKS MAIN CUE's producer, not to the remix.
SKIPs without a source project (OT_PROJECT or ~/.octabam_project), the port
or the .venv.
"""
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    src = os.environ.get("OT_PROJECT", "")
    if not src and pathlib.Path("~/.octabam_project").expanduser().is_file():
        src = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not src:
        print("  [SKIP] verify_usb_align: no source project (OT_PROJECT=<dir> or ~/.octabam_project)")
        return 0
    if not (ROOT / "out/emu/ot_emu").is_file() or not (ROOT / ".venv/bin/python3").is_file():
        print("  [SKIP] verify_usb_align: needs the port (make emu-cf) and the .venv")
        return 0
    r = subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/harness/usb_align.py"),
                        "--source", src, "--remix", "usb-audio"], cwd=ROOT, capture_output=True, text=True)
    tail = "\n".join(("    " + l) for l in (r.stdout + r.stderr).strip().splitlines()[-6:])
    m = re.search(r"RESULT: MAIN lags the tracks by (-?\d+) samples .* over (\d+) tones", r.stdout)
    if r.returncode or not m:
        print(f"  [FAIL] verify_usb_align: usb_align exit {r.returncode}\n{tail}")
        return 1
    lag, ntones = int(m.group(1)), int(m.group(2))
    ok = lag == 0 and ntones >= 2
    print(f"  [{'PASS' if ok else 'FAIL'}] MAIN/CUE aligned with the tracks under the port: lag {lag} samples over {ntones} tones")
    if not ok:
        print(tail)
    print(f"verify_usb_align: {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
