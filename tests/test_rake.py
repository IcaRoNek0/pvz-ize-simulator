import unittest

from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


class RakeTests(unittest.TestCase):
    def test_rake_is_one_shot_and_hits_for_1800(self):
        scenario = parse_scenario({
            "max_frames": 5,
            "brains": [{"row": 3, "hp": 70}],
            "rakes": [{"row": 3, "col": 8}],
            "zombies": [{"type": "gargantuar", "row": 3, "x": 600}],
        })
        sim = Simulator(scenario)
        result = sim.run()
        self.assertEqual(result["zombies"][0]["hp"], 1200)
        self.assertEqual(result["pending_effects"].get("rakes"), None)
        self.assertEqual(sim.rakes[0]["state"], "triggered")

    def test_rake_schema_round_trip(self):
        scenario = parse_scenario({"rakes": [{"row": 2, "col": 8}]})
        self.assertEqual(scenario.to_dict()["rakes"], [{"row": 2, "col": 8}])


    def test_initial_ladder_grid_item_round_trip(self):
        from pvz_ize.model import parse_scenario
        from pvz_ize.engine import Simulator
        scenario = parse_scenario({'ladders': [{'row': 3, 'col': 2}]})
        self.assertEqual(scenario.to_dict()['ladders'], [{'row': 3, 'col': 2}])
        self.assertEqual(Simulator(scenario).ladders, {(3, 2)})


if __name__ == "__main__":
    unittest.main()