#!/usr/bin/env python3
"""Run the gates the selected remix's modules declare (schema.Gate).

    python3 tools/verify/module_gates.py <remix> --stage isolated|image [--list]

`make verify` runs the isolated stage before it restores the selected
image (those gates build their own scratch images, or none) and the image
stage after `make bus` and the shared set gates. A gate declared by two
modules of the selection (the bus's two-core gate, verify_usb) runs once.
The runner exports REMIX and BUILD; a gate with `remix_arg` gets the remix
name as argv[1]; one with `venv` runs under .venv/bin/python3 when that
exists (the port's python), else python3 -- the Makefile's $(PY).

A script that does not exist is a FAIL, not a skip: the manifest named a
gate the tree does not carry. A gate's own [SKIP] line stays its own.
"""
import argparse
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]


def collect(modules, stage):
    """The gates of `modules` for one stage, in selection order, each script once."""
    seen, out = set(), []
    for m in modules:
        for g in getattr(m, "gates", ()):
            if g.stage != stage or g.script in seen:
                continue
            seen.add(g.script)
            out.append((m.key, g))
    return out


def python_for(gate, root=ROOT):
    venv = root / ".venv/bin/python3"
    if gate.venv and os.access(venv, os.X_OK):
        return str(venv)
    return sys.executable


def command(gate, remix_name, root=ROOT):
    cmd = [python_for(gate, root), str(root / gate.script)]
    if gate.remix_arg:
        cmd.append(remix_name)
    return cmd


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--stage", choices=("isolated", "image"), default="isolated")
    ap.add_argument("--list", action="store_true", help="print the commands, run nothing")
    a = ap.parse_args(argv)
    remix = registry.remix(a.remix)
    gates = collect(registry.selected(remix), a.stage)
    env = dict(os.environ, REMIX=remix.name)
    env.setdefault("BUILD", "0")
    if not gates:
        print(f"module gates ({a.stage}): none declared by {remix.name}'s modules")
        return 0
    fails = []
    for key, g in gates:
        cmd = command(g, remix.name)
        if a.list:
            print(f"{key:16} {' '.join(pathlib.Path(c).name if i == 0 else c for i, c in enumerate(cmd))}")
            continue
        print(f"\n== {key}: {g.script}{' ' + remix.name if g.remix_arg else ''}", flush=True)
        if not (ROOT / g.script).is_file():
            print(f"  [FAIL] {g.script}: no such file (the manifest names a gate the tree does not carry)")
            fails.append(g.script)
            continue
        r = subprocess.run(cmd, cwd=ROOT, env=env)
        if r.returncode:
            print(f"  [FAIL] {g.script} exit {r.returncode}")
            fails.append(g.script)
    if a.list:
        return 0
    print(f"\nmodule gates ({a.stage}): {len(gates)} run, {len(fails)} failed"
          + (": " + ", ".join(fails) if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
