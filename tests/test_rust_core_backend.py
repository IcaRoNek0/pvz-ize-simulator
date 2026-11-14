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
        self.assertTrue(supports_scenario({
            "plants": [{"type": "wallnut", "row": 3, "col": 1}],
            "zombies": [{"type": "ladder", "row": 3, "x": 90}],
            "rakes": [{"row": 3, "col": 8}],
        }))
        self.assertTrue(supports_scenario({
            "plants": [{"type": "potato_mine", "row": 3, "col": 2}],
            "zombies": [{"type": "normal", "row": 3, "x": 170}],
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

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_who_will_win_row_scope_uses_rust_slice(self):
        result = run_rust_core({
            "version": 2,
            "mode": "who_will_win",
            "max_frames": 120,
            "plants": [],
            "zombies": [{"type": "normal", "row": 2, "x": 500}],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["winner"], "plants")
        self.assertEqual(result["reason"], "no_row_3_threats")

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_cherry_bomb_delayed_blast_runs_through_rust(self):
        result = run_rust_core({
            "version": 2,
            "max_frames": 100,
            "plants": [{"type": "cherry_bomb", "row": 3, "col": 3}],
            "zombies": [{"type": "normal", "row": 3, "col": 4}],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["events"]["explosion"], 1)
        self.assertEqual(result["zombies"][0]["status"], "dead")

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_jalapeno_row_blast_runs_through_rust(self):
        result = run_rust_core({
            "version": 2,
            "max_frames": 100,
            "plants": [{"type": "jalapeno", "row": 3, "col": 2}],
            "zombies": [
                {"type": "normal", "row": 3, "x": 300},
                {"type": "normal", "row": 2, "x": 300},
            ],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["events"]["explosion"], 1)
        self.assertEqual(result["zombies"][0]["status"], "dead")
        self.assertEqual(result["zombies"][1]["status"], "active")

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_spikeweed_hazard_runs_through_rust(self):
        result = run_rust_core({
            "version": 2,
            "max_frames": 150,
            "plants": [{"type": "spikerock", "row": 3, "col": 2}],
            "zombies": [{"type": "normal", "row": 3, "x": 100, "speed": 0.001}],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["events"]["spikerock_pulse"], 3)

