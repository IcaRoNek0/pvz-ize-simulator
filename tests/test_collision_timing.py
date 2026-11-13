"""Static-native regression probes; not live-game parity tests."""

import unittest

from pvz_ize.engine import Projectile, Simulator
from pvz_ize.model import parse_scenario


class CollisionTimingTests(unittest.TestCase):
    def board(self, x=300, kind="normal", **attrs):
        return Simulator(parse_scenario({"seed": 3,
            "zombies": [{"type": kind, "row": 3, "x": x, **attrs}]}))

    def test_straight_forward_collision_uses_pre_motion_integer_x(self):
        for kind in ("pea", "ice", "puff", "spore"):
            sim = self.board()
            q = Projectile("q", "p", 3, 295.9, kind)
            sim.update_projectile(q)
            self.assertEqual(sim.zombies[0].hp, 270)
            self.assertTrue(q.active)
            self.assertAlmostEqual(q.x, 299.23)
            sim.update_projectile(q)
            self.assertEqual(sim.zombies[0].hp, 250)
            self.assertFalse(q.active)

    def test_backward_pea_uses_old_rectangle_not_new_left_edge(self):
        sim = self.board(x=200)
        q = Projectile("q", "p", 3, 295.5, "pea", direction=-1)
        sim.update_projectile(q)
        self.assertTrue(q.active)  # old left280 > zombie right278
        sim.update_projectile(q)
        self.assertFalse(q.active)
        self.assertEqual(sim.zombies[0].hp, 250)

    def test_puff_last_live_tick_does_not_gain_extra_range(self):
        sim = self.board()
        q = Projectile("q", "p", 3, 295.9, "puff", age=73)
        sim.update_projectile(q)
        self.assertTrue(q.active)
        sim.update_projectile(q)
        self.assertFalse(q.active)
        self.assertEqual(sim.zombies[0].hp, 270)

    def test_fireball_native_width_thirty_without_pea_left_extension(self):
        for shot_x, hit in ((205, False), (206, True), (278, True), (279, False)):
            sim = self.board(x=200)
            q = Projectile("q", "p", 3, shot_x, "fire")
            sim.update_projectile(q)
            self.assertEqual(sim.zombies[0].hp, 230 if hit else 270, shot_x)
            self.assertEqual(q.active, not hit)

    def test_fractional_negative_coordinate_truncates_towards_zero(self):
        sim = self.board(x=-75)  # zombie [-39,3]
        q = Projectile("q", "p", 3, -79.9, "puff")
        sim.update_projectile(q)
        self.assertFalse(q.active)  # [-79,-39] touches zombie
        self.assertEqual(sim.zombies[0].hp, 250)

    def test_plant_bite_reads_pre_move_x_at_cadence(self):
        sim = Simulator(parse_scenario({"plants": [{"type": "wallnut", "row": 3, "col": 4}],
            "zombies": [{"type": "normal", "row": 3, "x": 281.1, "speed": .2, "age": 3}]}))
        z, p = sim.zombies[0], sim.plants[0]
        sim.update_zombie(z)
        self.assertAlmostEqual(z.x, 280.9)
        self.assertFalse(z.eating)  # old mouth331..351 overlaps only19
        self.assertEqual(p.hp, 4000)
        for _ in range(4):
            sim.update_zombie(z)
        self.assertTrue(z.eating)
        self.assertEqual(p.hp, 3996)

    def test_brain_bite_uses_pre_move_x(self):
        sim = self.board(x=-29.9, age=3, speed=.2)
        z = sim.zombies[0]
        sim.update_zombie(z)
        self.assertLess(z.x, -30)
        self.assertFalse(z.eating)
        self.assertEqual(sim.brains[0].hp, 70)
        for _ in range(4):
            sim.update_zombie(z)
        self.assertTrue(z.eating)
        self.assertEqual(sim.brains[0].hp, 69)

    def test_straight_hit_shield_helmet_overflow_and_frozen_target(self):
        sim = self.board(x=200, kind="buckethead", helmet_hp=10, frozen=100)
        q = Projectile("q", "p", 3, 196, "pea")
        sim.update_projectile(q)
        self.assertEqual((sim.zombies[0].helmet_hp, sim.zombies[0].hp), (0, 260))

    def test_spikeweed_pulse_pops_launching_machine_and_dies(self):
        for kind in ("catapult", "zamboni"):
            sim = Simulator(parse_scenario({"plants": [{"type": "spikeweed", "row": 3, "col": 2}],
                "zombies": [{"type": kind, "row": 3, "x": 100}]}))
            z, p = sim.zombies[0], sim.plants[0]
            if kind == "catapult":
                z.phase, z.phase_timer = "catapult_launching", 100
            p.state, p.state_timer = "attacking", 75
            sim.special(p)
            self.assertEqual((p.hp, z.hp, z.status), (0, 0, "dead"))

    def test_spikeweed_pulse_continues_after_machine_destroys_plant(self):
        sim = Simulator(parse_scenario({"plants": [{"type": "spikeweed", "row": 3, "col": 2}],
            "zombies": [{"type": "zamboni", "row": 3, "x": 100},
                        {"type": "conehead", "row": 3, "x": 100}]}))
        p = sim.plants[0]
        p.state, p.state_timer = "attacking", 75
        sim.special(p)
        self.assertEqual(p.hp, 0)
        self.assertEqual(sim.zombies[0].status, "dead")
        self.assertEqual(sim.zombies[1].helmet_hp, 350)

    def test_spike_pulse_is_lethal_independent_of_runtime_machine_hp(self):
        for plant in ("spikeweed", "spikerock"):
            for machine in ("zamboni", "catapult"):
                sim = Simulator(parse_scenario({"plants": [{"type": plant, "row": 3, "col": 2}],
                    "zombies": [{"type": machine, "row": 3, "x": 100}]}))
                p, z = sim.plants[0], sim.zombies[0]
                z.hp = 5000
                p.state = "attacking"
                p.state_timer = 76 if plant == "spikeweed" else 71
                sim.update_plant(p)
                self.assertEqual(z.status, "dead", (plant, machine))
                self.assertEqual(p.hp, 0 if plant == "spikeweed" else 400)
                self.assertEqual(sim.counts["damage"], 1)

    def test_non_spike_1800_does_not_force_high_hp_machine_death(self):
        sim = self.board(kind="zamboni")
        sim.zombies[0].hp = 5000
        sim.damage(sim.zombies[0], 1800, "cherry", both=True)
        self.assertEqual((sim.zombies[0].status, sim.zombies[0].hp), ("active", 3200))

    def test_brain_uses_species_mouth_and_native_balloon_offset(self):
        cases = (("normal", False, -30), ("ladder", True, 10),
                 ("pogo", False, 0), ("balloon", False, -45))
        for kind, tool, threshold in cases:
            for delta, bites in ((0, True), (1, False)):
                sim = self.board(x=threshold + delta, kind=kind, tool=tool, age=4)
                sim.chew(sim.zombies[0])
                self.assertEqual(sim.brains[0].hp, 69 if bites else 70, (kind, delta))
