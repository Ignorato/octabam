"""check_shards --by-gate: the job list mirrors `make verify-remix`."""
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[2]))
import check_shards  # noqa: E402
from reach import recipe_scripts  # noqa: E402

ROOT = HERE.parents[3]


class ByGate(unittest.TestCase):
    def jobs(self, remix="bottleservice"):
        return check_shards.remix_jobs(remix, ROOT / "out/shards/0")

    def test_every_recipe_script_has_a_job(self):
        jobs = self.jobs()
        check_shards.check_recipe(jobs)          # raises SystemExit on drift
        recipe = recipe_scripts((ROOT / "Makefile").read_text(), "verify-remix")
        named = {c[1] for _n, cmds, _e in jobs for c in cmds if len(c) > 1}
        self.assertTrue(recipe - {"tools/verify/module_gates.py"} <= named, recipe - named)

    def test_drift_is_refused(self):
        jobs = [j for j in self.jobs() if j[0] != "usb"]
        with self.assertRaises(SystemExit) as cm:
            check_shards.check_recipe(jobs)
        self.assertIn("verify_usb.py", str(cm.exception))

    def test_image_stage_follows_the_set_gate(self):
        """TEMPO BUS boots the card verify_set stages: same job, after it,
        with the image restored between."""
        (_n, cmds, _e), = [j for j in self.jobs() if j[0] == "set"]
        scripts = [c[1] if c[0] != "make" else "make " + c[1] for c in cmds]
        self.assertEqual(scripts, ["tools/verify/verify_set.py", "make bus",
                                   "tools/verify/module_gates.py"])
        self.assertIn("--stage", cmds[2])
        self.assertEqual(cmds[2][cmds[2].index("--stage") + 1], "image")

    def test_module_gates_are_one_job_each(self):
        names = [n for n, _c, _e in self.jobs()]
        self.assertIn("gate:verify_scenesp2", names)
        self.assertIn("gate:verify_burn", names)
        self.assertEqual(len(names), len(set(names)))

    def test_every_job_carries_the_remix(self):
        for _n, _c, env in self.jobs():
            self.assertEqual(env["REMIX"], "bottleservice")


if __name__ == "__main__":
    unittest.main()
