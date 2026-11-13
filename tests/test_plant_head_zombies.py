"""Source-level contracts for all six plant-headed zombie variants."""

import unittest

from pvz_ize import plant_head_zombies as heads
from pvz_ize.catalog import ZOMBIES
from pvz_ize.engine import Projectile, Simulator
from pvz_ize.model import parse_scenario


def board(kind="pea_head", plants=(), **attributes):
    events = []
    data = {"seed": 123, "plants": list(plants), "zombies": [
        {"type": kind, "row": 3, "x": 400, **attributes}]}
    sim = Simulator(parse_scenario(data), events.append)
    heads.initialize(sim, sim.zombies[0])
    return sim, sim.zombies[0], events


def plant(kind="wallnut", col=2, row=3, **attributes):
    return {"type": kind, "row": row, "col": col, **attributes}


def tick(sim, z, count=1):
    for _ in range(count):
        sim.frame += 1
        heads.update(sim, z)


class PlantHeadTests(unittest.TestCase):
    def test_all_six_have_distinct_source_health_and_nonmetal_helmets(self):
        self.assertEqual(ZOMBIES["pea_head"].hp, 270)
        self.assertEqual(ZOMBIES["jalapeno_head"].hp, 500)
        self.assertEqual(ZOMBIES["wallnut_head"].helmet, 1100)
        self.assertEqual(ZOMBIES["tallnut_head"].helmet, 2200)
        for kind in ("wallnut_head", "tallnut_head"):
            self.assertFalse(ZOMBIES[kind].metal)
        self.assertEqual(ZOMBIES["squash_head"].speed, .38)

    def test_pea_head_fires_every_150_frames_even_while_eating(self):
        sim, z, events = board()
        z.eating = True
        tick(sim, z, 300)
        shots = [event for event in events if event["event"] == "projectile_fired"]
        self.assertEqual([event["frame"] for event in shots], [150, 300])
        self.assertEqual([(q.kind, q.direction) for q in sim.projectiles],
                         [("zombie_pea", -1), ("zombie_pea", -1)])

    def test_gatling_head_fires_at_original_counter_values(self):
        sim, z, events = board("gatling_head")
        tick(sim, z, 300)
        self.assertEqual([e["frame"] for e in events if e["event"] == "zombie_shot"],
                         [82, 99, 115, 132, 232, 249, 265, 282])

    def test_chill_slows_body_motion_not_phase_counter(self):
        sim, z, events = board(chilled=1000)
        tick(sim, z, 150)
        self.assertEqual(len(sim.projectiles), 1)

    def test_frozen_and_butter_pause_counter(self):
        for attribute in ("frozen", "buttered"):
            with self.subTest(attribute=attribute):
                sim, z, _ = board(**{attribute: 100})
                tick(sim, z, 100)
                self.assertEqual(z.phase_timer, 150)
                self.assertFalse(sim.projectiles)
                setattr(z, attribute, 0)
                tick(sim, z, 150)
                self.assertEqual(len(sim.projectiles), 1)

    def test_headless_shooter_stops_firing(self):
        sim, z, _ = board(headless=True)
        tick(sim, z, 300)
        self.assertFalse(sim.projectiles)

    def test_original_hypnotized_shooter_keeps_hostile_pea(self):
        sim, z, _ = board(hypnotized=True)
        tick(sim, z, 150)
        self.assertEqual(sim.projectiles[0].kind, "zombie_pea")
        self.assertEqual(sim.projectiles[0].direction, -1)

    def test_muzzle_interpolates_local_body_head_track(self):
        sim, z, _ = board()
        z.animation_phase = .5
        z.phase_timer = 1
        tick(sim, z)
        expected = z.x + heads.HEAD_X["walk2"][23] - 9
        self.assertAlmostEqual(sim.projectiles[0].x, expected)

    def test_zombie_pea_hits_plants_not_other_zombies(self):
        sim, z, events = board(plants=[plant("peashooter", col=2)])
        shot = Projectile("q", z.id, 3, 160, "zombie_pea", -1)
        self.assertTrue(heads.update_projectile(sim, shot))
        self.assertEqual(sim.plants[0].hp, 280)
        self.assertEqual(z.hp, 270)
        self.assertFalse(shot.active)
        self.assertEqual(events[-1]["event"], "projectile_hit_plant")

    def test_zombie_pea_passes_low_plants(self):
        for kind in ("puff_shroom", "potato_mine", "spikeweed", "spikerock", "lily_pad"):
            with self.subTest(kind=kind):
                sim, z, _ = board(plants=[plant(kind)])
                shot = Projectile("q", z.id, 3, 160, "zombie_pea", -1)
                hp = sim.plants[0].hp
                heads.update_projectile(sim, shot)
                self.assertTrue(shot.active)
                self.assertEqual(sim.plants[0].hp, hp)

    def test_zombie_pea_hits_pumpkin_protecting_low_plant(self):
        sim, z, _ = board(plants=[plant("puff_shroom"), plant("pumpkin")])
        shot = Projectile("q", z.id, 3, 160, "zombie_pea", -1)
        heads.update_projectile(sim, shot)
        self.assertFalse(shot.active)
        self.assertEqual(sim.plants[0].hp, 300)
        self.assertEqual(sim.plants[1].hp, 3980)

    def test_zombie_pea_kills_plant_and_stops(self):
        sim, z, _ = board(plants=[plant("peashooter", hp=20)])
        shot = Projectile("q", z.id, 3, 160, "zombie_pea", -1)
        heads.update_projectile(sim, shot)
        self.assertEqual(sim.plants[0].state, "destroyed")
        self.assertFalse(shot.active)
        self.assertTrue(heads.update_projectile(sim, shot))

    def test_other_projectile_kind_is_not_claimed(self):
        sim, z, _ = board()
        shot = Projectile("q", z.id, 3, 160, "pea")
        self.assertFalse(heads.update_projectile(sim, shot))
        self.assertEqual(shot.x, 160)

    def test_jalapeno_burns_own_row_only_then_dies(self):
        sim, z, events = board("jalapeno_head", plants=[
            plant("wallnut", col=1), plant("pumpkin", col=1),
            plant("spikerock", col=2), plant("wallnut", col=1, row=2)])
        z.phase_timer = 1
        tick(sim, z)
        self.assertEqual([p.hp for p in sim.plants], [0, 0, 0, 4000])
        self.assertEqual(z.status, "dead")
        self.assertTrue(any(e["event"] == "jalapeno_head_exploded" for e in events))

    def test_jalapeno_counter_uses_source_nominal_velocity_formula(self):
        sim, z, _ = board("jalapeno_head", velocity_parameter=.3)
        self.assertEqual(z.phase_timer % 2, 0)
        self.assertTrue(int(275 / .3) * 2 <= z.phase_timer <= int(449 / .3) * 2)

    def test_jalapeno_does_not_burn_airborne_squash(self):
        sim, z, _ = board("jalapeno_head", plants=[plant("squash")])
        sim.plants[0].state = "airborne"
        z.phase_timer = 1
        tick(sim, z)
        self.assertEqual(sim.plants[0].hp, 300)

    def test_squash_needs_eating_then_crushes_current_square(self):
        sim, z, events = board("squash_head", plants=[
            plant("wallnut", col=2), plant("pumpkin", col=2),
            plant("wallnut", col=3)])
        z.x = 125
        self.assertFalse(heads.update(sim, z))
        z.eating = True
        self.assertTrue(heads.update(sim, z))
        self.assertTrue(z.headless)
        self.assertFalse(z.eating)
        self.assertEqual((z.phase, z.phase_timer), ("head_squash_rising", 95))
        tick(sim, z, 102)
        self.assertTrue(sim.plants[0].hp > 0)
        tick(sim, z)
        self.assertEqual([p.hp for p in sim.plants], [0, 0, 4000])
        tick(sim, z, 102)
        self.assertEqual(z.status, "dead")
        self.assertTrue(any(e["event"] == "squash_head_impact" for e in events))

    def test_squash_does_not_crush_spikerock(self):
        sim, z, _ = board("squash_head", plants=[plant("spikerock", col=2)])
        z.x, z.eating = 125, True
        heads.update(sim, z)
        tick(sim, z, 103)
        self.assertEqual(sim.plants[0].hp, 450)

    def test_dead_zombie_does_not_fire_or_burn(self):
        sim, z, _ = board("jalapeno_head", plants=[plant()])
        z.status, z.phase_timer = "dead", 1
        heads.update(sim, z)
        self.assertEqual(sim.plants[0].hp, 4000)


if __name__ == "__main__":
    unittest.main()
