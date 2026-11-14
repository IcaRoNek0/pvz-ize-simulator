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
        self.assertTrue(supports_scenario({
            "plants": [], "zombies": [{"type": "buckethead", "row": 3, "col": 2}],
        }))
        self.assertTrue(supports_scenario({
            "plants": [], "zombies": [{"type": "football", "row": 3, "x": 90}],
        }))
        self.assertTrue(supports_scenario({
            "plants": [], "zombies": [{"type": "newspaper", "row": 3, "x": 90}],
        }))
        self.assertTrue(supports_scenario({
            "plants": [], "zombies": [{"type": "imp", "row": 3, "x": 90}],
        }))
        self.assertTrue(supports_scenario({
            "plants": [], "zombies": [{"type": "pole_vaulting", "row": 3, "x": 500}],
        }))
        self.assertFalse(supports_scenario({
            "plants": [{"type": "wallnut", "row": 3, "col": 6}],
            "zombies": [{"type": "pole_vaulting", "row": 3, "x": 500}],
        }))
        self.assertTrue(supports_scenario({
            "plants": [], "zombies": [{"type": "zamboni", "row": 3, "x": 800}],
        }))
        self.assertFalse(supports_scenario({
            "plants": [{"type": "wallnut", "row": 3, "col": 6}],
            "zombies": [{"type": "zamboni", "row": 3, "x": 800}],
        }))
        # Giant-triggered imp throw/landing has no Rust phase/altitude fields;
        # keeping the giant outside the gate forces the complete Python path.
        self.assertFalse(supports_scenario({
            "plants": [],
            "zombies": [
                {"type": "gargantuar", "row": 3, "x": 300},
                {"type": "imp", "row": 3, "x": 200},
            ],
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

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_imp_projectile_runs_through_rust(self):
        result = run_rust_core({
            "version": 2,
            "max_frames": 1,
            "plants": [{"type": "peashooter", "row": 3, "col": 1, "cooldown": 0}],
            "zombies": [{"type": "imp", "row": 3, "x": 90}],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["events"]["projectile_fired"], 1)
        self.assertEqual(result["events"]["projectile_hit"], 1)
        self.assertEqual(result["zombies"][0]["hp"], 50)

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_spent_pole_projectile_runs_through_rust(self):
        result = run_rust_core({
            "version": 2,
            "max_frames": 1,
            "plants": [{"type": "peashooter", "row": 3, "col": 1, "cooldown": 0}],
            "zombies": [{"type": "pole_vaulting", "row": 3, "x": 90, "tool": False}],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["events"]["projectile_hit"], 1)
        self.assertEqual(result["zombies"][0]["hp"], 480)

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_zamboni_catalog_defaults_run_without_board_targets(self):
        result = run_rust_core({
            "version": 2,
            "max_frames": 1,
            "plants": [],
            "zombies": [{"type": "zamboni", "row": 3, "x": 800}],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["zombies"][0]["hp"], 1350)
        self.assertEqual(result["zombies"][0]["x"], 799.75)

    def test_cob_arming_support_gate_keeps_ballistic_path_on_python(self):
        self.assertTrue(supports_scenario({
            "max_frames": 1,
            "plants": [{"type": "cob_cannon", "row": 3, "col": 2, "cooldown": 500}],
            "zombies": [{"type": "normal", "row": 3, "x": 600}],
        }))
        self.assertFalse(supports_scenario({
            "max_frames": 1,
            "plants": [{"type": "cob_cannon", "row": 3, "col": 2, "cooldown": 0}],
            "zombies": [{"type": "normal", "row": 3, "x": 600}],
        }))

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_cob_arming_counter_runs_through_rust(self):
        result = run_rust_core({
            "version": 2,
            "max_frames": 1,
            "plants": [{"type": "cob_cannon", "row": 3, "col": 2, "cooldown": 500}],
            "zombies": [{"type": "normal", "row": 3, "x": 600}],
            "brains": [3],
        })
        self.assertEqual(result["backend"], "rust-core-slice")
        self.assertEqual(result["plants"][0]["cooldown"], 499)
        self.assertEqual(result["projectiles"], [])

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_batch_bridge_uses_stable_native_rows(self):
        from pvz_ize.rust_core import run_batch_rust_core

        result = run_batch_rust_core({
            "version": 2,
            "seed": 9001,
            "runs": 3,
            "max_frames": 2,
            "plants": [{"type": "peashooter", "row": 3, "col": 1, "cooldown": 0}],
            "zombies": [{"type": "normal", "row": 3, "x": 90}],
            "brains": [3],
        }, workers=2)
        self.assertEqual(result["backend"], "rust-core-slice-rayon")
        self.assertEqual([row["run_index"] for row in result["results"]], [0, 1, 2])
        self.assertEqual([row["seed"] for row in result["results"]], [9001, 9002, 9003])
        self.assertEqual(sum(item["count"] for item in result["outcomes"].values()), 3)

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_batch_bridge_clamps_workers_and_wraps_seed(self):
        from pvz_ize.rust_core import run_batch_rust_core

        result = run_batch_rust_core({
            "version": 2,
            "seed": 2**63 - 1,
            "runs": 2,
            "max_frames": 1,
            "plants": [],
            "zombies": [{"type": "normal", "row": 3, "x": 500}],
            "brains": [3],
        }, workers=99)
        self.assertEqual(result["backend"], "rust-core-slice-rayon")
        self.assertEqual(result["parallel_workers"], 2)
        self.assertEqual([row["run_index"] for row in result["results"]], [0, 1])
        self.assertEqual([row["seed"] for row in result["results"]], [2**63 - 1, -(2**63)])

    @unittest.skipUnless(rust_core_available(), "native Rust slice is not built")
    def test_batch_bridge_single_run_keeps_batch_schema(self):
        from pvz_ize.rust_core import run_batch_rust_core

        result = run_batch_rust_core({
            "version": 2,
            "seed": 17,
            "runs": 1,
            "max_frames": 1,
            "plants": [],
            "zombies": [{"type": "normal", "row": 3, "x": 500}],
            "brains": [3],
        }, workers=8)
        self.assertTrue(result["batch"])
        self.assertEqual(result["runs"], 1)
        self.assertEqual(result["parallel_workers"], 1)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["seed"], 17)

    def test_batch_bridge_rejects_nonpositive_or_boolean_runs(self):
        from pvz_ize.rust_core import run_batch_rust_core

        for runs in (0, -1, True, 1.5):
            with self.subTest(runs=runs), self.assertRaises(ValueError):
                run_batch_rust_core({"runs": runs, "plants": [], "zombies": []})

