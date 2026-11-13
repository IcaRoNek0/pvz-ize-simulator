"""Regression checks for zombie combat and custom-brain settlement."""

import unittest

from pvz_ize.engine import Projectile, Simulator
from pvz_ize.model import parse_scenario


def zombie(type_="normal", **overrides):
    return {"type": type_, "row": 3, "x": 100, **overrides}


def simulator(zombies=None, plants=None, **overrides):
    return Simulator(parse_scenario({
        "seed": 0, "max_frames": 1000,
        "zombies": zombies or [], "plants": plants or [], **overrides,
    }))


class BrainChewingTests(unittest.TestCase):
    def test_brain_needs_seventy_bites_not_seventy_damage(self):
        sim = simulator([zombie(x=-30)], max_frames=279)
        result = sim.run()
        self.assertEqual(result["winner"], "undecided")
        self.assertEqual(result["brains"][0]["hp"], 1)
        self.assertEqual(result["events"]["brain_bitten"], 69)

        sim = simulator([zombie(x=-30)], max_frames=280)
        result = sim.run()
        self.assertEqual(result["winner"], "zombies")
        self.assertEqual(result["frames"], 280)
        self.assertEqual(result["events"]["brain_bitten"], 70)

    def test_two_zombies_share_brain_counter(self):
        result = simulator([zombie(x=-30), zombie(x=-30)]).run()
        self.assertEqual(result["winner"], "zombies")
        self.assertEqual(result["frames"], 140)
        self.assertEqual(result["events"]["brain_bitten"], 70)
        self.assertEqual(result["events"]["brain_eaten"], 1)
        self.assertEqual(result["brains"][0]["hp"], 0)

    def test_shared_brain_does_not_receive_extra_bites_after_depletion(self):
        result = simulator([zombie(x=-30), zombie(x=-30)],
                           brains=[{"row": 3, "hp": 3}]).run()
        self.assertEqual(result["frames"], 8)
        self.assertEqual(result["events"]["brain_bitten"], 3)
        self.assertEqual(result["brains"][0]["hp"], 0)

    def test_chilled_brain_chewing_uses_eight_frame_interval(self):
        result = simulator([zombie(x=-30, chilled=1000)]).run()
        self.assertEqual(result["winner"], "zombies")
        self.assertEqual(result["frames"], 560)

    def test_brain_mouth_threshold_is_not_lawn_edge(self):
        result = simulator([zombie(x=-29, speed=0.001)], max_frames=4).run()
        self.assertEqual(result["brains"][0]["hp"], 70)
        self.assertNotIn("brain_bitten", result["events"])

    def test_last_brain_takes_precedence_over_remaining_zombies(self):
        result = simulator([zombie(x=-30), zombie(row=2, x=700)],
                           brains=[{"row": 3, "hp": 1}]).run()
        self.assertEqual(result["winner"], "zombies")
        self.assertEqual(result["frames"], 4)
        self.assertTrue(any(z["status"] == "active" for z in result["zombies"]))


class DamageLayerTests(unittest.TestCase):
    def test_helmet_absorbs_then_spills_to_body(self):
        for kind in ("conehead", "buckethead", "football"):
            with self.subTest(kind=kind):
                sim = simulator([zombie(kind, helmet_hp=10)])
                z = sim.zombies[0]
                sim.damage(z, 20, "test")
                self.assertEqual((z.helmet_hp, z.hp), (0, 260))
                self.assertEqual(sim.counts["armor_lost"], 1)

    def test_shield_absorbs_then_spills_to_body(self):
        sim = simulator([zombie("screen_door", shield_hp=10)])
        z = sim.zombies[0]
        sim.damage(z, 20, "test")
        self.assertEqual((z.shield_hp, z.hp), (0, 260))

    def test_full_helmet_stops_damage_but_not_chill(self):
        sim = simulator([zombie("buckethead")])
        z = sim.zombies[0]
        sim.damage(z, 20, "ice", chill=True)
        self.assertEqual((z.helmet_hp, z.hp, z.chilled), (1080, 270, 1000))

    def test_full_screen_door_stops_damage_and_chill(self):
        sim = simulator([zombie("screen_door")])
        z = sim.zombies[0]
        sim.damage(z, 20, "ice", chill=True)
        self.assertEqual((z.shield_hp, z.hp, z.chilled), (1080, 270, 0))

    def test_ice_overflow_from_screen_door_can_chill_body(self):
        sim = simulator([zombie("screen_door", shield_hp=10)])
        z = sim.zombies[0]
        sim.damage(z, 20, "ice", chill=True)
        self.assertEqual((z.shield_hp, z.hp, z.chilled), (0, 260, 1000))

    def test_fume_hits_screen_door_and_body(self):
        sim = simulator([zombie("screen_door")],
                        [{"type": "fume_shroom", "row": 3, "col": 1}])
        sim.fire(sim.plants[0], 1)
        self.assertEqual((sim.zombies[0].shield_hp, sim.zombies[0].hp), (1080, 250))

    def test_backwards_pea_ignores_screen_door(self):
        sim = simulator([zombie("screen_door")])
        q = Projectile("q", "split", 3, 180, "pea", direction=-1)
        sim.update_projectile(q)
        self.assertFalse(q.active)
        self.assertEqual((sim.zombies[0].shield_hp, sim.zombies[0].hp), (1100, 250))

    def test_screen_door_resists_fireball_splash(self):
        sim = simulator([zombie("screen_door", chilled=50)])
        q = Projectile("q", "torch", 3, 125, "fire")
        sim.update_projectile(q)
        self.assertFalse(q.active)
        self.assertEqual((sim.zombies[0].shield_hp, sim.zombies[0].hp,
                          sim.zombies[0].chilled), (1060, 270, 0))

    def test_screen_door_is_not_hit_by_nearby_fireball_splash(self):
        sim = simulator([zombie("screen_door"), zombie("screen_door", x=160)])
        sim.update_projectile(Projectile("q", "torch", 3, 125, "fire"))
        self.assertEqual((sim.zombies[1].shield_hp, sim.zombies[1].hp), (1100, 270))

    def test_body_head_loss_threshold_is_strict(self):
        sim = simulator([zombie(hp=90)])
        z = sim.zombies[0]
        self.assertFalse(z.headless)
        sim.damage(z, 1, "test")
        self.assertEqual(z.hp, 89)
        self.assertTrue(z.headless)
        self.assertEqual(z.status, "active")

    def test_no_double_death_or_damage_for_dead_zombie(self):
        sim = simulator([zombie()])
        z = sim.zombies[0]
        sim.damage(z, 1800, "test")
        sim.damage(z, 20, "again")
        sim.kill(z, "again")
        self.assertEqual(z.status, "dead")
        self.assertEqual(sim.counts["zombie_died"], 1)
        self.assertEqual(sim.counts["damage"], 1)


class ZombieActionTests(unittest.TestCase):
    def test_headless_zombie_cannot_bite_plant_but_still_blocks_settlement(self):
        sim = simulator([zombie(x=120, hp=89)],
                        [{"type": "sunflower", "row": 3, "col": 2}], max_frames=4)
        result = sim.run()
        self.assertEqual(result["plants"][0]["hp"], 300)
        self.assertEqual(result["winner"], "undecided")
        self.assertLess(result["zombies"][0]["x"], 120)
        self.assertEqual(result["zombies"][0]["status"], "active")

    def test_headless_football_cannot_bite_brain_but_is_not_yet_gone(self):
        result = simulator([zombie("football", x=-40, hp=89)], max_frames=4).run()
        self.assertEqual(result["brains"][0]["hp"], 70)
        self.assertEqual(result["zombies"][0]["status"], "active")
        self.assertEqual(result["winner"], "undecided")

    def test_plant_bite_interval_and_four_damage_per_bite(self):
        sim = simulator([zombie(x=120)],
                        [{"type": "sunflower", "row": 3, "col": 2}], max_frames=4)
        result = sim.run()
        self.assertEqual(result["events"]["plant_bitten"], 1)
        self.assertEqual(result["plants"][0]["hp"], 296)

    def test_nut_bites_accelerate_only_after_five_hundred_unhit_frames(self):
        for kind in ("wallnut", "tallnut"):
            with self.subTest(kind=kind):
                sim = simulator([zombie(x=120, age=499)],
                                [{"type": kind, "row": 3, "col": 2}])
                z, p = sim.zombies[0], sim.plants[0]
                initial = p.hp
                sim.update_zombie(z)
                self.assertEqual(p.hp, initial - 4)
                for _ in range(4):
                    sim.update_zombie(z)
                self.assertEqual(p.hp, initial - 12)

    def test_recent_body_damage_suppresses_accelerated_nut_bites(self):
        sim = simulator([zombie(x=120, age=600)],
                        [{"type": "wallnut", "row": 3, "col": 2}])
        z, p = sim.zombies[0], sim.plants[0]
        sim.damage(z, 20, "test")
        for _ in range(4):
            sim.update_zombie(z)
        self.assertEqual(p.hp, 3996)

    def test_brainless_row_entry_is_not_zombie_victory(self):
        result = simulator([zombie(row=1, x=-99.9, speed=1)]).run()
        self.assertEqual(result["winner"], "plants")
        self.assertEqual(result["zombies"][0]["status"], "entered_house")
        self.assertEqual(result["brains"][0]["hp"], 70)

    def test_football_house_boundary_differs_from_normal(self):
        sim = simulator([zombie("football", row=1, x=-174, speed=0.32)], max_frames=1)
        result = sim.run()
        self.assertEqual(result["winner"], "undecided")
        self.assertEqual(result["zombies"][0]["status"], "active")
        result = simulator([zombie("football", row=1, x=-175)]).run()
        self.assertEqual(result["winner"], "plants")
        self.assertEqual(result["frames"], 0)


if __name__ == "__main__":
    unittest.main()
