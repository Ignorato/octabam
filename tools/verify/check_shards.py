#!/usr/bin/env python3
"""The per-remix half of `make check` for several remixes, N worktrees at a time.

    python3 tools/verify/check_shards.py [--jobs N] [--keep] [--shards DIR] <remix> ...
    make check-remixes REMIXES="a b c" [JOBS=4]
    make reach RUN=1 JOBS=4            # the check-remix lines through this
    python3 tools/verify/check_shards.py --by-gate [--jobs N] <remix>
    make check-remix-gates REMIX=<name> [JOBS=4]

Every `make check-remix` builds over out/mainos_bus.bin and its verifiers
read out/, so one tree runs one remix at a time; PR #486's 25-remix table
was three worktrees driven by hand. This makes N detached worktrees of HEAD
plus the tree's uncommitted changes under out/shards/<i>, each with the
shared vendor/ and .venv/ links, the stock slice, its submodules and its
OWN port build (out/emu is never shared between trees: AGENTS.md), then
hands the remixes out from one queue as shards come free, so the dear ones
(bottleservice, rig-kits) do not decide the wall time. Logs land in
out/check_shards/<remix>.log; one table at the end; exit 1 when a remix
failed. The shards are removed unless --keep.

`--by-gate` shards ONE remix's per-remix half by gate instead: every gate
of `make verify-remix` (plus `make cycles`) is its own job, each shard
restores the remix's image with `make bus` before its job, and the wall
is the longest gate rather than the whole list. The gates never read one
another's results; they only ever shared out/. Two exceptions are kept in
one job: verify_set stages the card that the image-stage module gates
(TEMPO BUS) boot, so those follow it in its shard. The job list mirrors
the `verify-remix` recipe and refuses to run when the two name different
scripts.
"""
import argparse
import os
import pathlib
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP = re.compile(r"^\s*(?:\[SKIP\]|SKIP:)")


def git(*args, cwd=ROOT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def make_shard(path, log):
    """A detached worktree of HEAD with this tree's uncommitted changes, the
    shared toolchain links, the stock slice, its submodules and its own
    port build."""
    remove_shard(path)
    git("worktree", "add", "--detach", str(path), "HEAD")
    diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--ignore-submodules=all"],
                          cwd=ROOT, capture_output=True, check=True).stdout
    if diff.strip():
        subprocess.run(["git", "apply", "--binary"], cwd=path, input=diff, check=True)
    for rel in git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0"):
        if rel and (ROOT / rel).is_file():
            (path / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, path / rel)
    for name in ("vendor", ".venv"):
        if (ROOT / name).exists():
            os.symlink(os.path.realpath(ROOT / name), path / name)
    (path / "out/raw").mkdir(parents=True)
    shutil.copy2(ROOT / "out/raw/section_3_MAIN_OS.bin", path / "out/raw/section_3_MAIN_OS.bin")
    with log.open("w") as f:
        for cmd in (["git", "submodule", "update", "--init"], ["make", "emu-cf"]):
            f.write(f"$ {' '.join(cmd)}\n")
            f.flush()
            r = subprocess.run(cmd, cwd=path, stdout=f, stderr=subprocess.STDOUT, env=clean_env())
            if r.returncode:
                raise SystemExit(f"check_shards: {' '.join(cmd)} failed in {path} ({r.returncode}): {log}")


def remove_shard(path):
    if path.exists():
        git("worktree", "remove", "--force", str(path), check=False)
        shutil.rmtree(path, ignore_errors=True)
    git("worktree", "prune", check=False)


def clean_env():
    env = dict(os.environ)
    for var in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"):
        env.pop(var, None)
    # every shard builds from this tree's memo (tools/remix/runtime_build.CACHE)
    env.setdefault("OCTABAM_CACHE", str(ROOT / "out/cache"))
    return env


def run_remix(shard, remix, logdir):
    log = logdir / f"{remix}.log"
    t0 = time.monotonic()
    with log.open("w") as f:
        r = subprocess.run(["make", "check-remix", f"REMIX={remix}"], cwd=shard,
                           stdout=f, stderr=subprocess.STDOUT, env=clean_env())
    text = log.read_text(errors="replace")
    skips = [l.strip() for l in text.splitlines() if SKIP.match(l)]
    return dict(remix=remix, rc=r.returncode, seconds=time.monotonic() - t0, skips=skips, log=log)


def remix_jobs(remix_name, shard):
    """The per-remix half as independent jobs: (name, [argv, ...], env).
    Mirrors `make verify-remix` + `make cycles`; `check_recipe` refuses drift."""
    sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
    from remix import registry  # noqa: E402
    import module_gates  # noqa: E402
    py = sys.executable
    venv = shard / ".venv/bin/python3"       # the shard links ROOT's .venv
    has_venv = (ROOT / ".venv/bin/python3").exists()
    PY = str(venv) if has_venv else py        # the Makefile's $(PY)
    env = {"REMIX": remix_name, "BUILD": os.environ.get("BUILD", "0")}
    V = "tools/verify"
    jobs = [
        ("cycles", [["make", "cycles", f"REMIX={remix_name}"]], env),
        ("dirtystate", [[py, f"{V}/verify_dirtystate.py", remix_name]], env),
        ("initregs", [[py, f"{V}/verify_initregs.py", remix_name]], env),
        ("dram_boot", [[py, f"{V}/verify_dram_boot.py"]], env),
    ]
    for name in ("labels", "modenames", "hidden"):
        jobs.append((name, [[str(venv), f"{V}/verify_{name}.py", remix_name]] if has_venv
                     else [["echo", f"  [SKIP] {name}: no .venv (make emu-setup)"]], env))
    remix = registry.remix(remix_name)
    for key, g in module_gates.collect(registry.selected(remix), "isolated", True):
        # As `make verify-remix` runs them: module_gates.py under $(PY), so a
        # gate without `venv` inherits the driver's interpreter. The script
        # path is relative so it runs in the shard's own tree.
        cmd = module_gates.command(g, remix_name, root=ROOT)
        cmd[0] = cmd[0] if g.venv else PY
        cmd[1] = str(g.script)
        jobs.append((f"gate:{pathlib.Path(g.script).stem}", [cmd], env))
    jobs.append(("menu", [[py, f"{V}/verify_menu.py"]], env))
    jobs.append(("set", [[py, f"{V}/verify_set.py", remix_name],
                         ["make", "bus", f"REMIX={remix_name}"],
                         [PY, f"{V}/module_gates.py", remix_name, "--stage", "image"]], env))
    jobs.append(("usb", [[py, f"{V}/verify_usb.py"]], env))
    return jobs


def check_recipe(jobs):
    """Every script the Makefile's verify-remix recipe runs is in the job
    list (module_gates.py stands for the gates it runs)."""
    sys.path.insert(0, str(ROOT / "tools/verify"))
    from reach import recipe_scripts  # noqa: E402
    recipe = recipe_scripts((ROOT / "Makefile").read_text(), "verify-remix")
    named = {str(c[1]) for _n, cmds, _e in jobs for c in cmds if len(c) > 1} | {"tools/verify/module_gates.py"}
    missing = recipe - named
    if missing:
        raise SystemExit(f"check_shards: verify-remix runs {sorted(missing)} and the by-gate job list does not; "
                         f"add the job (check_shards.remix_jobs)")


def run_job(shard, remix, job, logdir):
    name, cmds, env_add = job
    log = logdir / f"{name.replace(':', '_')}.log"
    env = clean_env()
    env.update(env_add)
    t0 = time.monotonic()
    rc = 0
    with log.open("w") as f:
        for cmd in [["make", "bus", f"REMIX={remix}"]] + cmds:
            f.write(f"$ {' '.join(cmd)}\n")
            f.flush()
            r = subprocess.run(cmd, cwd=shard, stdout=f, stderr=subprocess.STDOUT, env=env)
            if r.returncode:
                rc = r.returncode
                break
    text = log.read_text(errors="replace")
    skips = [l.strip() for l in text.splitlines() if SKIP.match(l)]
    return dict(remix=name, rc=rc, seconds=time.monotonic() - t0, skips=skips, log=log)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remixes", nargs="+")
    ap.add_argument("--jobs", type=int, default=4, help="worktrees at a time")
    ap.add_argument("--shards", type=pathlib.Path, default=ROOT / "out/shards")
    ap.add_argument("--keep", action="store_true", help="leave the shard worktrees for a look")
    ap.add_argument("--by-gate", action="store_true",
                    help="one remix: its per-remix half as one job per gate over the shards")
    a = ap.parse_args(argv)
    remixes = list(dict.fromkeys(a.remixes))
    if not (ROOT / "out/raw/section_3_MAIN_OS.bin").is_file():
        sys.exit("check_shards: out/raw/section_3_MAIN_OS.bin is missing (make os && make recon)")
    if a.by_gate:
        if len(remixes) != 1:
            sys.exit("check_shards: --by-gate takes exactly one remix")
        gate_jobs = remix_jobs(remixes[0], a.shards / "0")
        check_recipe(gate_jobs)
    work = gate_jobs if a.by_gate else remixes
    jobs = max(1, min(a.jobs, len(work)))
    a.shards.mkdir(parents=True, exist_ok=True)
    logdir = ROOT / "out/check_shards" / (remixes[0] if a.by_gate else "")
    logdir.mkdir(parents=True, exist_ok=True)
    shards = [a.shards / str(i) for i in range(jobs)]

    what = f"{len(work)} gates of {remixes[0]}" if a.by_gate else f"{len(remixes)} remixes"
    print(f"check_shards: {what} over {jobs} shards under {a.shards} (setup: submodules + make emu-cf each)", flush=True)
    errors = []

    def setup(i):
        try:
            make_shard(shards[i], a.shards / f"{i}.setup.log")
        except (SystemExit, subprocess.CalledProcessError, OSError) as exc:
            errors.append(str(exc))
    threads = [threading.Thread(target=setup, args=(i,)) for i in range(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        sys.exit("check_shards: " + "; ".join(errors))

    todo = queue.Queue()
    for w in work:
        todo.put(w)
    results = {}
    lock = threading.Lock()

    def worker(i):
        while True:
            try:
                item = todo.get_nowait()
            except queue.Empty:
                return
            if a.by_gate:
                res = run_job(shards[i], remixes[0], item, logdir)
                remix = item[0]
            else:
                remix = item
                res = run_remix(shards[i], remix, logdir)
            res["shard"] = i
            status = "ok" if res["rc"] == 0 else f"FAILED ({res['rc']})"
            with lock:
                results[remix] = res
                print(f"check_shards: {status:12} {res['seconds']:6.0f} s  {remix:20} shard {i}"
                      + (f"  {len(res['skips'])} SKIP" if res["skips"] else ""), flush=True)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(jobs)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.monotonic() - t0

    names = [j[0] for j in work] if a.by_gate else remixes
    print(f"\ncheck_shards: results ({wall:.0f} s wall, {sum(r['seconds'] for r in results.values()):.0f} s of "
          f"{'gate' if a.by_gate else 'remix'} time)")
    for remix in names:
        r = results[remix]
        status = "ok" if r["rc"] == 0 else f"FAILED ({r['rc']})"
        print(f"  {status:12} {r['seconds']:6.0f} s  {remix:20} {r['log'].relative_to(ROOT)}")
        for s in r["skips"]:
            print(f"               {s}")
    if not a.keep:
        for s in shards:
            remove_shard(s)
    bad = [r for r in results.values() if r["rc"]]
    unit = "gates" if a.by_gate else "remixes"
    if bad:
        print(f"check_shards: {len(bad)} of {len(results)} {unit} failed")
        return 1
    print(f"check_shards: every {'gate of ' + remixes[0] if a.by_gate else 'remix'} passed"
          + ("" if a.by_gate else " its per-remix half"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
