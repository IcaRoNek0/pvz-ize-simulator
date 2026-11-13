import unittest

from pvz_ize.engine import Simulator
from pvz_ize.model import ScenarioError, parse_scenario


class JackInputTests(unittest.TestCase):
    def data(self, countdown=3, **zombie):
        return {"seed": 2026, "max_frames": 200,
                "zombies": [{"type": "jack_in_the_box", "row": 3, "x": 600,
                             "jack_countdown_frames": countdown, **zombie}]}

    def test_countdown_is_before_110_frame_opening_sequence(self):
        events = []
        sim = Simulator(parse_scenario(self.data()), event_sink=events.append)
        result = sim.run()
        opening = next(e for e in events if e.get("phase") == "jack_popping")
        explosion = next(e for e in events if e["event"] == "jack_exploded")
        self.assertEqual((opening["frame"], explosion["frame"]), (3, 113))
        self.assertEqual(result["winner"], "plants")

    def test_zero_starts_opening_on_first_update(self):
        result = Simulator(parse_scenario(self.data(0))).run()
        self.assertEqual(result["frames"], 111)

    def test_freeze_pauses_countdown_but_chill_does_not(self):
        self.assertEqual(Simulator(parse_scenario(self.data(chilled=1000))).run()["frames"], 113)
        self.assertEqual(Simulator(parse_scenario(self.data(frozen=4))).run()["frames"], 116)

    def test_missing_box_prevents_explosion(self):
        result = Simulator(parse_scenario(self.data(tool=False))).run()
        self.assertNotIn("jack_exploded", result["events"])

    def test_magnet_cancels_explicit_countdown(self):
        data = self.data(5, x=420)
        data["plants"] = [{"type": "magnet_shroom", "row": 3, "col": 5, "cooldown": 0}]
        result = Simulator(parse_scenario(data)).run()
        self.assertEqual(result["events"]["tool_removed"], 1)
        self.assertNotIn("jack_exploded", result["events"])

    def test_normalized_input_replays_and_keeps_countdown(self):
        scenario = parse_scenario(self.data(17))
        replay = parse_scenario(scenario.to_dict())
        self.assertEqual(replay.zombies[0].jack_countdown_frames, 17)
        self.assertEqual(Simulator(scenario).run(), Simulator(replay).run())

    def test_invalid_values_and_wrong_species(self):
        for value in (-1, True, 1.5, None, 10000001):
            with self.assertRaises(ScenarioError):
                parse_scenario(self.data(value))
        with self.assertRaises(ScenarioError):
            parse_scenario(self.data(type="normal"))
