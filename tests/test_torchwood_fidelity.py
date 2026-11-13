"""Native torch conversion and imminent-collision boundary regressions."""

import unittest

from pvz_ize.engine import Projectile, Simulator
from pvz_ize.model import parse_scenario


def board(*, col=1, row=3, zombies=None):
    return Simulator(parse_scenario({"seed": 3,
        "plants": [{"type": "torchwood", "row": row, "col": col}],
        "zombies": zombies if zombies is not None else [{"type": "normal", "row": 3, "x": 0}]}))


class TorchwoodTests(unittest.TestCase):
    def test_clip_strict_ten_boundary_and_integer_truncation(self):
        for x, clips in ((20, False), (20.9, False), (21, True)):
            sim = board()
            q = Projectile("q", "p", 3, x, "pea")
            sim.update_projectile(q)
            self.assertEqual(sim.zombies[0].hp, 270 if clips else 250, x)
            self.assertEqual(q.active, clips)
            self.assertEqual(sim.counts["torch_clip"], int(clips))

    def test_clip_does_not_convert_tag_or_stop_movement(self):
        sim = board()
        q = Projectile("q", "p", 3, 21, "ice")
        sim.update_projectile(q)
        self.assertEqual((q.kind, q.last_torch, q.age), ("ice", -1, 1))
        self.assertAlmostEqual(q.x, 24.33)
        self.assertTrue(q.active)
        self.assertEqual((sim.zombies[0].hp, sim.zombies[0].chilled), (270, 0))

    def test_no_clip_for_backward_shots(self):
        sim = board()
        q = Projectile("q", "p", 3, 21, "pea", direction=-1)
        sim.update_projectile(q)
        self.assertEqual(sim.zombies[0].hp, 250)
        self.assertFalse(q.active)

    def test_no_clip_for_lobbed_peas(self):
        sim = board()
        q = Projectile("q", "p", 3, 21, "pea", motion="lob", vx=3.33, z=1)
        sim.update_projectile(q)
        self.assertEqual(sim.zombies[0].hp, 250)
        self.assertEqual(sim.counts["torch_clip"], 0)

    def test_non_pea_kinds_do_not_clip(self):
        for kind in ("puff", "spore", "fire"):
            sim = board()
            q = Projectile("q", "p", 3, 21, kind)
            sim.update_projectile(q)
            self.assertEqual(sim.zombies[0].hp, 230 if kind == "fire" else 250)
            self.assertEqual(sim.counts["torch_clip"], 0)

    def test_dead_other_row_and_already_used_torch_do_not_clip(self):
        for variant in ("dead", "other-row", "same-col"):
            sim = board(row=2 if variant == "other-row" else 3)
            q = Projectile("q", "p", 3, 21, "pea")
            if variant == "dead":
                sim.plants[0].hp = 0
            elif variant == "same-col":
                q.last_torch = sim.plants[0].col
            sim.update_projectile(q)
            self.assertEqual(sim.zombies[0].hp, 250, variant)

    def test_conversion_is_bidirectional_and_not_motion_limited(self):
        for direction in (1, -1):
            for motion in ("straight", "lob"):
                sim = board()
                q = Projectile("q", "p", 3, 75, "pea", direction, motion=motion, vx=0)
                sim.projectiles.append(q)
                sim.update_plant(sim.plants[0])
                self.assertEqual((q.kind, q.last_torch), ("fire", 1))

    def test_conversion_uses_integer_rectangle_and_inclusive_ten(self):
        for x, converts in ((59.9, False), (60, True), (125.9, True), (126, False)):
            sim = board()
            q = Projectile("q", "p", 3, x, "pea")
            sim.projectiles.append(q)
            sim.update_plant(sim.plants[0])
            self.assertEqual(q.kind, "fire" if converts else "pea", x)

    def test_ice_thaws_once_per_column_then_different_column_ignites(self):
        for direction in (1, -1):
            sim = Simulator(parse_scenario({"plants": [
                {"type": "torchwood", "row": 3, "col": 1},
                {"type": "torchwood", "row": 3, "col": 2}]}))
            q = Projectile("q", "p", 3, 75, "ice", direction)
            sim.projectiles.append(q)
            sim.update_plant(sim.plants[0])
            sim.update_plant(sim.plants[0])
            self.assertEqual((q.kind, q.last_torch), ("pea", 1))
            q.x = 155
            sim.update_plant(sim.plants[1])
            self.assertEqual((q.kind, q.last_torch), ("fire", 2))
            self.assertEqual(sim.counts["torch"], 2)

    def test_thawed_pea_does_not_clip_on_same_column(self):
        sim = board()
        q = Projectile("q", "p", 3, 75, "ice")
        sim.projectiles.append(q)
        sim.update_plant(sim.plants[0])
        q.x = 21
        sim.update_projectile(q)
        self.assertEqual(sim.zombies[0].hp, 250)
        self.assertEqual(sim.counts["torch_clip"], 0)

    def test_bungee_grab_pauses_conversion_but_grounded_tree_still_clips(self):
        sim = board(zombies=[{"type": "bungee", "row": 3, "col": 1},
                             {"type": "normal", "row": 3, "x": 0}])
        sim.zombies[0].phase, sim.zombies[0].target = "bungee_grabbing", sim.plants[0].id
        q = Projectile("q", "p", 3, 75, "pea")
        sim.projectiles.append(q)
        sim.update_plant(sim.plants[0])
        self.assertEqual(q.kind, "pea")
        q.x = 21
        sim.update_projectile(q)
        self.assertTrue(q.active)
        self.assertEqual(sim.zombies[1].hp, 270)

    def test_conversion_and_clip_ignore_inactive_or_wrong_row_projectiles(self):
        for active, row in ((False, 3), (True, 2)):
            sim = board()
            q = Projectile("q", "p", row, 75, "pea", active=active)
            sim.projectiles.append(q)
            sim.update_plant(sim.plants[0])
            self.assertEqual(q.kind, "pea")

    def test_plant_phase_converts_before_projectile_moves(self):
        sim = board(zombies=[])
        q = Projectile("q", "p", 3, 60, "pea")
        sim.projectiles.append(q)
        sim.update_plant(sim.plants[0])
        self.assertEqual(q.kind, "fire")
        sim.update_projectile(q)
        self.assertEqual(q.kind, "fire")
        self.assertAlmostEqual(q.x, 63.33)
        self.assertEqual(sim.counts["torch_clip"], 0)

    def test_normalized_replay_with_forward_and_rear_peas(self):
        s = parse_scenario({"movement_mode": "animation", "max_frames": 10000,
            "plants": [{"type": "torchwood", "row": 3, "col": 1},
                       {"type": "split_pea", "row": 3, "col": 2},
                       {"type": "torchwood", "row": 3, "col": 3}],
            "zombies": [{"type": "digger", "row": 3, "x": 0, "underground": False},
                        {"type": "buckethead", "row": 3, "x": 600}]})
        a = Simulator(s).run()
        self.assertEqual(a, Simulator(parse_scenario(s.to_dict())).run())
