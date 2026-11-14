import json
import unittest

from pvz_ize.rust_core import run_rust_core, rust_core_available, supports_scenario


class RustCoreBridgeTests(unittest.TestCase):
    def test_support_gate_rejects_unmigrated_units(self):
        self.assertTrue(supports_scenario({
            "plants": [{"type": "repeater", "row": 3, "col": 1, "cooldown": 0}],
            "zombies": [{"type": "normal", "row": 3, "col": 2}],
            "brains": [3],
        }))
        self.assertFalse(supports_scenario({
            "plants": [{"type": "cob_cannon", "row": 3, "col": 1}],
            "zombies": [{"type": "normal", "row": 3, "col": 2}],
        }))
        self.assertFalse(supports_scenario({
            "plants": [], "zombies": [{"type": "buckethead", "row": 3, "col": 2}],
        }))

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_supported_fixture_runs_through_rust(self):
        result = run_rust_core({
            "version": 2,
            "max_frames": 1,
            "plants": [{"type": "repeater", "row": 3, "col": 1, "cooldown": 0}],
            "zombies": [{"type": "normal", "row": 3, "x": 90}],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["events"]["projectile_hit"], 2)
        self.assertEqual(result["zombies"][0]["hp"], 230)

