import json
import unittest
from pathlib import Path

from pvz_ize.batch import run_batch_parallel
from pvz_ize.native_batch import native_available, run_batch_rust


class NativeBatchTests(unittest.TestCase):
    def scenario(self):
        data = json.loads((Path(__file__).parents[1] / "examples" / "v2_random.json").read_text())
        data["runs"] = 4
        return data

    def test_python_fallback_preserves_results(self):
        data = self.scenario()
        expected = run_batch_parallel(data, workers=2)
        actual = run_batch_rust(data, workers=2)
        self.assertEqual(expected["outcomes"], actual["outcomes"])
        self.assertEqual([r["winner"] for r in expected["results"]],
                         [r["winner"] for r in actual["results"]])

    @unittest.skipUnless(native_available(), "native Rust coordinator is not built")
    def test_native_backend_has_same_outcomes(self):
        data = self.scenario()
        expected = run_batch_parallel(data, workers=2)
        actual = run_batch_rust(data, workers=2)
        self.assertEqual(expected["outcomes"], actual["outcomes"])
        self.assertEqual([r["winner"] for r in expected["results"]],
                         [r["winner"] for r in actual["results"]])
        self.assertEqual(actual["backend"], "rust-coordinator-python-workers")


if __name__ == "__main__":
    unittest.main()
