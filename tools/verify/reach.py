#!/usr/bin/env python3
"""Which gates a change reaches: the diff against main, classified by path.

    python3 tools/verify/reach.py [--base origin/main] [--run] [--paths ...]
    make reach [BASE=origin/main] [RUN=1]

CONTRIBUTING's "every remix the change can reach" was worked out by hand:
a module's remixes from the selections, a build change's refhash, a
verifier's callers. This reads the changed paths (committed and not,
against the merge-base with `--base`) and prints the commands, one line
each, with the paths that put them there; `--run` runs them in order and
stops at the first failure. There is no default remix: a path
it cannot place, a shared gate or a build change reaches EVERY remix, and
an unclassified path is named as such.

It refuses a tree that is not rebased onto the base (the base must be an
ancestor of HEAD): gates run before a rebase are not a result (PR #396).
CI runs the dry form on every pull request so the expected local gates are
in the job log; it has no firmware, so it runs none of them.

Two or more remixes to check are printed as one `make check-shared
REMIXES="..."` (the ledger selftest, the knob census and the isolated
module gates that build their own image: once) and a `make check-remix
REMIX=<r>` each (its build, cycles, dirty state, init regs, DRAM boot,
labels, its own module gates, menu, the set under the port, USB). One
remix stays `make check`. The two halves together are `make check`.
"""
import argparse
import fnmatch
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]

# One command per gate; the order is the order they run in.
ORDER = ("verify_docs", "selftest", "test-acceptance", "ci-dsp", "ci-emu", "emu-cf", "refhash", "check-shared", "check", "check-remix", "accept", "ci")


def cmd_check(remix):
    return ("check", f"make check REMIX={remix}")


def cmd_accept(remix):
    return ("accept", f"make accept REMIX={remix} STRESS_SOURCE=${{STRESS_SOURCE}}")


CMD = {
    "verify_docs": ("verify_docs", "python3 tools/verify/verify_docs.py"),
    "selftest": ("selftest", "python3 tools/remix/selftest.py"),
    "test-acceptance": ("test-acceptance", "make test-acceptance"),
    "ci-dsp": ("ci-dsp", "make ci-dsp"),
    "ci-emu": ("ci-emu", "make ci-emu"),
    "emu-cf": ("emu-cf", "make emu-cf"),
    "refhash": ("refhash", "scripts/refhash.sh check"),
    "ci": ("ci", "make ci"),
}


class Context:
    """What the classifier needs from the registry, so tests can fake it."""

    def __init__(self, module_key, remixes_of, gate_owners, remixes, exists=None):
        self.module_key = module_key        # module directory -> key
        self.remixes_of = remixes_of        # key -> sorted remix names carrying it
        self.gate_owners = gate_owners      # verifier path -> keys whose manifests name it
        self.remixes = remixes              # every remix: the floor, since nothing is the default
        self.exists = exists or (lambda path: (ROOT / path).exists())

    def every(self):
        return [cmd_check(r) for r in self.remixes]

    @classmethod
    def from_registry(cls):
        from remix import registry
        mods = registry.modules()
        module_key = {m.name: m.key for m in mods.values()}
        remixes_of = {k: [] for k in mods}
        for name in registry.remix_names():
            for k in registry.remix(name).modules:
                remixes_of.setdefault(k, []).append(name)
        gate_owners = {}
        for m in mods.values():
            for g in getattr(m, "gates", ()):
                gate_owners.setdefault(g.script, []).append(m.key)
        return cls(module_key, {k: sorted(v) for k, v in remixes_of.items()}, gate_owners,
                   registry.remix_names())


def classify(paths, ctx):
    """[(path, [(kind, command), ...], note)] for each changed path."""
    out = []
    for path in paths:
        parts = pathlib.PurePosixPath(path).parts
        gates, note = [], ""
        top = parts[0] if parts else ""
        if top == "modules" and len(parts) >= 2:
            d = parts[1]
            if d.startswith("_"):
                note = "template: skipped by the registry"
            elif d in ctx.module_key:
                key = ctx.module_key[d]
                remixes = ctx.remixes_of.get(key, [])
                if remixes:
                    gates = [cmd_check(r) for r in remixes] + [cmd_accept(r) for r in remixes]
                    note = f"{key} -> " + ", ".join(remixes)
                else:
                    note = f"{key}: no remix carries it (the selftest refuses this)"
                    gates = [CMD["selftest"]]
            elif not ctx.exists(f"modules/{d}"):
                # A removed (or renamed) module: the registry no longer knows
                # it, and the remixes that carried it changed their remix.py
                # in the same diff (the selftest refuses an unknown module),
                # which routes their checks. Nothing more to run for the
                # directory itself.
                note = "removed module directory: its remixes' selections are in the diff"
            else:
                note = "unknown module directory"
                gates = ctx.every()
        elif top == "remixes" and len(parts) >= 2:
            name = parts[1][:-3] if parts[1].endswith(".py") else parts[1]
            if parts[-1] == "README.md":
                gates = [CMD["verify_docs"]]
            else:
                gates = [cmd_check(name), cmd_accept(name)]
        elif path.endswith(".md"):
            # A README anywhere under tools/ or scripts/ is a doc, not the tool.
            gates = [CMD["verify_docs"]]
        elif path == "tools/verify/reach.py" or path.startswith("tools/verify/tests/"):
            # The classifier and its tests change what is PRINTED, not what
            # any gate runs; their own tests are the gate.
            gates = [CMD["test-acceptance"]]
        elif path in ("tools/verify/acceptance.py", "tools/verify/module_gates.py",
                      "tools/harness/stress_project.py", "tools/harness/pressure.py"):
            gates = [CMD["test-acceptance"]] + ctx.every() + [cmd_accept(r) for r in ctx.remixes]
            note = "the acceptance machinery: every remix"
        elif path.startswith("tools/verify/"):
            owners = ctx.gate_owners.get(path, [])
            remixes = sorted({r for k in owners for r in ctx.remixes_of.get(k, [])})
            if remixes:
                gates = [cmd_check(r) for r in remixes]
                note = "a gate of " + ", ".join(owners)
            else:
                gates = ctx.every()
                note = "a shared gate: every remix"
        elif path.startswith(("tools/remix/", "tools/build/", "dsp/")):
            gates = [CMD["refhash"], CMD["test-acceptance"]] + ctx.every()
            note = "the build: every remix; refhash proves the artifacts and reports identical"
        elif path.startswith(("tools/harness/dsp_host/", "tools/patches/")) or path in (
                "scripts/setup.sh", "scripts/vendor.sh"):
            gates = [CMD["ci-dsp"]] + ctx.every()
            note = "the DSP toolchain: rebuild it first (scripts/setup.sh; a dsp_host change in an isolated tree, AGENTS.md)"
        elif path.startswith("tools/emu/"):
            gates = [CMD["ci-emu"], CMD["emu-cf"]] + ctx.every()
            note = "the ColdFire port: the set gates need OT_PROJECT"
        elif path.startswith(("tools/harness/", "tools/hw/", "tools/panel/", "scripts/")):
            gates = ctx.every()
            if path == "scripts/refhash.sh":
                gates = [CMD["refhash"]]
        elif path == "Makefile":
            gates = ctx.every() + [CMD["ci"]]
        elif path.startswith(".github/"):
            gates = [CMD["ci"]]
        elif path.startswith("docs/"):
            gates = [CMD["verify_docs"]]
        elif path in ("pyproject.toml", "uv.lock", "LICENSE", ".gitignore", ".gitmodules"):
            gates = ctx.every()
        else:
            gates = ctx.every()
            note = "unclassified: every remix"
        out.append((path, gates, note))
    return out


def plan(rows):
    """The commands in run order, each once, with the paths that put it
    there. Two or more remixes to check become ONE `make check-shared`
    (the remix-independent gates, once) and a `make check-remix` each; a
    single remix stays `make check`."""
    by_cmd = {}
    for path, gates, _ in rows:
        for kind, command in gates:
            by_cmd.setdefault((kind, command), []).append(path)
    checks = {k: v for k, v in by_cmd.items() if k[0] == "check"}
    if len(checks) > 1:
        names = sorted(c.split("REMIX=")[1] for _, c in checks)
        paths = sorted({p for v in checks.values() for p in v})
        for k in checks:
            del by_cmd[k]
        by_cmd[("check-shared", f'make check-shared REMIXES="{" ".join(names)}"')] = paths
        for (_, c), v in checks.items():
            by_cmd[("check-remix", c.replace("make check ", "make check-remix "))] = v
    keyed = sorted(by_cmd.items(), key=lambda kv: (ORDER.index(kv[0][0]), kv[0][1]))
    return [(kind, command, paths) for (kind, command), paths in keyed]


def remixes_reached(rows):
    out = set()
    for _, gates, _ in rows:
        for kind, command in gates:
            if kind == "check":
                out.add(command.split("REMIX=")[1])
    return sorted(out)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def changed_paths(base):
    mb = git("merge-base", base, "HEAD")
    if mb.returncode:
        sys.exit(f"reach: no merge-base with {base}: {mb.stderr.strip()} (git fetch origin?)")
    merge_base = mb.stdout.strip()
    if git("merge-base", "--is-ancestor", base, "HEAD").returncode:
        sys.exit(f"reach: {base} is not an ancestor of HEAD -- rebase first; gates run "
                 f"before the rebase are not a result (CONTRIBUTING.md)")
    diff = git("diff", "--name-only", merge_base).stdout.split()
    untracked = git("ls-files", "--others", "--exclude-standard").stdout.split()
    return merge_base, sorted(set(diff) | set(untracked))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--paths", nargs="*", help="classify these paths instead of the diff")
    ap.add_argument("--run", action="store_true", help="run the commands, in order, stopping at the first failure")
    a = ap.parse_args(argv)
    if a.paths is not None:
        merge_base, paths = None, sorted(set(a.paths))
    else:
        merge_base, paths = changed_paths(a.base)
    ctx = Context.from_registry()
    rows = classify(paths, ctx)
    if merge_base:
        print(f"reach: {len(paths)} changed path{'s' if len(paths) != 1 else ''} against {a.base} ({merge_base[:10]})")
    for path, _, note in rows:
        print(f"  {path}" + (f"   [{note}]" if note else ""))
    if not rows:
        print("  (nothing changed)")
        return 0
    print("\nremixes reached: " + (", ".join(remixes_reached(rows)) or "none"))
    print("\ngates, in order:")
    items = plan(rows)
    for kind, command, from_paths in items:
        why = from_paths[0] + (f" +{len(from_paths) - 1}" if len(from_paths) > 1 else "")
        print(f"  {command:56}  # {why}")
    if any(k == "accept" for k, _, _ in items) and not os.environ.get("STRESS_SOURCE"):
        print("\nSTRESS_SOURCE is unset: point it at a local project (never committed) for the accept lines.")
    if not a.run:
        return 0
    print()
    for kind, command, _ in items:
        cmd = command.replace("${STRESS_SOURCE}", os.environ.get("STRESS_SOURCE", ""))
        if kind == "accept" and not os.environ.get("STRESS_SOURCE"):
            print(f"reach: BLOCKED {command}: STRESS_SOURCE is unset")
            return 2
        print(f"reach: running {cmd}", flush=True)
        r = subprocess.run(cmd, shell=True, cwd=ROOT)
        if r.returncode:
            print(f"reach: FAILED ({r.returncode}) {cmd}")
            return 1
    print("reach: every gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
