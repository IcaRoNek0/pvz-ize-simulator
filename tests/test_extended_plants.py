"""Hook-level regression tests independent of catalog integration."""

import unittest

from pvz_ize import extended_plants as ext
from pvz_ize.engine import Simulator
from pvz_ize.model import Plant, Zombie, Brain, Scenario, parse_scenario


def make_sim(kind="gatling_pea", zombies=None, row=3, col=2):
    plant = Plant("p", kind, row, col, ext.SPECS[kind][0], 1)
    if zombies is None:
        zombies = [Zombie("z", "normal", row, 400., 270, 0, 0, .143)]
    sim = Simulator(Scenario(5, 10000, [plant], zombies, [Brain(3)]))
    return sim, sim.plants[0]


class ExtendedPlantsTests(unittest.TestCase):
    def test_old_type_is_not_intercepted(self):
        sim, p = make_sim()
        p.type = "peashooter"
        self.assertFalse(ext.update(sim, p))

    def test_gatling_four_frame_offsets(self):
        sim, p = make_sim()
        sim.frame = 1
        self.assertTrue(ext.update(sim, p))
        self.assertEqual([s["due"] for s in p.shots], [33, 50, 66, 83])
        for frame in range(2, 84):
            sim.frame = frame
            ext.update(sim, p)
        self.assertEqual(len(sim.projectiles), 4)
        self.assertTrue(all(q.kind == "pea" for q in sim.projectiles))

    def test_gloom_four_pulses_and_adjacent_rows(self):
        sim, p = make_sim("gloom_shroom")
        z = sim.zombies[0]
        z.row, z.x = 2, p.x + 40
        z.shield_hp = 100
        for frame in range(1, 161):
            sim.frame = frame
            ext.update(sim, p)
        self.assertEqual(z.hp, 190)
        self.assertEqual(z.shield_hp, 20)
        self.assertEqual(sim.counts["gloom_pulse"], 4)

    def test_gloom_does_not_hit_two_rows_away(self):
        sim, p = make_sim("gloom_shroom")
        sim.zombies[0].row = 1
        self.assertEqual(ext._targets(sim, p), [])

    def test_cattail_chooses_nearest_with_air_priority(self):
        sim, p = make_sim("cattail")
        z = sim.zombies[0]
        sim.targetable = lambda z, attack="ground": True
        farther = Zombie("air", "balloon", 1, 700, 270, 0, 0, .143, phase="balloon_flying")
        sim.zombies.append(farther)
        # Unknown catalog balloon has the ordinary rectangle for this isolated hook test.
        sim.hitbox = lambda z: (z.x + 36, z.x + 78)
        self.assertIs(ext._targets(sim, p)[0], farther)
        farther.phase = "balloon_walking"
        self.assertIs(ext._targets(sim, p)[0], z)

    def test_cattail_second_launch(self):
        sim, p = make_sim("cattail")
        p.cooldown = 51
        ext.update(sim, p)
        self.assertEqual(len(p.shots), 1)

    def test_cabbage_hits_body_not_door(self):
        sim, p = make_sim("cabbage_pult")
        z = sim.zombies[0]
        z.shield_hp = 1100
        q = sim.add_projectile(p, 3, z.x + 36, "cabbage", motion="lob", vx=0, z=1)
        ext.update_projectile(sim, q)
        self.assertEqual(z.hp, 230)
        self.assertEqual(z.shield_hp, 1100)

    def test_winter_melon_splash_and_shield_body(self):
        sim, p = make_sim("winter_melon")
        z = sim.zombies[0]
        z.shield_hp = 1100
        other = Zombie("other", "normal", 2, z.x, 270, 0, 100, .143)
        sim.zombies.append(other)
        q = sim.add_projectile(p, 3, z.x + 16, "winter_melon", motion="lob", vx=0, z=1)
        ext.update_projectile(sim, q)
        self.assertEqual((z.hp, z.shield_hp, z.chilled), (190, 1020, 1000))
        self.assertEqual((other.hp, other.shield_hp, other.chilled), (244, 74, 1000))

    def test_lob_miss_is_removed(self):
        sim, p = make_sim("melon_pult", zombies=[])
        q = sim.add_projectile(p, 3, 300, "melon", motion="lob", vx=0, z=90, vz=1, age=150)
        ext.update_projectile(sim, q)
        self.assertFalse(q.active)

    def test_homing_lost_target_does_not_retarget(self):
        sim, p = make_sim("cattail")
        q = sim.add_projectile(p, 3, 300, "cattail_spike", y=p.y, vx=2, vy=0,
                               motion="homing", target="missing")
        ext.update_projectile(sim, q)
        self.assertEqual(q.x, 302)
        self.assertTrue(q.active)

    def test_garlic_fixed_up_and_delay(self):
        sim, p = make_sim("garlic")
        p.garlic_direction = "up"
        z = sim.zombies[0]
        self.assertFalse(ext.on_bite(sim, p, z))
        self.assertTrue(ext.on_bite(sim, p, z))
        for _ in range(169):
            self.assertTrue(ext.update_zombie(sim, z))
        self.assertEqual(z.row, 3)
        self.assertFalse(ext.update_zombie(sim, z))
        self.assertEqual(z.row, 2)

    def test_garlic_boundary_falls_back_to_valid_row(self):
        sim, p = make_sim("garlic", row=1)
        p.garlic_direction = "up"
        z = sim.zombies[0]
        ext.on_bite(sim, p, z)
        for _ in range(170):
            ext.update_zombie(sim, z)
        self.assertEqual(z.row, 2)

    def test_garlic_random_seed_replays(self):
        results = []
        for _ in range(2):
            sim, p = make_sim("garlic")
            ext.on_bite(sim, p, sim.zombies[0])
            for _ in range(170):
                ext.update_zombie(sim, sim.zombies[0])
            results.append(sim.zombies[0].row)
        self.assertEqual(results[0], results[1])

    def test_hypno_intercepts_before_damage(self):
        sim, p = make_sim("hypno_shroom")
        calls = []
        sim.hypnotize = lambda z, source: calls.append((z.id, source))
        self.assertTrue(ext.on_bite(sim, p, sim.zombies[0]))
        self.assertEqual(p.hp, 0)
        self.assertEqual(calls, [("z", "p")])

    def test_cherry_delay_and_1800_damage(self):
        sim, p = make_sim("cherry_bomb")
        sim.zombies[0].x = p.x + 30
        sim.zombies[0].hp = 3000
        for _ in range(99):
            ext.update(sim, p)
        self.assertEqual(sim.zombies[0].hp, 3000)
        ext.update(sim, p)
        self.assertEqual(sim.zombies[0].hp, 1200)
        self.assertEqual(p.hp, 0)

    def test_doom_destroys_all_same_cell_layers(self):
        sim, p = make_sim("doom_shroom")
        shell = Plant("shell", "pumpkin", 3, 2, 4000, 0)
        elsewhere = Plant("safe", "wallnut", 3, 3, 4000, 0)
        sim.plants.extend([shell, elsewhere])
        p.state_timer = 1
        ext.update(sim, p)
        self.assertEqual(shell.hp, 0)
        self.assertEqual(elsewhere.hp, 4000)

    def test_ice_freeze_random_range_and_repeat_shorter(self):
        sim, p = make_sim("ice_shroom")
        ext._ice(sim, p)
        z = sim.zombies[0]
        self.assertTrue(400 <= z.frozen <= 600)
        self.assertEqual(z.chilled, 2000)
        self.assertEqual(z.hp, 250)
        ext._ice(sim, p)
        self.assertTrue(300 <= z.frozen <= 400)

    def test_ice_leaves_underground_digger_unchilled(self):
        sim, p = make_sim("ice_shroom")
        z = sim.zombies[0]
        z.phase = "digger_tunneling"
        ext._ice(sim, p)
        self.assertEqual(z.chilled, 0)
        self.assertEqual(z.hp, 270)

    def test_instant_plants_cannot_be_chewed(self):
        for kind in ext.INSTANTS:
            with self.subTest(kind=kind):
                sim, p = make_sim(kind)
                self.assertTrue(ext.on_bite(sim, p, sim.zombies[0]))

    def test_jalapeno_only_burns_its_row_removes_ladders(self):
        sim, p = make_sim("jalapeno")
        sim.zombies[0].chilled = 100
        other = Zombie("other", "normal", 2, 400, 270, 0, 0, .143)
        sim.zombies.append(other)
        sim.ladders = {(3, 4), (2, 4)}
        p.state_timer = 1
        ext.update(sim, p)
        self.assertEqual(sim.zombies[0].hp, 0)
        self.assertEqual(other.hp, 270)
        self.assertEqual(sim.ladders, {(2, 4)})


class ExtendedPlantsIntegrationTests(unittest.TestCase):
    def run_layout(self, plants, zombies, **options):
        return Simulator(parse_scenario({"seed": 13, "max_frames": 3000,
                                        "plants": plants, "zombies": zombies,
                                        **options})).run()

    def test_stacked_gatlings_attack_independently(self):
        plants = [{"id": name, "type": "gatling_pea", "row": 3, "col": 1,
                   "cooldown": 1} for name in ("a", "b")]
        result = self.run_layout(plants, [{"type": "normal", "row": 3, "col": 7}],
                                 allow_stacking=True)
        self.assertEqual(result["winner"], "plants")
        self.assertGreaterEqual(result["events"]["projectile_fired"], 16)

    def test_pumpkin_protects_garlic_before_effect(self):
        plants = [{"type": "garlic", "row": 3, "col": 2, "garlic_direction": "up"},
                  {"type": "pumpkin", "row": 3, "col": 2, "hp": 20}]
        result = self.run_layout(plants, [{"type": "normal", "row": 3, "x": 120}], max_frames=400)
        self.assertEqual(result["plants"][1]["hp"], 0)
        self.assertEqual(result["zombies"][0]["row"], 2)
        self.assertLess(result["plants"][0]["hp"], 400)

    def test_hypno_real_run_wins_with_friendly_survivor(self):
        result = self.run_layout([{"type": "hypno_shroom", "row": 3, "col": 2}],
                                 [{"type": "normal", "row": 3, "x": 170}])
        self.assertEqual(result["winner"], "plants")
        self.assertTrue(result["zombies"][0]["hypnotized"])
        self.assertEqual(result["plants"][0]["hp"], 0)

    def test_cactus_pops_balloon_in_real_run(self):
        result = self.run_layout([{"type": "cactus", "row": 3, "col": 1, "cooldown": 1}],
                                 [{"type": "balloon", "row": 3, "col": 5}], max_frames=2000)
        self.assertEqual(result["events"].get("balloon_popped"), 1)
        self.assertNotEqual(result["zombies"][0]["phase"], "balloon_flying")

    def test_cattail_hits_other_row(self):
        result = self.run_layout([{"type": "cattail", "row": 1, "col": 2, "cooldown": 1}],
                                 [{"type": "normal", "row": 4, "col": 6}])
        self.assertGreater(result["events"].get("projectile_hit", 0), 0)
        self.assertLess(result["zombies"][0]["hp"], 270)

    def test_ice_melon_real_run_chills_adjacent_targets(self):
        result = self.run_layout([{"type": "winter_melon", "row": 3, "col": 1, "cooldown": 1}],
                                 [{"type": "normal", "row": r, "col": 6} for r in (2, 3, 4)],
                                 max_frames=200)
        self.assertTrue(all(z["chilled"] > 0 for z in result["zombies"]))

    def test_cactus_in_flight_spike_cannot_hit_popping_balloon(self):
        sim = Simulator(parse_scenario({"max_frames": 1,
            "plants": [{"type": "cactus", "row": 3, "col": 1}],
            "zombies": [{"type": "balloon", "row": 3, "x": 400}]}))
        z = sim.zombies[0]
        sim.pop_balloon(z, "test")
        sim.add_projectile(sim.plants[0], 3, 420, "cactus_spike", target="air")
        result = sim.run()
        self.assertEqual(result["zombies"][0]["hp"], 270)
        self.assertEqual(result["events"].get("projectile_hit", 0), 0)

    def test_cattail_cannot_hit_popping_balloon(self):
        sim = Simulator(parse_scenario({"max_frames": 1,
            "plants": [{"type": "cattail", "row": 3, "col": 1}],
            "zombies": [{"type": "balloon", "row": 3, "x": 400}]}))
        z = sim.zombies[0]
        sim.pop_balloon(z, "test")
        sim.add_projectile(sim.plants[0], 3, 420, "cattail_spike", y=300,
                           vx=2, vy=0, motion="homing", target=z.id)
        result = sim.run()
        self.assertEqual(result["zombies"][0]["hp"], 270)
        self.assertEqual(result["events"].get("projectile_hit", 0), 0)

    def test_ice_shroom_chills_but_does_not_freeze_bouncing_pogo(self):
        result = self.run_layout([{"type": "ice_shroom", "row": 3, "col": 1,
                                   "state_timer": 1}],
                                 [{"type": "pogo", "row": 3, "col": 5}], max_frames=1)
        self.assertEqual(result["zombies"][0]["frozen"], 0)
        self.assertGreater(result["zombies"][0]["chilled"], 0)
        self.assertEqual(result["zombies"][0]["hp"], 500)

    def test_melon_lob_cannot_hit_off_ground_popping_balloon(self):
        sim = Simulator(parse_scenario({"max_frames": 1,
            "plants": [{"type": "melon_pult", "row": 3, "col": 1}],
            "zombies": [{"type": "balloon", "row": 3, "x": 400}]}))
        z = sim.zombies[0]
        sim.pop_balloon(z, "test")
        sim.add_projectile(sim.plants[0], 3, 420, "melon", motion="lob", vx=0, z=1)
        result = sim.run()
        self.assertEqual(result["zombies"][0]["hp"], 270)

    def test_gloom_cannot_damage_off_ground_popping_balloon(self):
        sim = Simulator(parse_scenario({"max_frames": 76,
            "plants": [{"type": "gloom_shroom", "row": 3, "col": 4, "cooldown": 1}],
            "zombies": [{"type": "balloon", "row": 3, "x": 400}]}))
        sim.pop_balloon(sim.zombies[0], "test")
        result = sim.run()
        self.assertEqual(result["zombies"][0]["hp"], 270)

    def test_gloom_exact_touch_is_not_overlap(self):
        sim = Simulator(parse_scenario({"max_frames": 80,
            "plants": [{"type": "gloom_shroom", "row": 3, "col": 1, "cooldown": 1}],
            "zombies": [{"type": "normal", "row": 3, "x": 164, "speed": .001}]}))
        # Hold the zombie in place at the exact right edge, 40+160=200.
        sim.zombies[0].speed = 0
        result = sim.run()
        self.assertEqual(result["zombies"][0]["hp"], 270)
        self.assertEqual(result["events"].get("gloom_pulse", 0), 0)

    def test_cattail_cannot_hit_thrown_imp(self):
        sim = Simulator(parse_scenario({"max_frames": 1,
            "plants": [{"type": "cattail", "row": 3, "col": 1}],
            "zombies": [{"type": "imp", "row": 3, "x": 400}]}))
        z = sim.zombies[0]
        z.phase, z.phase_timer = "imp_thrown", 100
        sim.add_projectile(sim.plants[0], 3, 420, "cattail_spike", y=300,
                           vx=2, vy=0, motion="homing", target=z.id)
        result = sim.run()
        self.assertEqual(result["zombies"][0]["hp"], 70)
        self.assertEqual(result["events"].get("projectile_hit", 0), 0)

    def test_cattail_cannot_hit_rising_digger(self):
        sim = Simulator(parse_scenario({"max_frames": 1,
            "plants": [{"type": "cattail", "row": 3, "col": 1}],
            "zombies": [{"type": "digger", "row": 3, "x": 400}]}))
        z = sim.zombies[0]
        z.phase, z.phase_timer = "digger_rising", 100
        sim.add_projectile(sim.plants[0], 3, 440, "cattail_spike", y=300,
                           vx=2, vy=0, motion="homing", target=z.id)
        result = sim.run()
        self.assertEqual(result["zombies"][0]["hp"], 270)
        self.assertEqual(result["zombies"][0]["helmet_hp"], 100)
        self.assertEqual(result["events"].get("projectile_hit", 0), 0)

    def test_spikerock_two_pulses_bypass_door_and_is_not_chewed(self):
        sim = Simulator(parse_scenario({"max_frames": 70,
            "plants": [{"type": "spikerock", "row": 3, "col": 2}],
            "zombies": [{"type": "screen_door", "row": 3, "x": 100}]}))
        sim.zombies[0].speed = 0
        result = sim.run()
        self.assertEqual(result["events"].get("spikerock_pulse"), 2)
        self.assertEqual(result["zombies"][0]["hp"], 230)
        self.assertEqual(result["zombies"][0]["shield_hp"], 1100)
        self.assertEqual(result["plants"][0]["hp"], 450)

    def test_spikerock_survives_eight_giant_hits_and_dies_on_ninth(self):
        sim = Simulator(parse_scenario({"max_frames": 1,
            "plants": [{"type": "spikerock", "row": 3, "col": 2}],
            "zombies": [{"type": "gargantuar", "row": 3, "x": 110}]}))
        z = sim.zombies[0]
        from pvz_ize import extended_zombies
        for hit in range(1, 10):
            z.phase, z.phase_timer = "giant_smashing", 75
            extended_zombies.update(sim, z)
            self.assertEqual(sim.plants[0].hp, 450 - 50 * hit)

    def test_spikerock_pops_tire_and_loses_only_fifty_hp(self):
        result = self.run_layout([{"type": "spikerock", "row": 3, "col": 2}],
                                 [{"type": "zamboni", "row": 3, "x": 120}], max_frames=2)
        self.assertEqual(result["zombies"][0]["status"], "dead")
        self.assertEqual(result["plants"][0]["hp"], 400)

    def test_blover_fifty_frame_activation_removes_flying_balloon(self):
        result = self.run_layout([{"type": "blover", "row": 2, "col": 1}],
                                 [{"type": "balloon", "row": 3, "col": 7}], max_frames=60)
        self.assertEqual(result["winner"], "plants")
        self.assertEqual(result["frames"], 50)
        self.assertEqual(result["zombies"][0]["status"], "exited")
        self.assertEqual(result["plants"][0]["hp"], 0)

    def test_blover_leaves_popping_and_walking_balloon_alone(self):
        sim = Simulator(parse_scenario({"max_frames": 1,
            "plants": [{"type": "blover", "row": 2, "col": 1, "state_timer": 1}],
            "zombies": [{"id": name, "type": "balloon", "row": 3, "col": 7}
                        for name in ("flying", "popping", "walking")]}))
        sim.pop_balloon(sim.zombies[1], "test")
        sim.zombies[2].phase = "balloon_walking"
        result = sim.run()
        self.assertEqual([z["status"] for z in result["zombies"]], ["exited", "active", "active"])


if __name__ == "__main__":
    unittest.main()
