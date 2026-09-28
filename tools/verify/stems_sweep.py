#!/usr/bin/env python3
"""STEM REC against the emulated card's speed: which track counts the 4 MiB
ring survives at which card delay.

    python3 tools/verify/stems_sweep.py [--counts 1,2,4,8] [--latencies 8,16,24,32,48,64] [--seconds 5] [--jobs 2]

Each run is a take of --seconds on the THRU fixture (stems_fixture.py
--thru) under `ot_emu --ata-latency N` (samples between a card sector and
its interrupt; 8 is the port's default, STEM_REC.md 13.3). The delay slows
the project's load as well, so the load's budget grows with it. From the
port's watch log of the state words it reports the peak fill (frames, and
a share of the ring), whether and when the take overflowed, the writer's
rate while recording, and the fill's growth: the trend of its troughs (the
fill right after each chunk the writer takes) over the second half of the
recording, with the time left to overflow when it rises. The emulated card has a constant delay per sector; a
real card stalls, so this gives steady-rate limits only. Not a gate.

The runs are independent (each writes out/stems_runs/sweep-<n>t-<lat>.*),
so --jobs of them run side by side; a port run holds about 650 MB.
"""
import argparse
import concurrent.futures
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_stems as v  # noqa: E402

FPS = 44100 / 16            # frames a second
RING = 0x400000


def trend(points):
    """The least-squares slope of (seconds, frames) points, frames a second;
    None with fewer than two points (a slow writer takes few chunks)."""
    if len(points) < 2:
        return None
    mx = sum(x for x, _ in points) / len(points)
    my = sum(y for _, y in points) / len(points)
    sxx = sum((x - mx) ** 2 for x, _ in points)
    return sum((x - mx) * (y - my) for x, y in points) / sxx if sxx else 0.0


def run(s, n, lat, seconds):
    mask = (1 << n) - 1
    stop = int(seconds * FPS)
    tag = f"sweep-{n}t-{lat}"
    # The card's delay slows the project's load too (at 64, 20 s of
    # emulated time did not finish it: 28 Sep 2026). The port ends the load
    # once the engine is idle, so the budget grows with the delay for free.
    log, _, _, words, _ = v.port(s, stop + 300, stop_at=stop, tag=tag, fixture=v.FIXTURE_THRU,
                                 mask=mask, dump_blocks=False, load_ms=20000 * max(1, lat // 8),
                                 extra=(*v.watched(s, span=28), "--ata-latency", str(lat)))
    loaded = "LOAD PROJECT handled" in log
    ws = v.writes(s, log, span=28)
    t0 = next((x for x, w, val in ws if w == 0 and val == v.ST_RECORDING), None)
    fin = next((x for x, w, val in ws if w == 0 and val == v.ST_FINISHING), None)
    over = next((x for x, w, val in ws if w == 1 and val == v.ERR_OVERFLOW), None)
    end_x = over if over is not None else fin
    rframes = RING // (64 * n)
    # The fill is a sawtooth: one frame more every frame, a chunk less each
    # time the writer takes one. Its trend is the troughs': the fill right
    # after each stems_rd write, over the second half of the recording.
    wr, rd, fills, troughs = 0, 0, [], []
    for x, w, val in ws:
        if w == 3 and val:
            wr = val
            fills.append((x, wr - rd))
        elif w == 4:
            rd = val
            if t0 is not None and x >= t0 and (end_x is None or x <= end_x):
                troughs.append((x / 44100, wr - rd))
    peak = v.rebuilt_peak(ws)
    half = [p for p in troughs if troughs and p[0] >= (troughs[0][0] + troughs[-1][0]) / 2]
    slope = trend(half)
    last = next((f for x, f in reversed(fills) if end_x is None or x <= end_x), 0)
    rd_end = next((val for x, w, val in reversed(ws) if w == 4 and (end_x is None or x <= end_x)), 0)
    span_s = (end_x - t0) / 44100 if t0 is not None and end_x is not None else 0
    return {
        "tracks": n, "latency": lat, "loaded": loaded, "peak": peak, "peak_share": peak / rframes,
        "overflow_s": None if over is None or t0 is None else (over - t0) / 44100,
        "writer_MBps": rd_end * 64 * n / span_s / 1e6 if span_s else 0.0,
        "slope_fps": slope, "troughs": len(half),
        "to_overflow_s": (rframes - last) / slope if slope and slope > 0 and over is None else None,
        "state": words[0], "status": words[1],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", default="1,2,4,8")
    ap.add_argument("--latencies", default="8,16,24,32,48,64")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()
    env = {**os.environ, "REMIX": "stems", "XBUS": "1", "SPEC": "1"}
    subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env, check=True, capture_output=True)
    s = v.syms()
    if not v.fixtures():
        sys.exit(f"stems_sweep: no fixtures (a project template at {v.TEMPLATE}: STEMS_TEMPLATE=<dir>)")
    grid = [(n, lat) for n in map(int, a.counts.split(",")) for lat in map(int, a.latencies.split(","))]
    rows = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        futures = {pool.submit(run, s, n, lat, a.seconds): (n, lat) for n, lat in grid}
        for f in concurrent.futures.as_completed(futures):
            rows[futures[f]] = r = f.result()
            print(json.dumps(r), flush=True)
    rows = [rows[k] for k in grid]
    pathlib.Path("out/stems_sweep.json").write_text(json.dumps(rows, indent=2) + "\n")
    print("\n| Tracks | Latency | Peak fill | Overflow | Writer | Fill growth | To overflow |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        if not r["loaded"]:
            print(f"| {r['tracks']} | {r['latency']} | the project's load did not finish: no take |  |  |  |  |")
            continue
        print(f"| {r['tracks']} | {r['latency']} | {r['peak_share']:.0%} ({r['peak']:,}) | "
              f"{'at %.2f s' % r['overflow_s'] if r['overflow_s'] is not None else 'no'} | "
              f"{r['writer_MBps']:.2f} MB/s | "
              f"{'%+.0f frames/s' % r['slope_fps'] if r['slope_fps'] is not None else 'too few chunks'} | "
              f"{'%.1f s' % r['to_overflow_s'] if r['to_overflow_s'] else '-'} |")


if __name__ == "__main__":
    sys.exit(main())
