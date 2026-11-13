import copy
import math
import unittest

from pvz_ize.catalog import PLANTS, ZOMBIES
from pvz_ize.model import ScenarioError, parse_scenario


def plant(**overrides):
    return {"type": "peashooter", "row": 3, "col": 2, **overrides}


def zombie(**overrides):
    return {"type": "normal", "row": 3, "col": 8, **overrides}


class ScenarioTests(unittest.TestCase):
    def test_defaults_have_one_brain_in_third_row(self):
        scenario = parse_scenario({})
        self.assertEqual([(b.row, b.hp) for b in scenario.brains], [(3, 70)])
        self.assertEqual(scenario.plants, [])
        self.assertEqual(scenario.zombies, [])
        self.assertEqual(scenario.seed, 0)
        self.assertGreater(scenario.max_frames, 0)

    def test_coordinate_conversion_and_defaults(self):
        scenario = parse_scenario({"plants": [plant()], "zombies": [zombie()]})
        self.assertEqual(scenario.plants[0].x, 120)
        self.assertEqual(scenario.zombies[0].x, 570)
        self.assertEqual(scenario.plants[0].hp, PLANTS["peashooter"].hp)
        self.assertEqual(scenario.zombies[0].hp, ZOMBIES["normal"].hp)

    def test_aliases_are_canonicalized(self):
        scenario = parse_scenario({
            "plants": [plant(type="1")], "zombies": [zombie(type="tt")]
        })
        self.assertEqual(scenario.plants[0].type, "peashooter")
        self.assertEqual(scenario.zombies[0].type, "buckethead")
        self.assertEqual(scenario.zombies[0].helmet_hp, 1100)

    def test_arbitrary_and_multiple_brain_rows(self):
        scenario = parse_scenario({"brains": [1, {"row": 5, "hp": 20}]})
        self.assertEqual([(b.row, b.hp) for b in scenario.brains], [(1, 70), (5, 20)])

    def test_seed_is_reproducible_without_mutating_input(self):
        data = {"seed": 42, "plants": [plant(), plant(row=2)]}
        original = copy.deepcopy(data)
        self.assertEqual(parse_scenario(data).to_dict(), parse_scenario(data).to_dict())
        self.assertEqual(data, original)

    def test_explicit_initial_state(self):
        data = {"plants": [plant(id="p", hp=123, cooldown=7, state_timer=9)],
                "zombies": [{"type": "buckethead", "row": 1, "x": 123.5,
                             "id": "z", "hp": 50, "helmet_hp": 20,
                             "speed": 0.5, "age": 12, "chilled": 4,
                             "headless": True}]}
        scenario = parse_scenario(data)
        self.assertEqual(scenario.plants[0].cooldown, 7)
        self.assertEqual(scenario.plants[0].state_timer, 9)
        unit = scenario.zombies[0]
        self.assertEqual((unit.x, unit.hp, unit.helmet_hp, unit.speed),
                         (123.5, 50, 20, 0.5))
        self.assertTrue(unit.headless)

    def test_all_catalog_types_parse(self):
        for name in PLANTS:
            with self.subTest(plant=name):
                self.assertEqual(parse_scenario({"plants": [plant(type=name)]})
                                 .plants[0].type, name)
        for name in ZOMBIES:
            with self.subTest(zombie=name):
                self.assertEqual(parse_scenario({"zombies": [zombie(type=name)]})
                                 .zombies[0].type, name)

    def test_invalid_top_level_values(self):
        invalid = [None, [], "scenario", 1, True,
                   {"unknown": 1}, {"version": 3}, {"version": True},
                   {"version": 1.0}, {"version": "1"},
                   {"seed": True}, {"seed": 1.5}, {"seed": None},
                   {"seed": 10**1000},
                   {"max_frames": 0}, {"max_frames": -1},
                   {"max_frames": True}, {"max_frames": 1.0},
                   {"max_frames": 10_000_001}, {"max_frames": 10**1000},
                   {"plants": None},
                   {"plants": {}}, {"zombies": "normal"}, {"brains": None}]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ScenarioError):
                parse_scenario(data)

    def test_invalid_plants(self):
        invalid = [None, 1, {}, plant(type="not_a_plant"), plant(type=1),
                   plant(row=0), plant(row=6), plant(row=True), plant(row=3.0),
                   plant(col=0), plant(col=10), plant(col=2.0),
                   plant(hp=-1), plant(hp=301), plant(hp=True),
                   plant(cooldown=None), plant(cooldown=-1),
                   plant(state_timer=1.5), plant(id=""), plant(id=3),
                   plant(speed=1)]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ScenarioError):
                parse_scenario({"plants": [value]})

    def test_invalid_zombies(self):
        invalid = [None, {}, zombie(type="not_a_zombie"), zombie(type=False),
                   zombie(row=0), zombie(row=6), zombie(row=True),
                   zombie(row=3.0), zombie(col=0), zombie(col=10),
                   zombie(x=100), {"type": "normal", "row": 3},
                   zombie(hp=-1), zombie(hp=271), zombie(hp=True),
                   zombie(helmet_hp=1), zombie(shield_hp=1),
                   zombie(speed=0), zombie(speed=-1), zombie(speed=6),
                   zombie(speed=True), zombie(speed=math.nan),
                   zombie(speed=math.inf), zombie(headless=1),
                   zombie(age=-1), zombie(chilled=1.5), zombie(id=""),
                   zombie(unknown=1)]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ScenarioError):
                parse_scenario({"zombies": [value]})
        for x in (math.nan, math.inf, -math.inf, True, -1001, 2001):
            with self.subTest(x=x), self.assertRaises(ScenarioError):
                parse_scenario({"zombies": [{"type": "normal", "row": 3, "x": x}]})

    def test_invalid_brains(self):
        invalid = [[], [0], [6], [True], [3.0], [3, 3],
                   [{"row": 3, "hp": 0}], [{"row": 3, "hp": 71}],
                   [{"row": 3, "hp": True}], [{"row": 3, "x": 1}], [{}]]
        for brains in invalid:
            with self.subTest(brains=brains), self.assertRaises(ScenarioError):
                parse_scenario({"brains": brains})

    def test_overlapping_plants_are_rejected(self):
        with self.assertRaises(ScenarioError):
            parse_scenario({"plants": [plant(), plant(type="wallnut")]})

    def test_ids_are_globally_unique(self):
        cases = [{"plants": [plant(id="same"), plant(row=2, id="same")]},
                 {"plants": [plant(id="same")], "zombies": [zombie(id="same")]},
                 {"plants": [plant(id="z1")], "zombies": [zombie()]}]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ScenarioError):
                parse_scenario(data)


class SettlementTests(unittest.TestCase):
    def simulate(self, data):
        from pvz_ize.engine import Simulator
        return Simulator(parse_scenario(data)).run()

    def test_empty_field_is_immediate_plant_win(self):
        result = self.simulate({})
        self.assertEqual(result["winner"], "plants")
        self.assertEqual(result["frames"], 0)
        self.assertEqual(result["brains"][0]["row"], 3)
        self.assertEqual(result["brains"][0]["hp"], 70)

    def test_frame_limit_is_undecided(self):
        result = self.simulate({"max_frames": 1, "zombies": [zombie()]})
        self.assertEqual(result["winner"], "undecided")
        self.assertEqual(result["frames"], 1)
        self.assertTrue(result["reason"])

    def test_all_zombies_move_from_first_frame(self):
        result = self.simulate({"max_frames": 1, "zombies": [
            zombie(id="a", speed=0.2), zombie(id="b", row=2, speed=0.4)]})
        units = {z["id"]: z for z in result["zombies"]}
        self.assertAlmostEqual(units["a"]["x"], 569.8)
        self.assertAlmostEqual(units["b"]["x"], 569.6)
        self.assertEqual(units["a"]["age"], 1)
        self.assertEqual(units["b"]["age"], 1)

    def test_initial_dead_or_off_board_zombies_do_not_block_settlement(self):
        units = [{"type": "normal", "row": 3, "x": 900},
                 {"type": "normal", "row": 3, "x": -200},
                 zombie(hp=0)]
        for unit in units:
            with self.subTest(unit=unit):
                result = self.simulate({"zombies": [unit]})
                self.assertEqual(result["winner"], "plants")
                self.assertEqual(result["frames"], 0)
                self.assertEqual(result["brains"][0]["hp"], 70)

    def test_run_is_repeatable_and_does_not_mutate_initial_scenario(self):
        from pvz_ize.engine import Simulator
        scenario = parse_scenario({"max_frames": 10, "zombies": [zombie()]})
        original = copy.deepcopy(scenario.to_dict())
        simulator = Simulator(scenario)
        first = simulator.run()
        self.assertEqual(scenario.to_dict(), original)
        self.assertEqual(simulator.run(), first)
        first["brains"][0]["hp"] = -1
        self.assertEqual(simulator.run()["brains"][0]["hp"], 70)

    def test_unopposed_zombie_eats_default_brain(self):
        result = self.simulate({"zombies": [zombie(col=1)], "max_frames": 20_000})
        self.assertEqual(result["winner"], "zombies")
        self.assertTrue(all(b["hp"] == 0 for b in result["brains"]))

    def test_zombie_in_a_brainless_row_exits_and_does_not_block_settlement(self):
        result = self.simulate({"brains": [5], "zombies": [zombie(row=1, col=1)],
                                "max_frames": 20_000})
        self.assertEqual(result["winner"], "plants")
        self.assertEqual(result["brains"][0]["hp"], 70)

    def test_arbitrary_brain_row_can_be_eaten(self):
        result = self.simulate({"brains": [1], "zombies": [zombie(row=1, col=1)],
                                "max_frames": 20_000})
        self.assertEqual(result["winner"], "zombies")
        self.assertEqual(result["brains"][0]["hp"], 0)

    def test_one_eaten_brain_does_not_mean_zombie_win(self):
        result = self.simulate({"brains": [1, 5],
                                "zombies": [zombie(row=1, col=1)],
                                "max_frames": 20_000})
        self.assertEqual(result["winner"], "plants")
        self.assertEqual({b["row"]: b["hp"] for b in result["brains"]}, {1: 0, 5: 70})


if __name__ == "__main__":
    unittest.main()
