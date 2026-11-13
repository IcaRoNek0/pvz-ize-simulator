"""Combat contracts, independent of animation/pixel-equivalence assumptions."""

import unittest

from pvz_ize.catalog import PLANTS
from pvz_ize.engine import Projectile, Simulator, overlap
from pvz_ize.model import parse_scenario


def plant(name="peashooter", **values):
    return {"type": name, "row": 3, "col": 1, "cooldown": 1, **values}


def zombie(name="normal", **values):
    return {"type": name, "row": 3, "x": 500, "speed": 0.001, **values}


class CombatTests(unittest.TestCase):
    def test_bungee_grab_pauses_plant_until_released(self):
        sim, events = self.simulation([plant()], [zombie("bungee", x=40)])
        p, z = sim.plants[0], sim.zombies[0]
        z.phase, z.target = "bungee_grabbing", p.id
        p.shots = [{"due": 1, "direction": 1}]
        self.advance_plants(sim, 10)
        self.assertEqual(p.cooldown, 1)
        self.assertEqual(len(p.shots), 1)
        self.assertEqual(self.events(events, "projectile_fired"), [])
        z.status = "dead"
        self.advance_plants(sim, 1)
        self.assertEqual(len(self.events(events, "projectile_fired")), 1)

    def simulation(self, plants=(), zombies=()):
        events = []
        sim = Simulator(parse_scenario({"seed": 42, "plants": list(plants),
                                       "zombies": list(zombies)}), events.append)
        return sim, events

    def advance_plants(self, sim, count):
        # Freeze targets to isolate attack timers from movement and bite updates.
        for _ in range(count):
            sim.frame += 1
            for unit in sim.plants:
                sim.update_plant(unit)

    @staticmethod
    def events(events, kind):
        return [e for e in events if e["event"] == kind]

    def test_single_shooter_windups_and_projectile_kinds(self):
        cases = {"peashooter": (34, "pea"), "snow_pea": (34, "ice"),
                 "puff_shroom": (28, "puff"), "scaredy_shroom": (24, "spore")}
        for name, (delay, kind) in cases.items():
            with self.subTest(plant=name):
                sim, events = self.simulation([plant(name)], [zombie(x=200)])
                self.advance_plants(sim, delay)
                self.assertEqual(self.events(events, "projectile_fired"), [])
                self.advance_plants(sim, 1)
                shots = self.events(events, "projectile_fired")
                self.assertEqual([(e["frame"], e["kind"]) for e in shots],
                                 [(1 + delay, kind)])

    def test_repeater_has_two_shots_separated_by_25_frames(self):
        sim, events = self.simulation([plant("repeater", cooldown=26)], [zombie()])
        self.advance_plants(sim, 51)
        self.assertEqual([e["frame"] for e in self.events(events, "projectile_fired")],
                         [26, 51])

    def test_split_pea_has_two_back_shots_and_one_front_shot(self):
        sim, events = self.simulation([plant("split_pea", col=4, cooldown=26)],
                                     [zombie(id="left", x=100), zombie(id="right", x=600)])
        self.advance_plants(sim, 51)
        fired = self.events(events, "projectile_fired")
        self.assertEqual([(e["frame"], e["direction"]) for e in fired],
                         [(26, -1), (51, 1), (51, -1)])

    def test_split_pea_does_not_fire_front_without_front_target(self):
        sim, events = self.simulation([plant("split_pea", col=4)], [zombie(x=100)])
        self.advance_plants(sim, 26)
        self.assertEqual([e["direction"] for e in self.events(events, "projectile_fired")], [-1])

    def test_split_pea_rear_muzzle_can_hit_the_trailing_miner(self):
        sim, events = self.simulation([plant("split_pea", col=2)], [
            zombie("digger", id="leading", x=90),
            zombie("digger", id="trailing", x=10)])
        for z in sim.zombies:
            z.phase, z.direction, z.underground = "digger_walking", 1, False
        sim.fire(sim.plants[0], -1)
        shot = sim.projectiles[0]
        self.assertEqual(shot.x, sim.plants[0].x + 37 - 64)
        self.assertEqual(self.events(events, "projectile_fired")[0]["x"], shot.x)
        sim.update_projectile(shot)
        self.assertEqual(self.events(events, "projectile_hit")[0]["zombie"], "trailing")
        self.assertEqual(sim.zombies[0].helmet_hp, 100)
        self.assertEqual(sim.zombies[1].helmet_hp, 80)

    def test_split_pea_front_muzzle_uses_positive_head_offset(self):
        sim, _ = self.simulation([plant("split_pea")])
        sim.fire(sim.plants[0], 1)
        self.assertEqual(sim.projectiles[0].x, sim.plants[0].x + 37 + 24)

    def test_animation_walk_resamples_speed_after_chewing(self):
        events = []
        sim = Simulator(parse_scenario({"movement_mode": "animation",
            "plants": [plant("wallnut")], "zombies": [zombie(x=40, speed=.143)]}), events.append)
        z = sim.zombies[0]
        z.eating, z.age = True, 4
        sim.plants[0].hp = 0
        sim.chew(z)
        sim.move(z)
        self.assertFalse(z.eating)
        changed = self.events(events, "walk_segment_changed")
        self.assertEqual(len(changed), 1)
        self.assertTrue(.23 <= changed[0]["velocity_parameter"] <= .37)

    def test_reported_two_miners_split_pea_line_loses_to_bucket(self):
        sim, events = self.simulation([
            plant(kind, col=col, cooldown=cd) for col, kind, cd in [
                (1, "repeater", 18), (2, "split_pea", 72), (3, "fume_shroom", 74),
                (4, "squash", 0), (5, "spikeweed", 0), (6, "wallnut", 0)]], [
            {"type": "buckethead", "row": 3, "col": 7},
            {"type": "digger", "row": 3, "col": 2, "underground": True},
            {"type": "digger", "row": 3, "col": 7, "underground": True}])
        result = sim.run()
        self.assertEqual(result["winner"], "zombies")
        self.assertEqual(sim.plants[2].hp, 0)
        self.assertTrue(all(z.status == "dead" for z in sim.zombies[1:]))
        self.assertTrue(any(e["event"] == "plant_died" and e["plant"] == "p3"
                            and e["source"] in {"z2", "z3"} for e in events))

    def test_threepeater_fires_all_valid_rows_when_one_has_target(self):
        for row, rows in [(1, [1, 2]), (3, [2, 3, 4]), (5, [4, 5])]:
            with self.subTest(row=row):
                sim, events = self.simulation([plant("threepeater", row=row)],
                                             [zombie(row=row)])
                self.advance_plants(sim, 35)
                self.assertEqual([e["row"] for e in self.events(events, "projectile_fired")], rows)

    def test_empty_lane_still_advances_and_resets_attack_cycle(self):
        sim, events = self.simulation([plant()], [zombie(row=1)])
        self.advance_plants(sim, 1)
        self.assertTrue(136 <= sim.plants[0].cooldown <= 150)
        self.assertEqual(self.events(events, "attack_started"), [])

    def test_pending_shot_is_cancelled_when_plant_dies(self):
        sim, events = self.simulation([plant()], [zombie()])
        self.advance_plants(sim, 1)
        sim.destroy_plant(sim.plants[0], "test")
        self.advance_plants(sim, 40)
        self.assertEqual(self.events(events, "projectile_fired"), [])

    def test_puff_does_not_target_outside_short_range(self):
        sim, events = self.simulation([plant("puff_shroom")], [zombie(x=400)])
        self.advance_plants(sim, 35)
        self.assertEqual(self.events(events, "attack_started"), [])

    def test_scaredy_nearby_adjacent_lane_suppresses_shooting(self):
        sim, events = self.simulation([plant("scaredy_shroom", col=4)],
                                     [zombie(id="near", row=2, x=300), zombie(id="far", x=600)])
        self.advance_plants(sim, 50)
        self.assertEqual(self.events(events, "projectile_fired"), [])
        self.assertGreater(sim.plants[0].cooldown, 0)

    def test_fume_windup_and_same_row_multi_target_shield_bypass(self):
        sim, events = self.simulation([plant("fume_shroom")],
                                     [zombie("screen_door", id="a", x=200),
                                      zombie(id="b", x=300), zombie(id="far", x=500),
                                      zombie(id="other_row", row=2, x=200)])
        self.advance_plants(sim, 49)
        self.assertTrue(all(z.hp == 270 for z in sim.zombies))
        self.advance_plants(sim, 1)
        self.assertEqual([z.hp for z in sim.zombies], [250, 250, 270, 270])
        self.assertEqual(sim.zombies[0].shield_hp, 1080)
        self.assertEqual([e["frame"] for e in self.events(events, "fume")], [50])
        self.assertEqual(sim.projectiles, [])

    def test_fume_strict_range_boundary_does_not_damage(self):
        sim, _ = self.simulation([plant("fume_shroom")], [zombie(x=404)])
        sim.fire(sim.plants[0], 1)  # Left edge 440 touches the range's right edge.
        self.assertEqual(sim.zombies[0].hp, 270)

    def test_projectile_speed_and_direction(self):
        sim, _ = self.simulation()
        for direction in (-1, 1):
            q = Projectile("q", "p", 3, 300, "pea", direction)
            sim.update_projectile(q)
            self.assertAlmostEqual(q.x, 300 + 3.33 * direction)
            self.assertEqual(q.age, 1)

    def test_puff_projectile_expires_at_age_75(self):
        sim, _ = self.simulation()
        q = Projectile("q", "p", 3, 200, "puff", age=73)
        sim.update_projectile(q)
        self.assertTrue(q.active)
        sim.update_projectile(q)
        self.assertFalse(q.active)

    def test_projectile_hits_one_target_in_its_own_row(self):
        sim, _ = self.simulation(zombies=[zombie(id="a", x=200), zombie(id="b", x=205),
                                          zombie(id="other", row=2, x=200)])
        q = Projectile("q", "p", 3, 200, "pea")
        sim.update_projectile(q)
        self.assertEqual([z.hp for z in sim.zombies], [250, 270, 270])
        self.assertFalse(q.active)

    def test_forward_shot_hits_door_but_reverse_shot_bypasses_it(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                sim, _ = self.simulation(zombies=[zombie("screen_door", x=200)])
                sim.update_projectile(Projectile("q", "p", 3, 205, "pea", direction))
                self.assertEqual(sim.zombies[0].hp, 250 if direction < 0 else 270)
                self.assertEqual(sim.zombies[0].shield_hp, 1100 if direction < 0 else 1080)

    def test_ice_shot_chills_unshielded_target(self):
        sim, _ = self.simulation(zombies=[zombie(x=200)])
        sim.update_projectile(Projectile("q", "p", 3, 200, "ice"))
        self.assertEqual((sim.zombies[0].hp, sim.zombies[0].chilled), (250, 1000))

    def test_ice_shot_blocked_by_door_does_not_chill_body(self):
        sim, _ = self.simulation(zombies=[zombie("screen_door", x=200)])
        sim.update_projectile(Projectile("q", "p", 3, 200, "ice"))
        self.assertEqual(sim.zombies[0].chilled, 0)

    def test_torchwood_converts_ice_only_once_per_torch(self):
        sim, events = self.simulation([plant("torchwood")])
        q = Projectile("q", "p", 3, 75, "ice")
        sim.projectiles.append(q)
        self.advance_plants(sim, 2)
        self.assertEqual(q.kind, "pea")
        self.assertEqual(len(self.events(events, "torch")), 1)

    def test_second_torchwood_converts_thawed_pea_to_fire(self):
        sim, _ = self.simulation([plant("torchwood", id="a"),
                                  plant("torchwood", id="b", col=2)])
        q = Projectile("q", "p", 3, 75, "ice")
        sim.projectiles.append(q)
        self.advance_plants(sim, 1)
        q.x += 80
        self.advance_plants(sim, 1)
        self.assertEqual(q.kind, "fire")

    def test_fireball_clears_cold_but_door_prevents_splash(self):
        sim, _ = self.simulation(zombies=[zombie("screen_door", x=200, chilled=100)])
        sim.update_projectile(Projectile("q", "p", 3, 206, "fire"))
        z = sim.zombies[0]
        self.assertEqual((z.hp, z.shield_hp, z.chilled), (270, 1060, 0))

    def test_fireball_splash_is_less_than_primary_and_same_lane_only(self):
        sim, _ = self.simulation(zombies=[zombie(id="primary", x=200),
                                          zombie(id="splash", x=250),
                                          zombie(id="other", row=2, x=250)])
        sim.update_projectile(Projectile("q", "p", 3, 206, "fire"))
        self.assertEqual([z.hp for z in sim.zombies], [230, 257, 270])

    def test_spikeweed_first_hit_delay_and_repeated_cycle(self):
        sim, events = self.simulation([plant("spikeweed")], [zombie(x=0)])
        self.advance_plants(sim, 25)
        self.assertEqual(sim.zombies[0].hp, 270)
        self.advance_plants(sim, 1)
        self.assertEqual(sim.zombies[0].hp, 250)
        self.advance_plants(sim, 101)
        self.assertEqual([e["frame"] for e in self.events(events, "damage")], [26, 127])

    def test_spikeweed_strict_boundary_does_not_damage(self):
        sim, _ = self.simulation([plant("spikeweed")], [zombie(x=54)])
        self.advance_plants(sim, 30)  # Zombie left edge 90 == attack right edge.
        self.assertEqual(sim.zombies[0].hp, 270)

    def test_potato_is_armed_immediately_and_explodes_as_same_row_aoe(self):
        sim, events = self.simulation([plant("potato_mine")],
                                     [zombie(id="trigger", x=50), zombie(id="near", x=80),
                                      zombie(id="other", row=2, x=50), zombie(id="far", x=200)])
        self.advance_plants(sim, 1)
        self.assertEqual([z.status for z in sim.zombies], ["dead", "dead", "active", "active"])
        self.assertEqual(sim.plants[0].hp, 0)
        self.assertEqual([e["frame"] for e in self.events(events, "explosion")], [1])

    def test_headless_zombie_does_not_trigger_potato(self):
        sim, _ = self.simulation([plant("potato_mine")], [zombie(x=50, headless=True)])
        self.advance_plants(sim, 2)
        self.assertEqual(sim.plants[0].hp, 300)
        self.assertEqual(sim.zombies[0].hp, 270)

    def test_potato_post_vault_trigger_rect_is_shifted_40_pixels(self):
        for x, triggered in ((-10, False), (2, True)):
            with self.subTest(x=x):
                sim, _ = self.simulation([plant("potato_mine")],
                                         [zombie("pole_vaulting", x=x, tool=False)])
                self.assertEqual(sim.potato_triggered(sim.plants[0]), triggered)
                sim.special(sim.plants[0])
                self.assertEqual(sim.plants[0].hp == 0, triggered)

    def test_potato_pole_shift_persists_for_later_candidates(self):
        pole = zombie("pole_vaulting", x=200, tool=False)
        normal = zombie(x=-10)
        for units, triggered in (([pole, normal], False), ([normal, pole], True)):
            sim, _ = self.simulation([plant("potato_mine")], units)
            self.assertEqual(sim.potato_triggered(sim.plants[0]), triggered)

    def test_potato_ignores_poles_excluded_before_rect_mutation(self):
        for values in ({"headless": True}, {"hypnotized": True}, {"row": 2}, {"tool": True}):
            sim, _ = self.simulation([plant("potato_mine")],
                                     [zombie("pole_vaulting", x=200, **({"tool": False} | values)),
                                      zombie(x=-10)])
            self.assertTrue(sim.potato_triggered(sim.plants[0]), values)

    def test_native_overlap_handles_negative_potato_rect_width(self):
        self.assertEqual(overlap(120, 95, 68, 110), -10)
        self.assertEqual(overlap(68, 110, 120, 95), -10)
        self.assertEqual(overlap(120, 95, 100, 142), -25)

    def test_potato_multiple_poles_can_suppress_later_trigger(self):
        poles = [zombie("pole_vaulting", x=200, tool=False) for _ in range(2)]
        sim, _ = self.simulation([plant("potato_mine")], [*poles, zombie(x=40)])
        self.assertFalse(sim.potato_triggered(sim.plants[0]))
        sim.zombies[-1].eating = True
        # Rect [120,95] versus zombie [76,118] gives native gap -2,
        # within the extra 30 px eating tolerance despite negative width.
        self.assertTrue(sim.potato_triggered(sim.plants[0]))

    def test_potato_eating_extra_range_applies_after_pole_shift(self):
        sim, _ = self.simulation([plant("potato_mine")],
                                 [zombie("pole_vaulting", x=-10, tool=False)])
        sim.zombies[0].eating = True
        self.assertTrue(sim.potato_triggered(sim.plants[0]))

    def test_pogo_with_pole_does_not_trigger_but_can_take_blast_damage(self):
        sim, _ = self.simulation([plant("potato_mine")], [zombie("pogo", x=50)])
        sim.special(sim.plants[0])
        self.assertEqual(sim.plants[0].hp, 300)
        sim.zombies[0].tool = False
        sim.special(sim.plants[0])
        self.assertEqual(sim.zombies[0].hp, 0)
        sim, _ = self.simulation([plant("potato_mine")],
                                 [zombie("pogo", x=50), zombie(x=50)])
        sim.special(sim.plants[0])
        self.assertEqual([z.hp for z in sim.zombies], [0, 0])

    def test_magnet_removes_supported_metal_immediately(self):
        for name, layer in [("buckethead", "helmet_hp"), ("football", "helmet_hp"),
                            ("screen_door", "shield_hp")]:
            with self.subTest(zombie=name):
                sim, events = self.simulation([plant("magnet_shroom")], [zombie(name, x=200)])
                self.advance_plants(sim, 1)
                self.assertEqual(getattr(sim.zombies[0], layer), 0)
                self.assertEqual(sim.zombies[0].hp, 270)
                self.assertEqual(sim.plants[0].state_timer, 1500)
                self.assertEqual(len(self.events(events, "magnet")), 1)

    def test_magnet_does_not_remove_cone_or_out_of_range_armor(self):
        for name, values in [("conehead", {"x": 100}),
                             ("buckethead", {"x": 700}),
                             ("buckethead", {"x": 100, "row": 1})]:
            with self.subTest(zombie=name, values=values):
                sim, events = self.simulation([plant("magnet_shroom", row=5)],
                                             [zombie(name, **{"row": 5, **values})])
                before = sim.zombies[0].helmet_hp
                self.advance_plants(sim, 1)
                self.assertEqual(sim.zombies[0].helmet_hp, before)
                self.assertEqual(self.events(events, "magnet"), [])

    def test_magnet_recharges_for_1500_frames(self):
        sim, events = self.simulation([plant("magnet_shroom")],
                                     [zombie("buckethead", id="a", x=150),
                                      zombie("buckethead", id="b", x=200)])
        self.advance_plants(sim, 1500)
        self.assertEqual(len(self.events(events, "magnet")), 1)
        self.advance_plants(sim, 1)
        self.assertEqual([e["frame"] for e in self.events(events, "magnet")], [1, 1501])

    def test_chomper_waits_70_frames_then_swallows_armored_target(self):
        sim, events = self.simulation([plant("chomper")], [zombie("buckethead", x=80)])
        self.advance_plants(sim, 70)
        self.assertEqual(sim.zombies[0].status, "active")
        self.advance_plants(sim, 1)
        self.assertEqual(sim.zombies[0].status, "dead")
        self.assertEqual(sim.plants[0].state, "digesting")
        self.assertEqual(sim.plants[0].state_timer, 4000)
        self.assertEqual([e["frame"] for e in self.events(events, "swallow")], [71])

    def test_chomper_rechecks_target_at_bite_time(self):
        sim, events = self.simulation([plant("chomper")], [zombie(x=80)])
        self.advance_plants(sim, 1)
        sim.zombies[0].x = 500
        self.advance_plants(sim, 70)
        self.assertEqual(sim.zombies[0].status, "active")
        self.assertEqual(self.events(events, "swallow"), [])

    def test_squash_impacts_after_180_frames_and_can_damage_multiple_targets(self):
        sim, events = self.simulation([plant("squash")],
                                     [zombie("buckethead", id="a", x=80),
                                      zombie(id="b", x=85), zombie(id="far", x=400)])
        self.advance_plants(sim, 180)
        self.assertEqual(sim.zombies[0].status, "active")
        self.advance_plants(sim, 1)
        self.assertEqual([z.status for z in sim.zombies], ["dead", "dead", "active"])
        self.assertEqual([e["frame"] for e in self.events(events, "squash_impact")], [181])

    def test_passive_plant_types_have_health_but_no_offense(self):
        for name in ("sunflower", "wallnut", "tallnut", "umbrella_leaf", "torchwood"):
            with self.subTest(plant=name):
                sim, events = self.simulation([plant(name)], [zombie()])
                self.advance_plants(sim, 200)
                self.assertEqual(sim.plants[0].hp, PLANTS[name].hp)
                self.assertEqual(self.events(events, "damage"), [])
                self.assertEqual(self.events(events, "projectile_fired"), [])


if __name__ == "__main__":
    unittest.main()
