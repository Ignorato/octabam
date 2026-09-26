"""The path classifier, against a fake registry: no manifests, no firmware."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import reach


def ctx():
    return reach.Context(
        module_key={"character": "CHARACTER", "miniverb": "MINIVERB", "orphan": "ORPHAN"},
        remixes_of={"CHARACTER": ["bamsep26", "usb"], "MINIVERB": ["miniverb"], "ORPHAN": []},
        gate_owners={"tools/verify/verify_character.py": ["CHARACTER"]},
        default="bamsep26")


def commands(paths):
    return [c for _, c, _ in reach.plan(reach.classify(paths, ctx()))]


class ClassifyTests(unittest.TestCase):
    def test_module_reaches_every_remix_that_carries_it(self):
        cmds = commands(["modules/character/engine.asm"])
        self.assertEqual(cmds, ["make check REMIX=bamsep26", "make check REMIX=usb",
                                "make accept REMIX=bamsep26 STRESS_SOURCE=${STRESS_SOURCE}",
                                "make accept REMIX=usb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_submodule_pin_is_the_module(self):
        self.assertEqual(commands(["modules/miniverb/upstream"]),
                         ["make check REMIX=miniverb", "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_module_no_remix_carries_gets_the_floor_and_a_note(self):
        rows = reach.classify(["modules/orphan/manifest.py"], ctx())
        self.assertIn("no remix carries", rows[0][2])
        self.assertEqual(commands(["modules/orphan/manifest.py"]), ["make check REMIX=bamsep26"])

    def test_template_runs_nothing(self):
        self.assertEqual(commands(["modules/_template/manifest.py"]), [])

    def test_remix_selection_and_readme(self):
        self.assertEqual(commands(["remixes/miniverb/remix.py"]),
                         ["make check REMIX=miniverb", "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])
        self.assertEqual(commands(["remixes/miniverb/README.md"]), ["python3 tools/verify/verify_docs.py"])

    def test_verifier_reaches_its_owners_remixes(self):
        self.assertEqual(commands(["tools/verify/verify_character.py"]),
                         ["make check REMIX=bamsep26", "make check REMIX=usb"])
        self.assertEqual(commands(["tools/verify/verify_menu.py"]), ["make check REMIX=bamsep26"])

    def test_build_change_needs_refhash(self):
        cmds = commands(["tools/build/build_bus.py"])
        self.assertEqual(cmds[:1], ["make test-acceptance"])
        self.assertIn("scripts/refhash.sh check", cmds)
        self.assertIn("make check REMIX=bus", cmds)

    def test_runner_changes_need_the_runner_tests(self):
        for p in ("tools/verify/acceptance.py", "tools/verify/tests/test_x.py", "tools/harness/pressure.py"):
            self.assertIn("make test-acceptance", commands([p]), p)

    def test_toolchain_port_docs_ci(self):
        self.assertEqual(commands(["tools/patches/dsp56300.patch"])[0], "make ci-dsp")
        self.assertIn("make ci-emu", commands(["tools/emu/ot_emu/machine.h"]))
        self.assertEqual(commands(["docs/remixer/MODULES.md", "README.md"]), ["python3 tools/verify/verify_docs.py"])
        self.assertEqual(commands([".github/workflows/ci.yml"]), ["make ci"])

    def test_unclassified_gets_the_floor_and_says_so(self):
        rows = reach.classify(["mystery.bin"], ctx())
        self.assertIn("unclassified", rows[0][2])
        self.assertEqual(commands(["mystery.bin"]), ["make check REMIX=bamsep26"])

    def test_order_is_fixed_and_each_command_once(self):
        cmds = commands(["docs/x.md", "modules/character/a.asm", "tools/build/b.py", "modules/character/b.asm"])
        self.assertEqual(cmds[0], "python3 tools/verify/verify_docs.py")
        self.assertEqual(len(cmds), len(set(cmds)))
        self.assertLess(cmds.index("scripts/refhash.sh check"), cmds.index("make check REMIX=bamsep26"))

    def test_remixes_reached(self):
        rows = reach.classify(["modules/character/a.asm", "remixes/miniverb/remix.py"], ctx())
        self.assertEqual(reach.remixes_reached(rows), ["bamsep26", "miniverb", "usb"])


if __name__ == "__main__":
    unittest.main()
