import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "diff_rust_python.py"
SPEC = importlib.util.spec_from_file_location("diff_rust_python", MODULE_PATH)
diff = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(diff)


class RustDiffHarnessTests(unittest.TestCase):
    def test_projection_keeps_terminal_state_and_drops_metadata(self):
        result = {
            "model": "python", "warnings": ["approx"], "seconds": 1.2,
            "winner": "plants", "reason": "no_on_board_zombies", "status": "finished",
            "frames": 12, "brains": [], "plants": [], "zombies": [],
            "projectiles": [], "pending_effects": {}, "zombie_special_state": {},
            "plant_head_state": {}, "active_hostile_zombies": 0,
            "active_friendly_zombies": 0, "ladders": [], "events": {"finished": 1},
        }
        projection = diff.projection(result)
        self.assertEqual(projection["winner"], "plants")
        self.assertEqual(projection["frames"], 12)
        self.assertNotIn("model", projection)
        self.assertNotIn("seconds", projection)

    def test_missing_rust_binary_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            scenario = Path(directory) / "scenario.json"
            scenario.write_text(json.dumps({"plants": [], "zombies": []}))
            output = io.StringIO()
            with redirect_stdout(output):
                code = diff.main([str(scenario), "--rust-binary", str(Path(directory) / "missing")])
            self.assertEqual(code, 3)
            self.assertEqual(json.loads(output.getvalue())["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
