"""Source-derived checks for Plant/Projectile/Zombie star and corn mechanics.

References: Portable Plant.cpp StarFruitFire/UpdateShooter/FindTargetAndFire,
Projectile.cpp GetDamageFlags/FindCollisionTarget/UpdateLobMotion, and
Zombie.cpp ApplyButter. These test the offline approximation, not game parity.
"""

import math
import unittest

from pvz_ize.engine import Projectile, Simulator
from pvz_ize.model import parse_scenario


def make_sim(plant_type="kernelpult", zombie_type="normal", *, row=3,
             zombie_row=3, zombie_x=500, seed=0, **zombie_state):
    return Simulator(parse_scenario({
        "seed": seed,
        "plants": [{"type": plant_type, "row": row, "col": 3, "cooldown": 1}],
        "zombies": [{"type": zombie_type, "row": zombie_row, "x": zombie_x,
                     **zombie_state}],
    }))


class StarfruitTests(unittest.TestCase):
    def test_exact_five_vectors_and_spawn_origin(self):
        sim = make_sim("starfruit")
        plant = sim.plants[0]
        sim.fire(plant, 1)
        diagonal = math.sqrt(3) * 3.33 / 2
        expected = [(-3.33, 0), (0, 3.33), (0, -3.33),
                    (diagonal, 1.665), (diagonal, -1.665)]
        self.assertEqual(len(sim.projectiles), 5)
        for shot, (vx, vy) in zip(sim.projectiles, expected):
            self.assertAlmostEqual(shot.vx, vx)
            self.assertAlmostEqual(shot.vy, vy)
            self.assertEqual((shot.x, shot.y), (plant.x + 25, plant.y + 25))
            self.assertEqual(shot.motion, "star")
            self.assertEqual(shot.kind, "star")
        self.assertFalse(any(q.vx > 0 and q.vy == 0 for q in sim.projectiles))

    def test_same_row_front_zombie_does_not_trigger_shooting(self):
        sim = make_sim("starfruit", zombie_x=500)
        self.assertFalse(sim.targets(sim.plants[0]))
        sim.queue_shot(sim.plants[0])
        self.assertFalse(sim.plants[0].shots)

    def test_same_row_behind_zombie_triggers_shooting(self):
        sim = make_sim("starfruit", zombie_x=30)
        self.assertEqual(sim.targets(sim.plants[0]), sim.zombies)

    def test_cross_row_vertical_target_triggers_shooting(self):
        sim = make_sim("starfruit", zombie_row=2, zombie_x=185)
        self.assertEqual(sim.targets(sim.plants[0]), sim.zombies)

    def test_recently_bitten_starfruit_can_fire_at_front_target(self):
        sim = make_sim("starfruit", zombie_x=500)
        self.assertFalse(sim.targets(sim.plants[0]))
        sim.plants[0].recently_eaten = 50
        self.assertEqual(sim.targets(sim.plants[0]), sim.zombies)

    def test_vertical_stars_can_damage_other_rows(self):
        for target_row, direction in ((2, -1), (4, 1)):
            with self.subTest(target_row=target_row):
                sim = make_sim("starfruit", zombie_row=target_row, zombie_x=185)
                sim.fire(sim.plants[0], 1)
                shot = next(q for q in sim.projectiles if q.vx == 0 and q.vy * direction > 0)
                for _ in range(60):
                    if not shot.active:
                        break
                    sim.update_projectile(shot)
                self.assertEqual(sim.zombies[0].hp, 250)
                self.assertEqual(shot.row, target_row)

    def test_left_star_bypasses_door_but_right_diagonal_does_not(self):
        for vx, vy, body_damage, shield_damage in ((-3.33, 0, 20, 0),
                                                   (math.sqrt(3) * 3.33 / 2, 1.665, 0, 20)):
            with self.subTest(vx=vx):
                sim = make_sim("starfruit", "screen_door", zombie_x=300)
                unit = sim.zombies[0]
                left, _ = sim.hitbox(unit)
                shot = Projectile("test", "p1", 3, left - vx, "star", y=310,
                                  vx=vx, vy=vy, motion="star")
                sim.update_projectile(shot)
                self.assertFalse(shot.active)
                self.assertEqual(unit.hp, 270 - body_damage)
                self.assertEqual(unit.shield_hp, 1100 - shield_damage)

    def test_digger_immunity_depends_on_star_age_and_horizontal_direction(self):
        for age, vx, should_hit in ((0, 1, False), (23, 0, False),
                                    (24, 1, True), (0, -1, True)):
            with self.subTest(age=age, vx=vx):
                sim = make_sim("starfruit", "digger", zombie_x=300, helmet_hp=0)
                unit = sim.zombies[0]
                unit.phase, unit.direction = "digger_walking", 1
                left, _ = sim.hitbox(unit)
                shot = Projectile("test", "p1", 3, left - vx, "star", age=age,
                                  y=310, vx=vx, motion="star")
                sim.update_projectile(shot)
                self.assertEqual(unit.hp, 250 if should_hit else 270)
                self.assertEqual(shot.active, not should_hit)

    def test_star_is_removed_outside_vertical_playfield(self):
        sim = make_sim("starfruit")
        for y, vy in ((40, -3.33), (600, 3.33)):
            with self.subTest(y=y):
                shot = Projectile("test", "p1", 3, 200, "star", y=y,
                                  vx=0, vy=vy, motion="star")
                sim.update_projectile(shot)
                self.assertFalse(shot.active)


class KernelpultTests(unittest.TestCase):
    def test_period_is_300_minus_integer_in_0_through_14(self):
        periods = set()
        for seed in range(100):
            sim = make_sim(seed=seed)
            sim.update_plant(sim.plants[0])
            periods.add(sim.plants[0].cooldown)
        self.assertEqual(periods, set(range(286, 301)))

    def test_attack_windup_is_29_updates(self):
        sim = make_sim()
        events = []
        sim.event_sink = events.append
        for frame in range(1, 31):
            sim.frame = frame
            sim.update_plant(sim.plants[0])
            if frame < 30:
                self.assertFalse(sim.projectiles)
        started = next(e for e in events if e["event"] == "attack_started")
        fired = next(e for e in events if e["event"] == "projectile_fired")
        self.assertEqual(fired["frame"] - started["frame"], 29)

    def test_one_of_four_random_outcomes_selects_butter(self):
        class FourOutcomes:
            def __init__(self):
                self.outcomes = iter(range(4))

            def randrange(self, bound):
                if bound != 4:
                    raise AssertionError("butter selection must have four equiprobable outcomes")
                return next(self.outcomes)

        sim = make_sim()
        sim.rng = FourOutcomes()
        for _ in range(4):
            sim.queue_shot(sim.plants[0])
        self.assertEqual([q["kind"] for q in sim.plants[0].shots],
                         ["butter", "kernel", "kernel", "kernel"])

    def test_seeded_butter_selection_replays(self):
        def choices(seed):
            sim = make_sim(seed=seed)
            for _ in range(40):
                sim.queue_shot(sim.plants[0])
            return [q["kind"] for q in sim.plants[0].shots]

        self.assertEqual(choices(42), choices(42))
        self.assertNotEqual(choices(42), choices(43))
        self.assertEqual(set(choices(42)), {"kernel", "butter"})

    def test_lob_origin_initial_velocity_and_gravity(self):
        for kind, dx, dy in (("kernel", 19, -37), ("butter", 12, -56)):
            with self.subTest(kind=kind):
                sim = make_sim()
                plant = sim.plants[0]
                sim.fire(plant, 1, kind)
                shot = sim.projectiles[0]
                self.assertEqual((shot.x, shot.y), (plant.x + dx, plant.y + dy))
                self.assertEqual(shot.motion, "lob")
                self.assertEqual(shot.vy, 0)
                initial_x, initial_vz, vx = shot.x, shot.vz, shot.vx
                self.assertLess(initial_vz, 0)
                sim.update_projectile(shot)
                self.assertAlmostEqual(shot.vz, initial_vz + 0.115)
                self.assertAlmostEqual(shot.z, initial_vz + 0.115)
                self.assertAlmostEqual(shot.x, initial_x + vx)
                self.assertEqual(sim.zombies[0].hp, 270)

    def test_lob_takes_time_and_does_not_track_moving_target(self):
        sim = make_sim()
        sim.fire(sim.plants[0], 1, "kernel")
        shot = sim.projectiles[0]
        vx, initial_x = shot.vx, shot.x
        sim.zombies[0].x = 750
        for _ in range(60):
            sim.update_projectile(shot)
        self.assertAlmostEqual(shot.x, initial_x + 60 * vx)
        self.assertEqual(shot.vx, vx)
        self.assertEqual(sim.zombies[0].hp, 270)
        self.assertLess(shot.z, 0)
        for _ in range(150):
            if not shot.active:
                break
            sim.update_projectile(shot)
        self.assertFalse(shot.active)
        self.assertEqual(sim.zombies[0].hp, 270)

    def test_actual_fired_lob_eventually_hits_stationary_target(self):
        for kind, damage in (("kernel", 20), ("butter", 40)):
            with self.subTest(kind=kind):
                sim = make_sim()
                sim.zombies[0].eating = True
                sim.fire(sim.plants[0], 1, kind)
                shot = sim.projectiles[0]
                for _ in range(20):
                    sim.update_projectile(shot)
                self.assertEqual(sim.zombies[0].hp, 270)
                for _ in range(150):
                    if not shot.active:
                        break
                    sim.update_projectile(shot)
                self.assertEqual(sim.zombies[0].hp, 270 - damage)

    def test_kernel_and_butter_damage_bypass_screen_door(self):
        for kind, damage in (("kernel", 20), ("butter", 40)):
            with self.subTest(kind=kind):
                sim = make_sim(zombie_type="screen_door")
                sim.fire(sim.plants[0], 1, kind)
                shot = sim.projectiles[0]
                for _ in range(170):
                    if not shot.active:
                        break
                    sim.update_projectile(shot)
                self.assertEqual(sim.zombies[0].hp, 270 - damage)
                self.assertEqual(sim.zombies[0].shield_hp, 1100)

    def butter_hit(self, sim):
        unit = sim.zombies[0]
        left, _ = sim.hitbox(unit)
        shot = Projectile("test", "p1", unit.row, left, "butter",
                          age=30, vx=0, vz=0, motion="lob")
        sim.update_projectile(shot)
        return unit

    def test_butter_pauses_movement_and_resumes_when_counter_expires(self):
        sim = make_sim()
        unit = self.butter_hit(sim)
        self.assertEqual(unit.buttered, 400)
        original_x = unit.x
        for _ in range(399):
            sim.update_zombie(unit)
        self.assertEqual(unit.x, original_x)
        self.assertEqual(unit.buttered, 1)
        sim.update_zombie(unit)
        self.assertEqual(unit.buttered, 0)
        self.assertLess(unit.x, original_x)

    def test_butter_pauses_eating_then_bites_resume(self):
        sim = make_sim(zombie_x=160)
        plant = sim.plants[0]
        unit = self.butter_hit(sim)
        unit.eating = True
        initial_hp = plant.hp
        for _ in range(399):
            sim.update_zombie(unit)
        self.assertEqual(plant.hp, initial_hp)
        sim.update_zombie(unit)
        self.assertLess(plant.hp, initial_hp)

    def test_headless_zombies_take_damage_without_butter(self):
        sim = make_sim(headless=True)
        unit = self.butter_hit(sim)
        self.assertEqual(unit.hp, 230)
        self.assertEqual(unit.buttered, 0)

    def test_hit_that_removes_head_does_not_apply_butter(self):
        sim = make_sim(hp=110)
        unit = self.butter_hit(sim)
        self.assertEqual(unit.hp, 70)
        self.assertTrue(unit.headless)
        self.assertEqual(unit.buttered, 0)


if __name__ == "__main__":
    unittest.main()
