import copy
import random
import unittest

from pvz_ize import movement
from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


class WalkRestartTests(unittest.TestCase):
    def board(self, kind="conehead", mode="animation", **attrs):
        sim = Simulator(parse_scenario({"seed": 201, "movement_mode": mode,
            "zombies": [{"type": kind, "row": 3, "x": 600, **attrs}]}))
        z = sim.zombies[0]
        z.eating, z.age, z.animation_phase = True, 4, .6
        return sim, z

    def test_stop_draws_speed_before_variant_and_advances_without_moving(self):
        sim, z = self.board()
        rng = random.Random()
        rng.setstate(sim.rng.getstate())
        velocity, variant = rng.uniform(.23, .37), rng.randrange(2)
        sim.chew(z)
        self.assertFalse(z.eating)
        self.assertEqual(z.x, 600)
        self.assertEqual(z.velocity_parameter, velocity)
        self.assertEqual(z.walk_variant, variant)
        self.assertEqual(sim.rng.getstate(), rng.getstate())
        reference = copy.copy(z)
        reference.animation_phase = 0
        movement.displacement(reference)
        self.assertEqual(z.animation_phase, reference.animation_phase)
        self.assertGreater(z.animation_phase, 0)
        self.assertEqual(sim._walk_segments[z.id], (movement.track_name(z), z.speed))
        dx = movement.displacement(reference)
        sim.move(z)
        self.assertAlmostEqual(z.x, 600 - dx)
        self.assertEqual(z.animation_phase, reference.animation_phase)
        self.assertEqual(sim.rng.getstate(), rng.getstate())

    def test_postvault_pole_still_consumes_variant_draw(self):
        sim, z = self.board("pole_vaulting")
        z.phase, z.speed, z.tool = "pole_walking", .143, False
        rng = random.Random()
        rng.setstate(sim.rng.getstate())
        velocity, variant = rng.uniform(.23, .37), rng.randrange(2)
        sim.chew(z)
        self.assertEqual((z.velocity_parameter, z.walk_variant), (velocity, variant))
        self.assertEqual(sim.rng.getstate(), rng.getstate())
        self.assertGreater(z.animation_phase, 0)

    def test_special_tracks_skip_variant_draw(self):
        for kind, phase, bounds in (("ladder", None, (.79, .81)),
                                    ("newspaper", "newspaper_mad", (.89, .91))):
            sim, z = self.board(kind)
            if phase:
                z.phase = phase
            rng = random.Random()
            rng.setstate(sim.rng.getstate())
            expected = rng.uniform(*bounds)
            sim.chew(z)
            self.assertEqual(z.velocity_parameter, expected)
            self.assertEqual(sim.rng.getstate(), rng.getstate())

    def test_flag_and_pea_head_consume_then_force_variant_zero(self):
        for kind in ("flag", "pea_head"):
            sim, z = self.board(kind)
            rng = random.Random()
            rng.setstate(sim.rng.getstate())
            if kind != "flag":
                rng.uniform(.23, .37)
            rng.randrange(2)
            sim.chew(z)
            self.assertEqual(z.walk_variant, 0)
            if kind == "flag":
                self.assertEqual(z.velocity_parameter, .45)
            self.assertEqual(sim.rng.getstate(), rng.getstate())

    def test_mean_mode_is_unchanged(self):
        sim, z = self.board(mode="mean")
        state = sim.rng.getstate()
        sim.chew(z)
        self.assertFalse(z.eating)
        self.assertEqual((z.x, z.animation_phase), (600, .6))
        self.assertEqual(state, sim.rng.getstate())

    def test_only_stops_on_bite_cadence(self):
        sim, z = self.board()
        state = sim.rng.getstate()
        z.age = 3
        sim.chew(z)
        self.assertTrue(z.eating)
        self.assertEqual(state, sim.rng.getstate())
        z.age = 4
        sim.chew(z)
        self.assertFalse(z.eating)
        self.assertNotEqual(state, sim.rng.getstate())

    def test_chill_halves_tick_end_advance(self):
        plain, a = self.board()
        cold, b = self.board(chilled=100)
        a.age = b.age = 8
        plain.chew(a)
        cold.chew(b)
        self.assertAlmostEqual(a.animation_phase, 2 * b.animation_phase)

    def test_hypnotized_target_disappears_waits_for_cadence_and_next_tick(self):
        for mode in ("mean", "animation"):
            sim, z = self.board(mode=mode, hypnotized=True)
            state = sim.rng.getstate()
            z.age = 2
            sim.update_zombie(z)
            self.assertEqual((z.x, z.eating), (600, True))
            self.assertEqual(sim.rng.getstate(), state)
            sim.update_zombie(z)
            self.assertEqual((z.x, z.eating), (600, False))
            if mode == "animation":
                self.assertGreater(z.animation_phase, 0)
                self.assertLess(z.animation_phase, .1)
                self.assertNotEqual(sim.rng.getstate(), state)
            sim.update_zombie(z)
            self.assertGreater(z.x, 600)

    def test_killing_hypnotized_bite_does_not_stop_until_next_cadence(self):
        sim, z = self.board(hypnotized=True)
        other = sim.spawn_zombie("normal", z.row, 610)
        other.hp = 4
        sim.update_zombie(z)
        self.assertEqual(other.hp, 4)
        z.age = 3
        sim.update_zombie(z)
        self.assertEqual(other.hp, 0)
        self.assertEqual((z.x, z.eating), (600, True))
        for _ in range(3):
            sim.update_zombie(z)
            self.assertEqual((z.x, z.eating), (600, True))
        sim.update_zombie(z)
        self.assertEqual((z.x, z.eating), (600, False))

    def test_normalized_replay_including_stop(self):
        raw = {"movement_mode": "animation", "max_frames": 1000,
               "plants": [{"type": "wallnut", "row": 3, "col": 4, "hp": 4}],
               "zombies": [{"type": "conehead", "row": 3, "x": 280}]}
        scenario = parse_scenario(raw)
        result = Simulator(scenario).run()
        self.assertGreater(result["events"].get("walking_started", 0), 0)
        self.assertEqual(result, Simulator(parse_scenario(scenario.to_dict())).run())
