import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, "-m", "pvz_ize", *args],
                              cwd=ROOT, input=stdin, text=True,
                              capture_output=True, timeout=20)

    def scenario_file(self, data, callback):
        with tempfile.TemporaryDirectory(prefix="pvz-ize-test-") as folder:
            path = Path(folder) / "scenario.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return callback(str(path))

    def test_help(self):
        result = self.cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run", result.stdout)
        self.assertIn("catalog", result.stdout)

    def test_catalog_json(self):
        result = self.cli("catalog", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("peashooter", json.dumps(data))
        self.assertIn("buckethead", json.dumps(data))

    def test_empty_scenario_file(self):
        result = self.scenario_file({}, lambda path: self.cli("run", path, "--json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["winner"], "plants")

    def test_stdin(self):
        result = self.cli("run", "-", "--json", stdin=json.dumps({"brains": [2]}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["brains"][0]["row"], 2)

    def test_direct_layout(self):
        result = self.cli("run", "--json", "--brain-row", "2",
                          "--plant", "wallnut,2,2", "--zombie", "normal,2,8",
                          "--max-frames", "1", "--seed", "17")
        self.assertEqual(result.returncode, 2, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["winner"], "undecided")
        self.assertEqual(data["frames"], 1)
        self.assertEqual(data["brains"][0]["row"], 2)

    def test_multiple_brain_rows(self):
        result = self.cli("run", "--json", "--brain-row", "1", "--brain-row", "5")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([b["row"] for b in json.loads(result.stdout)["brains"]], [1, 5])

    def test_seeded_runs_are_reproducible(self):
        args = ("run", "--json", "--plant", "peashooter,3,2",
                "--zombie", "normal,3,8", "--seed", "7", "--max-frames", "100")
        first, second = self.cli(*args), self.cli(*args)
        self.assertEqual(first.returncode, 2, first.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))

    def test_max_frames_override_file(self):
        data = {"max_frames": 5000,
                "zombies": [{"type": "normal", "row": 3, "col": 8}]}
        result = self.scenario_file(data, lambda path: self.cli(
            "run", path, "--json", "--max-frames", "1"))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["frames"], 1)

    def test_validate_accepts_valid_file(self):
        result = self.scenario_file({}, lambda path: self.cli("validate", path))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_rejects_invalid_file(self):
        result = self.scenario_file({"brains": []},
                                    lambda path: self.cli("validate", path))
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.strip())
        self.assertNotIn("Traceback", result.stderr)

    def test_input_errors_are_clean(self):
        cases = [(("run", "-", "--json"), "not json"),
                 (("run", "-", "--json"), "[]"),
                 (("run", "-", "--json"), '{"plants":null}'),
                 (("run", "-", "--json"), json.dumps({"seed": 10**1000})),
                 (("run", "--json", "--plant", "unknown,3,2"), None),
                 (("run", "--json", "--plant", "peashooter,3"), None),
                 (("run", "--json", "--zombie", "normal,6,8"), None),
                 (("run", "--json", "--brain-row", "0"), None),
                 (("run", "--json", "--max-frames", "0"), None)]
        for args, stdin in cases:
            with self.subTest(args=args, stdin=stdin):
                result = self.cli(*args, stdin=stdin)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stderr.strip())
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_file_is_clean_error(self):
        with tempfile.TemporaryDirectory(prefix="pvz-ize-test-") as folder:
            result = self.cli("run", str(Path(folder) / "missing.json"), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)

    def test_artifacts_and_dumped_initial_replay(self):
        with tempfile.TemporaryDirectory(prefix="pvz-ize-test-") as folder:
            paths = {name: Path(folder) / "artifacts" / filename for name, filename in
                     (("output", "result.json"), ("trace", "events.ndjson"),
                      ("initial", "initial.json"))}
            result = self.cli("run", "--json", "--plant", "peashooter,3,2",
                              "--zombie", "normal,3,8", "--seed", "7",
                              "--max-frames", "400", "--output", str(paths["output"]),
                              "--trace", str(paths["trace"]),
                              "--dump-initial", str(paths["initial"]))
            self.assertEqual(result.returncode, 2, result.stderr)
            expected = json.loads(result.stdout)
            self.assertEqual(json.loads(paths["output"].read_text(encoding="utf-8")), expected)
            initial = json.loads(paths["initial"].read_text(encoding="utf-8"))
            self.assertEqual(initial["seed"], 7)
            self.assertEqual(initial["max_frames"], 400)
            self.assertEqual(initial["plants"][0]["type"], "peashooter")
            self.assertEqual(initial["zombies"][0]["x"], 570)
            self.assertIn("cooldown", initial["plants"][0])
            events = [json.loads(line) for line in
                      paths["trace"].read_text(encoding="utf-8").splitlines()]
            self.assertGreater(len(events), 1)
            self.assertEqual(events[-1]["event"], "finished")
            self.assertEqual(events[-1]["winner"], expected["winner"])
            self.assertEqual(events[-1]["frame"], expected["frames"])
            self.assertEqual([event["frame"] for event in events],
                             sorted(event["frame"] for event in events))
            replay_trace = Path(folder) / "replay.ndjson"
            replay = self.cli("run", str(paths["initial"]), "--json",
                              "--trace", str(replay_trace))
            self.assertEqual(replay.returncode, result.returncode, replay.stderr)
            self.assertEqual(json.loads(replay.stdout), expected)
            self.assertEqual(replay_trace.read_text(encoding="utf-8"),
                             paths["trace"].read_text(encoding="utf-8"))

    def test_output_destinations_cannot_collide(self):
        flags = ("--output", "--trace", "--dump-initial")
        for index, first in enumerate(flags):
            for second in flags[index + 1:]:
                with self.subTest(first=first, second=second):
                    with tempfile.TemporaryDirectory(prefix="pvz-ize-test-") as folder:
                        path = Path(folder) / "keep.txt"
                        path.write_text("keep existing content", encoding="utf-8")
                        alias = str(Path(folder) / "unused" / ".." / "keep.txt")
                        result = self.cli("run", "--json", first, str(path), second, alias)
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertTrue(result.stderr.strip())
                        self.assertNotIn("Traceback", result.stderr)
                        self.assertEqual(path.read_text(encoding="utf-8"), "keep existing content")

    def test_artifacts_cannot_overwrite_input(self):
        for flag in ("--output", "--trace", "--dump-initial"):
            with self.subTest(flag=flag):
                with tempfile.TemporaryDirectory(prefix="pvz-ize-test-") as folder:
                    path = Path(folder) / "scenario.json"
                    content = '{"brains": [2]}\n'
                    path.write_text(content, encoding="utf-8")
                    result = self.cli("run", str(path), "--json", flag, str(path))
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertTrue(result.stderr.strip())
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_artifact_symlink_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory(prefix="pvz-ize-test-") as folder:
            source, alias = Path(folder) / "scenario.json", Path(folder) / "alias.json"
            source.write_text("{}", encoding="utf-8")
            alias.symlink_to(source)
            result = self.cli("run", str(source), "--output", str(alias))
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), "{}")
            self.assertTrue(alias.is_symlink())

    def test_artifact_hardlink_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory(prefix="pvz-ize-test-") as folder:
            source, alias = Path(folder) / "scenario.json", Path(folder) / "alias.json"
            source.write_text("{}", encoding="utf-8")
            alias.hardlink_to(source)
            result = self.cli("run", str(source), "--trace", str(alias))
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), "{}")
            self.assertEqual(alias.read_text(encoding="utf-8"), "{}")

    def test_unknown_arguments_are_clean_errors(self):
        for args in (("run", "--unknown"), ("catalog", "--unknown"), ("unknown",)):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stderr.strip())
                self.assertNotIn("Traceback", result.stderr)

    def test_duplicate_json_keys_and_nonfinite_numbers_are_rejected(self):
        invalid = ['{"seed": 1, "seed": 2}',
                   '{"plants": [{"type": "wallnut", "row": 2, "row": 3, "col": 2}]}',
                   '{"seed": NaN}', '{"seed": Infinity}', '{"seed": -Infinity}']
        for content in invalid:
            with self.subTest(content=content):
                result = self.cli("run", "-", "--json", stdin=content)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stderr.strip())
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(result.stdout.strip())

    def test_file_and_direct_layout_cannot_be_mixed(self):
        placements = (("--plant", "wallnut,3,2"), ("--zombie", "normal,3,8"),
                      ("--zombie-x", "normal,3,650"), ("--brain-row", "2"))
        for placement in placements:
            with self.subTest(placement=placement):
                result = self.scenario_file({}, lambda path: self.cli(
                    "run", path, "--json", *placement))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertTrue(result.stderr.strip())
                self.assertNotIn("Traceback", result.stderr)
        result = self.cli("run", "-", "--plant", "wallnut,3,2", stdin="{}")
        self.assertEqual(result.returncode, 1, result.stderr)


if __name__ == "__main__":
    unittest.main()
