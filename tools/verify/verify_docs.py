#!/usr/bin/env python3
"""Every module has a row in README.md's module table and every remix a page
under docs/remixes/ listed in docs/remixes/README.md.

    python3 tools/verify/verify_docs.py

Eight merged modules and four remixes had neither on 27 Sep 2026; the
index (`make modules`) is generated from the manifests, the README is a
copy, and nothing compared them.
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    readme = ROOT.joinpath("README.md").read_text()
    table = readme[readme.index("## What it carries"):readme.index("## Quick start")]
    bold = " ".join(re.findall(r"\*\*(.+?)\*\*", table)).upper()
    fails = []
    for m in registry.modules().values():
        if m.is_stock:
            continue
        if m.key.upper() not in bold and m.name.upper() not in bold \
                and m.name.replace("-", " ").upper() not in bold:
            fails.append(f"README.md: no module-table row names {m.key!r} ({m.name})")
    index = ROOT.joinpath("docs/remixes/README.md").read_text()
    for path in sorted(ROOT.glob("remixes/*.py")):
        name = path.stem
        # A remix may share a page with a sibling (octatrick-usb -> octatrick.md).
        link = re.search(r"\[`%s`\]\(([^)]+)\)" % re.escape(name), index)
        if link is None:
            fails.append(f"docs/remixes/README.md: does not link `{name}` to a page")
        elif not (ROOT / "docs/remixes" / link.group(1)).exists():
            fails.append(f"docs/remixes/{link.group(1)}: linked for `{name}`, missing")
    for f in fails:
        print("  [FAIL]", f)
    n = len([m for m in registry.modules().values() if not m.is_stock])
    print(f"verify_docs: {n} modules, {len(list(ROOT.glob('remixes/*.py')))} remixes, {len(fails)} missing")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
