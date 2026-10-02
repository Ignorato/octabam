"""The build's Keep assert, on a bytearray standing in for the image."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from remix import keep  # noqa: E402
from remix.schema import Keep, Kind, Module  # noqa: E402

BASE = 0x40000000


def _mod(*keeps):
    return Module(name="k", key="K", kind=Kind.CF_PATCH, doc="fixture", keeps=keeps)


class KeepTests(unittest.TestCase):
    def setUp(self):
        self.img = bytearray(64)
        self.img[0x10:0x14] = bytes.fromhex("48780064")

    def test_stock_passes(self):
        self.assertEqual(keep.violations(self.img, BASE, [_mod(Keep(BASE + 0x10, bytes.fromhex("48780064")))]), [])

    def test_rewritten_bytes_are_named(self):
        self.img[0x13] = 0x70
        got = keep.violations(self.img, BASE, [_mod(Keep(BASE + 0x10, bytes.fromhex("48780064"), "pea"))])
        self.assertEqual(len(got), 1)
        self.assertIn("K keeps 0x40000010 (pea): finds 48780070", got[0])

    def test_module_without_keeps(self):
        self.assertEqual(keep.violations(self.img, BASE, [_mod()]), [])


if __name__ == "__main__":
    unittest.main()
