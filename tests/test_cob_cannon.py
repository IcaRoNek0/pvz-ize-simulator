import unittest

from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


class CobCannonTests(unittest.TestCase):
    def test_catalog_and_arming_reload(self):
        scenario = parse_scenario({
            "max_frames": 700,
            "brains": [{"row": 3, "hp": 70}],
            "plants": [{"type": "cob_cannon", "row": 3, "col": 2}],
            "zombies": [{"type": "normal", "row": 3, "x": 600}],
        })
        events = []
        result = Simulator(scenario, events.append).run()
        self.assertEqual(result["winner"], "plants")
        fired = [e for e in events if e["event"] == "cob_fired"]
        impacts = [e for e in events if e["event"] == "cob_impact"]
        self.assertEqual(len(fired), 1)
        self.assertEqual(len(impacts), 1)
        self.assertEqual(impacts[0]["zombies"], ["z1"])

    def test_cob_can_start_ready_with_explicit_zero_cooldown(self):
        scenario = parse_scenario({
            "max_frames": 50,
            "brains": [3],
            "plants": [{"type": "cob_cannon", "row": 3, "col": 2, "cooldown": 0}],
            "zombies": [{"type": "normal", "row": 3, "x": 600}],
        })
        events = []
        Simulator(scenario, events.append).run()
        self.assertTrue(any(e["event"] == "cob_fired" for e in events))


if __name__ == "__main__":
    unittest.main()

    def test_cob_cannon_occupies_two_columns(self):
        from pvz_ize.model import parse_scenario, ScenarioError
        with self.assertRaises(ScenarioError):
            parse_scenario({'plants':[{'type':'cob_cannon','row':3,'col':9}]})
        with self.assertRaises(ScenarioError):
            parse_scenario({'plants':[{'type':'cob_cannon','row':3,'col':2},{'type':'wallnut','row':3,'col':3}]})
