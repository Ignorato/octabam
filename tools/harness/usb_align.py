#!/usr/bin/env python3
"""The MAIN/CUE-to-track alignment of the twenty-channel USB stream, under the
ColdFire port.

USB AUDIO OUT TRACKS MAIN CUE reads channels 1-16 from the tracks' read-back
arena (the previous ping-pong bank) and 17-20 from the mixdown buffer (the
current pull), two sources with two timings. On hardware MAIN was heard
lagging the tracks (Bryan T, 25 Sep 2026), the amount unmeasured. This
stages the tone project (tools/harness/usb_sig_project.py: track N's left
channel at 200 + 100 N Hz, its right at +50) on a card, boots the remix
under the port, drains EP3 IN once the sequencer plays, and reads the lag of
MAIN L (channel 17) behind each track's left channel from the phase of that
track's tone in both, Goertzel at the known frequency over the same window:
lag = (phase_track - phase_main) / (2 pi f) samples, modulo the tone's
period. Eight tracks, eight periods: the one lag in [-4096, 4096] that fits
them all is reported, in samples and in 16-sample blocks; MAIN R against the
right channels likewise.

    tools/harness/usb_align.py [--source <project>] [--remix usb-audio] [--polls 12000]

The source project is the template usb_sig_project.py needs (a locally saved
Octatrack project; default OT_PROJECT or ~/.octabam_project). The remix must
carry USB AUDIO OUT TRACKS MAIN CUE and the tone project's FX modules (the
rig's: `usb-audio`). Needs the port (make emu-cf) and the .venv.
"""
import argparse
import cmath
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402
from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/usb_align"
FS = 44100
NCH = 20
FRAME_B = 4 * NCH
SEARCH = 4096                       # samples either side


def tone(track):
    """(left Hz, right Hz) of track 1..8, as usb_sig_project.py makes them."""
    f = 200 + 100 * track
    return f, f + 50


def goertzel(x, f):
    w = -2j * math.pi * f / FS
    return sum(v * cmath.exp(w * k) for k, v in enumerate(x))


def lag_fit(pairs):
    """pairs: (f, phase_track - phase_main). The lag in [-SEARCH, SEARCH] that
    fits every tone's residue best; returns (lag, rms residual in samples)."""
    best = None
    for d in range(-SEARCH, SEARCH + 1):
        err = 0.0
        for f, dphi in pairs:
            period = FS / f
            r = (dphi * period / (2 * math.pi) - d) % period
            r = min(r, period - r)
            err += r * r
        if best is None or err < best[1]:
            best = (d, err)
    return best[0], math.sqrt(best[1] / len(pairs))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=os.environ.get("OT_PROJECT") or
                    (pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
                     if pathlib.Path("~/.octabam_project").expanduser().is_file() else ""))
    ap.add_argument("--remix", default="usb-audio")
    ap.add_argument("--polls", type=int, default=12000, help="EP3 IN polls to drain once playing (250 us each)")
    ap.add_argument("--frames", type=int, default=24000, help="DSP frames the port runs after the transport start")
    ap.add_argument("--image", default="", help="a built image (default: build the remix)")
    a = ap.parse_args()
    if not a.source:
        sys.exit("usb_align: no source project (--source, OT_PROJECT or ~/.octabam_project)")
    if not EMU.exists() or not PY.exists():
        sys.exit("usb_align: needs the port (make emu-cf) and the .venv")
    remix = registry.remix(a.remix)
    if "USB AUDIO OUT TRACKS MAIN CUE" not in remix.modules:
        sys.exit(f"usb_align: {a.remix} does not carry USB AUDIO OUT TRACKS MAIN CUE")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    image = OUT / "image.bin"
    if a.image:
        shutil.copy2(a.image, image)
    else:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"usb_align: build failed\n{r.stdout[-800:]}{r.stderr[-800:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    proj = OUT / "project"
    r = subprocess.run([str(PY), "tools/harness/usb_sig_project.py", "--source", a.source, "--out", str(proj),
                        "--remix", a.remix], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"usb_align: usb_sig_project failed\n{r.stdout[-800:]}{r.stderr[-800:]}")
    audio = [f"{proj / 'AUDIO' / 'USBSIG' / f'T{t}.wav'}:AUDIO/USBSIG/T{t}.wav" for t in range(1, 9)]
    card = OUT / "card.img"
    cmd = [str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "USBSIG",
           "--tree", str(OUT / "tree"), "--out", str(card), "--image-mb", "64"]
    for x in audio:
        cmd += ["--audio", x]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"usb_align: stage_card failed\n{r.stdout[-800:]}{r.stderr[-800:]}")
    sock = f"/tmp/ot-align-{os.getpid()}.sock"
    log = OUT / "port.txt"
    with open(log, "w") as lf:
        emu = subprocess.Popen([str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM",
                                "--project", "USBSIG", "--sequencer", "--internal-clock", "--poke-trig", "2",
                                "--frames", str(a.frames), "--load-ms", "90000",
                                "--usb-host", sock, "--usb-hold-ms", "60000"],
                               cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
    raw = bytearray()
    try:
        b = usb_host.Bench(sock, timeout=120.0)
        usb_host.enumerate_device(b, hs=True)
        b.ctrl_nodata(0x01, 0x0b, 1, 4)                 # SET_INTERFACE 4 alt 1: EP3 IN up
        deadline = time.time() + 1200
        while "sequencer  : playing" not in log.read_text(errors="replace"):
            if emu.poll() is not None:
                sys.exit(f"usb_align: the port exited before the transport started -- {log}")
            if time.time() > deadline:
                sys.exit(f"usb_align: no transport start in 20 min -- {log}")
            b.ep_in(3, 1024)                            # keep the endpoint drained meanwhile
            time.sleep(0.05)
        print("transport started; draining", a.polls, "polls")
        empty = 0
        for _ in range(a.polls):
            data = b.ep_in(3, 1024)
            empty += not data
            raw += data
        b.sock.close()
    finally:
        try:
            emu.wait(timeout=600)
        except subprocess.TimeoutExpired:
            emu.kill()
    (OUT / "stream.pcm").write_bytes(raw)
    n = len(raw) // FRAME_B
    print(f"stream: {n} frames ({n / FS:.2f} s), {empty} empty polls, {log}")
    if n < 2 * FS:
        sys.exit("usb_align: less than two seconds of stream")
    # the steady state: the last second, one window for every channel
    start = n - FS
    ch = [[0] * FS for _ in range(NCH)]
    for i in range(FS):
        base = (start + i) * FRAME_B
        for c in range(NCH):
            w = int.from_bytes(raw[base + 4 * c:base + 4 * c + 4], "little")
            v = w >> 8
            ch[c][i] = v - (1 << 24) if v & 0x800000 else v
    for side, main_ch in (("L", 16), ("R", 17)):
        pairs, rows = [], []
        for t in range(1, 9):
            f = tone(t)[0 if side == "L" else 1]
            xt = goertzel(ch[2 * (t - 1) + (0 if side == "L" else 1)], f)
            xm = goertzel(ch[main_ch], f)
            if abs(xt) < 1e3 or abs(xm) < 1e3:
                rows.append(f"    T{t} {f} Hz: track {abs(xt):.3g} main {abs(xm):.3g} -- too weak, skipped")
                continue
            dphi = cmath.phase(xt) - cmath.phase(xm)
            period = FS / f
            rows.append(f"    T{t} {f} Hz: |track| {abs(xt) / FS * 2:.0f} |main| {abs(xm) / FS * 2:.0f}  "
                        f"lag mod {period:.1f} = {(dphi * period / (2 * math.pi)) % period:.2f} samples")
            pairs.append((f, dphi))
        print(f"MAIN {side} against the tracks' {side} channels:")
        print("\n".join(rows))
        if len(pairs) >= 3:
            d, res = lag_fit(pairs)
            print(f"  -> MAIN {side} lags the tracks by {d} samples = {d / 16:.3f} blocks (rms residual {res:.2f} samples over {len(pairs)} tones)")
        else:
            print("  -> too few tones to fit a lag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
