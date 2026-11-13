"""Integration checks for cross-module rules found during source review."""

import unittest

from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


class InteractionTests(unittest.TestCase):
    def sim(self, plants=(), zombies=(), **extra):
        return Simulator(parse_scenario({"plants": list(plants), "zombies": list(zombies), **extra}))

    def test_chomper_cannot_swallow_giant(self):
        sim = self.sim([{"type": "chomper", "row": 3, "col": 1}],
                       [{"type": "gargantuar", "row": 3, "x": 100}])
        p, z = sim.plants[0], sim.zombies[0]
        p.state = "biting"
        sim.special(p)
        self.assertEqual(z.hp, 2960)
        self.assertEqual(z.status, "active")
        self.assertNotEqual(p.state, "digesting")

    def test_hypnotized_zombie_bites_through_shield(self):
        sim = self.sim(zombies=[{"type": "normal", "row": 3, "x": 100, "hypnotized": True},
                               {"type": "screen_door", "row": 3, "x": 100}])
        a, b = sim.zombies
        a.age = 4
        self.assertTrue(sim.zombie_combat(a))
        self.assertEqual((b.hp, b.shield_hp), (266, 1100))

    def test_airborne_units_do_not_stop_to_bite_enemy(self):
        sim = self.sim(zombies=[{"type": "imp", "row": 3, "x": 100},
                               {"type": "normal", "row": 3, "x": 100, "hypnotized": True}])
        for phase in ("imp_thrown", "imp_landing", "pole_jumping", "balloon_flying"):
            sim.zombies[0].phase = phase
            self.assertFalse(sim.zombie_combat(sim.zombies[0]))
            self.assertFalse(sim.zombie_combat(sim.zombies[1]))

    def test_catapult_and_bungee_target_main_before_shell(self):
        plants = [{"type": "pumpkin", "row": 3, "col": 1},
                  {"type": "wallnut", "row": 3, "col": 1}]
        sim = self.sim(plants, [{"type": "catapult", "row": 3, "x": 600}], max_frames=230)
        result = sim.run()
        self.assertEqual([p["hp"] for p in result["plants"]], [4000, 3925])
        sim = self.sim(plants, [{"type": "bungee", "row": 3, "col": 1}])
        z = sim.zombies[0]
        z.phase, z.phase_timer = "bungee_waiting", 1
        sim.update_zombie(z)
        self.assertEqual(z.target, sim.plants[1].id)

    def test_magnet_prefers_carried_armor_over_placed_ladder(self):
        sim = self.sim([{"type": "magnet_shroom", "row": 3, "col": 1}],
                       [{"type": "buckethead", "row": 3, "x": 100}])
        sim.ladders.add((3, 1))
        sim.special(sim.plants[0])
        self.assertEqual(sim.zombies[0].helmet_hp, 0)
        self.assertIn((3, 1), sim.ladders)

    def test_magnet_distance_modes_are_explicit(self):
        plants = [{"type": "magnet_shroom", "row": 3, "col": 3}]
        zombies = [{"type": "buckethead", "row": 2, "x": 164},
                   {"type": "buckethead", "row": 3, "x": 254}]
        horizontal, source = (self.sim(plants, zombies, magnet_distance_mode=mode)
                              for mode in ("horizontal", "source"))
        for sim in (horizontal, source):
            sim.special(sim.plants[0])
        self.assertEqual([z.helmet_hp for z in horizontal.zombies], [0, 1100])
        self.assertEqual([z.helmet_hp for z in source.zombies], [1100, 0])

    def test_original_off_ground_bit_is_not_bit_three(self):
        sim = self.sim(zombies=[{"type": "balloon", "row": 3, "x": 500}])
        z = sim.zombies[0]
        z.phase = "balloon_popping"
        for attack in ("ground", "air", "homing", "lob"):
            self.assertFalse(sim.targetable(z, attack))
        for attack in ("off_ground", "explosion", "all"):
            self.assertTrue(sim.targetable(z, attack))

    def test_grounded_balloon_can_lose_head(self):
        sim = self.sim(zombies=[{"type": "balloon", "row": 3, "x": 500, "tool": False}])
        z = sim.zombies[0]
        self.assertEqual(z.speed, .143)
        sim.damage(z, 181, "test")
        self.assertTrue(z.headless)


if __name__ == "__main__":
    unittest.main()
