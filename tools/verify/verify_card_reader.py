#!/usr/bin/env python3
"""The card reader returns what the builder wrote, byte for byte.

    python3 tools/verify/verify_card_reader.py

`emu_card.extract_image` is how every STEM REC port run gets its WAV back,
so it is held to the builder that made the image: files of awkward sizes (0,
1, one cluster, one cluster + 1, many clusters), a long name and nested
folders, built, read back and compared. It also pins what the reader cannot
show: a folder with no file in it does not appear (it lists files), so a
take that made its folder and wrote nothing reads as no take at all. And it
pins the FAT16 image itself, by hash, so a change to the builder that moves
one byte of it is seen.
"""
import hashlib
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import emu_card as ec  # noqa: E402


def _bytes(n):
    """n bytes of a fixed pattern, so the image, and its hash, repeat."""
    return bytes(range(256)) * (n // 256) + bytes(range(n % 256))


FILES = {
    "PRESETS/PROJ/project.work": b"",
    "PRESETS/AUDIO/a.wav": b"\x01",
    "PRESETS/AUDIO/Long Name Recording.wav": _bytes(4096),
    "PRESETS/AUDIO/250910-1432/T1.wav": _bytes(4097),
    "big.bin": _bytes(300_000),
}
EMPTY = "PRESETS/AUDIO/250910-1433"
# The 16 MB image of build_tree(), from upstream's builder (27 Sep 2026, 68af650).
FAT16_SHA = "5c36bdd8bebdeaa519f2358f9e359f9144ced5d8ce161a1783d68da88919a853"


def build_tree(root):
    for rel, data in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (root / EMPTY).mkdir(parents=True)


def main():
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    with tempfile.TemporaryDirectory() as t:
        tree = pathlib.Path(t) / "tree"
        build_tree(tree)
        img16 = ec.build_image(str(tree), 16)
        got = ec.extract_image(img16)
        for rel, data in FILES.items():
            check(f"/{rel} ({len(data):,} B)", got.get(rel) == data,
                  "" if rel in got else "missing")
        check("nothing read back that was not written", set(got) == set(FILES),
              f"{sorted(set(got) - set(FILES))}")
        check(f"an empty folder ({EMPTY}) does not appear",
              not any(p.startswith(EMPTY) for p in got))
        sha = hashlib.sha256(img16).hexdigest()
        check("FAT16: the image is what upstream's builder made", sha == FAT16_SHA, sha)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
