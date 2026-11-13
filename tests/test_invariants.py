import copy
import random
import unittest

from pvz_ize.catalog import PLANTS, ZOMBIES
from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


class InvariantTests(unittest.TestCase):
    def check_result(self, result):
        self.assertLessEqual(result["frames"], 2000)
        self.assertTrue(all(b["hp"] >= 0 for b in result["brains"]))
        self.assertTrue(all(z["hp"] >= 0 and z["helmet_hp"] >= 0 and z["shield_hp"] >= 0
                            for z in result["zombies"]))
        alive_brains = any(b["hp"] > 0 for b in result["brains"])
        active_zombies = any(z["status"] == "active" and not z["hypnotized"]
                             for z in result["zombies"])
        if result["winner"] == "plants":
            self.assertTrue(alive_brains)
            self.assertFalse(active_zombies)
        elif result["winner"] == "zombies":
            self.assertFalse(alive_brains)
        else:
            self.assertTrue(alive_brains and active_zombies)
            self.assertEqual(result["frames"], 2000)

    def test_all_supported_plant_zombie_pairs_finish_or_timeout_cleanly(self):
        for plant in PLANTS:
            for zombie in ZOMBIES:
                with self.subTest(plant=plant, zombie=zombie):
                    scenario = parse_scenario({"max_frames": 2000,
                        "plants": [{"type": plant, "row": 3, "col": 2}],
                        "zombies": [{"type": zombie, "row": 3, "col": 4}]})
                    self.check_result(Simulator(scenario).run())

    def test_seeded_random_scenarios_replay_from_normalized_initial_state(self):
        rng = random.Random(2026)
        for seed in range(15):
            cells = rng.sample([(r, c) for r in range(1, 6) for c in range(1, 6)], 6)
            data = {"seed": seed, "max_frames": 2000,
                "brains": rng.sample(range(1, 6), rng.randint(1, 5)),
                "plants": [{"type": rng.choice(list(PLANTS)), "row": r, "col": c}
                           for r, c in cells],
                "zombies": [{"type": rng.choice(list(ZOMBIES)),
                             "row": rng.randint(1, 5), "col": rng.randint(3, 9)}
                            for _ in range(4)]}
            with self.subTest(seed=seed):
                scenario = parse_scenario(data)
                expected = Simulator(scenario).run()
                self.check_result(expected)
                replay = Simulator(parse_scenario(scenario.to_dict())).run()
                self.assertEqual(expected, replay)

    def test_single_lane_row_translation_preserves_outcome_and_timing(self):
        for plant in ("peashooter", "snow_pea", "repeater", "potato_mine", "chomper", "squash"):
            base = {"seed": 9, "max_frames": 2000,
                    "plants": [{"type": plant, "row": 1, "col": 2}],
                    "zombies": [{"type": "conehead", "row": 1, "col": 4}],
                    "brains": [1]}
            first = Simulator(parse_scenario(base)).run()
            for row in range(2, 6):
                data = copy.deepcopy(base)
                data["brains"] = [row]
                data["plants"][0]["row"] = row
                data["zombies"][0]["row"] = row
                shifted = Simulator(parse_scenario(data)).run()
                self.assertEqual((first["winner"], first["frames"], first["events"]),
                                 (shifted["winner"], shifted["frames"], shifted["events"]))
