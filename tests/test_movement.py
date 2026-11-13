import unittest

from pvz_ize import movement
from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


class MovementTests(unittest.TestCase):
    def zombie(self, **extra):
        return parse_scenario({"movement_mode": "animation", "zombies": [{
            "type": "normal", "row": 3, "x": 500, "velocity_parameter": .3,
            "animation_phase": 0, "walk_variant": 1, **extra}]}).zombies[0]

    def test_track_velocity_matches_source_formula(self):
        z = self.zombie()
        xs = movement.tracks()["Zombie/anim_walk"]
        rate = .3 * len(xs) / (xs[-1] - xs[0]) * 47
        self.assertAlmostEqual(movement.displacement(z), (xs[1]-xs[0]) * .01 * rate)
        self.assertAlmostEqual(z.animation_phase, .01 * rate / len(xs))

    def test_chill_halves_rate_and_displacement_at_same_phase(self):
        normal, cold = self.zombie(), self.zombie(chilled=1000)
        self.assertAlmostEqual(movement.displacement(normal), 2 * movement.displacement(cold))
        self.assertAlmostEqual(normal.animation_phase, 2 * cold.animation_phase)

    def test_phase_changes_instantaneous_motion(self):
        a, b = self.zombie(), self.zombie(animation_phase=.5)
        self.assertNotEqual(movement.displacement(a), movement.displacement(b))

    def test_animation_initial_state_replays_full_result(self):
        data = {"seed": 13, "max_frames": 1200, "movement_mode": "animation",
                "plants": [{"type": "snow_pea", "row": 3, "col": 1}],
                "zombies": [{"type": "conehead", "row": 3, "col": 7}]}
        scenario = parse_scenario(data)
        self.assertEqual(Simulator(scenario).run(), Simulator(parse_scenario(scenario.to_dict())).run())

    def test_all_track_types_have_data_and_finite_motion(self):
        for name in ("normal", "football", "imp", "pole_vaulting", "ladder", "digger",
                     "gargantuar", "red_eye_gargantuar", "newspaper", "balloon"):
            with self.subTest(type=name):
                data = {"movement_mode": "animation", "max_frames": 500,
                        "zombies": [{"type": name, "row": 3, "col": 7}]}
                result = Simulator(parse_scenario(data)).run()
                self.assertEqual(result["movement_mode"], "animation")
                self.assertLess(result["zombies"][0]["x"], 600)

    def test_all_zombie_types_replay_even_when_track_is_not_used(self):
        from pvz_ize.catalog import ZOMBIES
        for name in ZOMBIES:
            with self.subTest(type=name):
                initial = parse_scenario({"movement_mode": "animation", "max_frames": 100,
                    "zombies": [{"type": name, "row": 3, "col": 7}]})
                self.assertEqual(Simulator(initial).run(),
                                 Simulator(parse_scenario(initial.to_dict())).run())

    def test_initial_missing_tools_choose_walking_not_running_parameters(self):
        for name in ("pole_vaulting", "ladder"):
            initial = parse_scenario({"movement_mode": "animation", "zombies": [
                {"type": name, "row": 3, "col": 7, "tool": False}]})
            self.assertTrue(.23 <= initial.zombies[0].velocity_parameter <= .37)
            sim = Simulator(initial)
            self.assertEqual(sim.zombies[0].speed, .143)
            self.assertFalse(sim.zombies[0].tool)

    def test_first_walking_frame_preserves_explicit_phase(self):
        scenario = parse_scenario({"movement_mode": "animation", "zombies": [
            {"type": "normal", "row": 3, "col": 7, "animation_phase": .5}]})
        sim = Simulator(scenario)
        expected = movement.displacement(scenario.zombies[0])
        before = sim.zombies[0].x
        sim.move(sim.zombies[0])
        self.assertAlmostEqual(before-sim.zombies[0].x, expected)


if __name__ == "__main__":
    unittest.main()
