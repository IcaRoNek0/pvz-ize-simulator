"""Shared native projectile selection and pre-sync coordinate regressions."""

import unittest

from pvz_ize.engine import Projectile, Simulator
from pvz_ize.model import parse_scenario


def board(zombies=None, plants=None):
    return Simulator(parse_scenario({"seed": 3,
        "zombies": zombies or [{"type": "normal", "row": 3, "x": 300}],
        "plants": plants or []}))


class ProjectileSelectionTests(unittest.TestCase):
    def test_collision_chooses_sprite_x_not_hitbox_left_in_both_directions(self):
        for direction in (1, -1):
            sim = board([{"id": "normal", "type": "normal", "row": 3, "x": 200},
                         {"id": "giant", "type": "gargantuar", "row": 3, "x": 220}])
            sim.update_projectile(Projectile("q", "p", 3, 200, "pea", direction))
            self.assertEqual([z.hp for z in sim.zombies], [250, 3000])

    def test_integer_x_tie_retains_array_order_not_fraction_or_hitbox(self):
        for reverse in (False, True):
            units = [{"id": "normal", "type": "normal", "row": 3, "x": 200.9},
                     {"id": "giant", "type": "gargantuar", "row": 3, "x": 200.1}]
            sim = board(list(reversed(units)) if reverse else units)
            hits = sim.projectile_targets(3, 200, 240)
            self.assertEqual([z.id for z in hits], [z.id for z in sim.zombies])

    def test_negative_integer_tie_uses_truncation_and_array_order(self):
        sim = board([{"id": "first", "type": "normal", "row": 3, "x": -.9},
                     {"id": "second", "type": "gargantuar", "row": 3, "x": .1}])
        self.assertEqual([z.id for z in sim.projectile_targets(3, 0, 40)], ["first", "second"])

    def test_candidate_filters_precede_selection(self):
        sim = board([{"id": "ally", "type": "normal", "row": 3, "x": 190, "hypnotized": True},
                     {"id": "other-row", "type": "gargantuar", "row": 2, "x": 200},
                     {"id": "target", "type": "normal", "row": 3, "x": 200}])
        self.assertEqual([z.id for z in sim.projectile_targets(3, 190, 240)], ["target"])

    def test_plant_target_order_is_not_changed_by_projectile_selection(self):
        sim = board([{"id": "normal", "type": "normal", "row": 3, "x": 200},
                     {"id": "giant", "type": "gargantuar", "row": 3, "x": 220}])
        self.assertEqual([z.id for z in sim.in_range(3, 200, 240)], ["giant", "normal"])
        self.assertEqual([z.id for z in sim.projectile_targets(3, 200, 240)], ["normal", "giant"])

    def test_old_x_for_all_shared_and_extended_projectiles(self):
        for kind, motion, x, damage in (("star", "star", 295.9, 20),
                ("kernel", "lob", 295.9, 20), ("butter", "lob", 295.9, 40),
                ("cabbage", "lob", 295.9, 40), ("melon", "lob", 255.9, 80),
                ("winter_melon", "lob", 255.9, 80), ("cactus_spike", "straight", 295.9, 20)):
            with self.subTest(kind=kind):
                sim = board()
                q = Projectile("q", "p", 3, x, kind, motion=motion, vx=3.33, vy=0, y=310, z=1)
                sim.update_projectile(q)
                self.assertEqual(sim.zombies[0].hp, 270)
                self.assertTrue(q.active)
                sim.update_projectile(q)
                self.assertEqual(sim.zombies[0].hp, 270 - damage)
                self.assertFalse(q.active)

    def test_extended_projectiles_use_shared_sprite_x_selection(self):
        for kind, motion in (("cabbage", "lob"), ("melon", "lob"), ("cactus_spike", "straight")):
            sim = board([{"id": "normal", "type": "normal", "row": 3, "x": 200},
                         {"id": "giant", "type": "gargantuar", "row": 3, "x": 220}])
            q = Projectile("q", "p", 3, 200, kind, motion=motion, vx=0, y=310, z=1)
            sim.update_projectile(q)
            self.assertLess(sim.zombies[0].hp, 270)
            # Melon splashes the giant, but normal must receive primary damage.
            if kind == "melon":
                self.assertEqual(sim.zombies[0].hp, 190)
                self.assertEqual(sim.zombies[1].hp, 2974)
            else:
                self.assertEqual(sim.zombies[1].hp, 3000)

    def test_homing_uses_old_x_but_moved_float_y_and_assigned_target(self):
        sim = board()
        z = sim.zombies[0]
        q = Projectile("q", "p", 3, 295.9, "cattail_spike", motion="homing",
                       vx=2, vy=0, y=310, target=z.id)
        sim.update_projectile(q)
        self.assertTrue(q.active)
        self.assertEqual(z.hp, 270)
        sim.update_projectile(q)
        self.assertFalse(q.active)
        self.assertEqual(z.hp, 250)

    def test_star_row_uses_moved_y_even_when_x_is_old(self):
        sim = board([{"type": "normal", "row": 4, "x": 300}])
        q = Projectile("q", "p", 3, 336, "star", motion="star", vx=0, vy=3.33, y=379)
        sim.update_projectile(q)
        self.assertEqual(q.row, 4)
        self.assertEqual(sim.zombies[0].hp, 250)

    def test_homing_height_uses_new_y_and_target_need_not_match_updated_row(self):
        sim = board()
        q = Projectile("q", "p", 2, 336, "cattail_spike", motion="homing",
                       vx=0, vy=2, y=249.9, target=sim.zombies[0].id)
        sim.update_projectile(q)
        self.assertEqual(q.row, 2)
        self.assertGreater(q.y, 250)
        self.assertEqual(sim.zombies[0].hp, 250)
        self.assertFalse(q.active)

    def test_homing_does_not_retarget_to_lower_x_collision_candidate(self):
        sim = board([{"id": "other", "type": "normal", "row": 3, "x": 280},
                     {"id": "locked", "type": "normal", "row": 3, "x": 300}])
        q = Projectile("q", "p", 3, 336, "cattail_spike", motion="homing",
                       vx=2, vy=0, y=310, target="locked")
        sim.update_projectile(q)
        self.assertEqual([z.hp for z in sim.zombies], [270, 250])

    def test_melon_z_collision_window_is_minus_35_not_minus_30(self):
        for kind, x, damage in (("melon", 316, 80), ("winter_melon", 316, 80),
                                 ("cabbage", 336, 0), ("kernel", 336, 0), ("butter", 336, 0)):
            sim = board()
            q = Projectile("q", "p", 3, x, kind, motion="lob", vx=0,
                           z=-34.5, vz=0, age=21)
            sim.update_projectile(q)
            self.assertEqual(sim.zombies[0].hp, 270 - damage, kind)

    def test_melon_exact_z_threshold_and_rising_still_do_not_collide(self):
        for z, vz in ((-36, .885), (-34, -1)):
            sim = board()
            q = Projectile("q", "p", 3, 316, "melon", motion="lob", vx=0, z=z, vz=vz, age=21)
            sim.update_projectile(q)
            self.assertTrue(q.active)
            self.assertEqual(sim.zombies[0].hp, 270)

    def test_zombie_pea_uses_old_rectangle_with_strict_eight_overlap(self):
        sim = board(plants=[{"type": "wallnut", "row": 3, "col": 3}])
        q = Projectile("q", "z", 3, 279.9, "zombie_pea", direction=-1)
        sim.update_projectile(q)
        self.assertTrue(q.active)
        self.assertEqual(sim.plants[0].hp, 4000)
        sim.update_projectile(q)
        self.assertFalse(q.active)
        self.assertEqual(sim.plants[0].hp, 3980)

    def test_normalized_replay_matches_after_multi_species_collision(self):
        s = parse_scenario({"movement_mode": "animation", "max_frames": 5000,
            "plants": [{"type": "melon_pult", "row": 3, "col": 2}],
            "zombies": [{"type": "normal", "row": 3, "x": 400},
                        {"type": "gargantuar", "row": 3, "x": 420}]})
        self.assertEqual(Simulator(s).run(), Simulator(parse_scenario(s.to_dict())).run())
