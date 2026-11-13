"""Social-zombie state contracts, without requiring the graphics runtime."""

from random import Random
from types import SimpleNamespace
import unittest

from pvz_ize import social_special as social


def unit(name="dancing", **values):
    data = {"id": "z", "type": name, "row": 3, "x": 500.0, "hp": 500,
            "status": "active", "headless": False, "eating": False,
            "phase": "initial", "phase_timer": 0, "direction": -1,
            "target_col": None, "target": None, "tool": True, "leader": None,
            "buttered": 0, "chilled": 0, "speed": 0.2, "age": 0}
    return SimpleNamespace(**{**data, **values})


def plant(name="sunflower", **values):
    data = {"id": "p", "type": name, "row": 3, "col": 3,
            "hp": 300, "state": "ready", "shots": []}
    data.update(values)
    data["x"] = 40 + 80 * (data["col"] - 1)
    return SimpleNamespace(**data)


class FakeSimulator:
    def __init__(self, zombies=(), plants=()):
        self.zombies, self.plants = list(zombies), list(plants)
        self.brains = [SimpleNamespace(row=3, hp=70)]
        self.rng, self.frame, self.events = Random(42), 0, []
        self.chewed = []
        self.ladders = set()

    def emit(self, event, **data):
        self.events.append({"frame": self.frame, "event": event, **data})

    def active(self, row=None, headed=False):
        return [z for z in self.zombies if z.status == "active" and z.hp > 0
                and (row is None or row == z.row) and (not headed or not z.headless)]

    def spawn_zombie(self, name, row, x, leader=None):
        z = unit(name, id=f"child{len(self.zombies)}", row=row, x=x,
                 leader=leader, hp=270)
        self.zombies.append(z)
        social.initialize(self, z)
        return z

    def chew(self, z):
        self.chewed.append(z.id)

    def destroy_plant(self, p, source):
        p.hp = 0
        p.shots.clear()
        self.emit("plant_died", plant=p.id, source=source)

    def resolve_umbrella(self, row, col):
        return next((p for p in self.plants if p.hp > 0 and p.type == "umbrella_leaf"
                     and abs(p.row - row) <= 1 and abs(p.col - col) <= 1), None)

    def advance(self, count=1):
        for _ in range(count):
            self.frame += 1
            for z in tuple(self.active()):
                consumed = social.update(self, z)
                if not consumed:
                    if not z.eating:
                        z.x += z.direction * z.speed
                    self.chew(z)


class SocialSpecialTests(unittest.TestCase):
    def test_unknown_unit_leaves_normal_update_to_caller(self):
        z = unit("normal")
        self.assertFalse(social.update(FakeSimulator([z]), z))

    def test_explicit_phase_is_not_reinitialized(self):
        z = unit(phase="dancer_hold", phase_timer=20)
        social.initialize(FakeSimulator([z]), z)
        self.assertEqual((z.phase, z.phase_timer), ("dancer_hold", 20))

    def test_dancer_initial_timer_and_first_frame_moonwalk(self):
        z = unit()
        sim = FakeSimulator([z])
        social.initialize(sim, z)
        self.assertTrue(300 <= z.phase_timer <= 311)
        sim.advance()
        self.assertAlmostEqual(z.x, 499.5)
        self.assertEqual(sim.chewed, [])

    def test_chilled_moonwalk_is_half_speed(self):
        z = unit(chilled=100)
        sim = FakeSimulator([z])
        sim.advance()
        self.assertAlmostEqual(z.x, 499.75)

    def test_moonwalk_contact_ends_initial_stage_without_biting_plant(self):
        z = unit(x=170)
        p = plant()  # x=200, bite interval [220,240] intersects plant [210,270].
        sim = FakeSimulator([z], [p])
        sim.advance()
        self.assertEqual(z.phase, "dancer_summoning")
        self.assertEqual((z.x, p.hp), (170, 300))

    def test_moonwalk_checks_collision_after_motion_too(self):
        z = unit(x=210)
        p = plant()  # Mouth moves from [260,280] to [259,279], still partial.
        sim = FakeSimulator([z], [p])
        sim.advance(21)
        self.assertEqual(z.phase, "dancer_summoning")
        self.assertEqual(p.hp, 300)

    def test_moonwalk_does_not_stop_for_ground_spikes(self):
        z = unit(x=170)
        sim = FakeSimulator([z], [plant("spikeweed")])
        sim.advance()
        self.assertEqual(z.phase, "dancer_moonwalk")

    def test_dancer_climbing_takes_priority_and_restores_initial_stage_timer(self):
        z = unit(x=170, phase="dancer_moonwalk", phase_timer=123)
        p = plant("wallnut")
        sim = FakeSimulator([z], [p])
        sim.ladders.add((p.row, p.col))
        sim.advance()
        self.assertEqual(z.phase, "ladder_climbing")
        self.assertEqual(z.phase_timer, 120)
        sim.advance(119)
        self.assertEqual(z.phase, "ladder_climbing")
        sim.advance()
        self.assertEqual((z.phase, z.phase_timer), ("dancer_moonwalk", 123))
        self.assertLess(z.x, p.x)

    def test_backup_climbing_is_not_overwritten_by_shared_dance_phase(self):
        z = unit("backup_dancer", x=170)
        p = plant("wallnut")
        sim = FakeSimulator([z], [p])
        sim.ladders.add((p.row, p.col))
        sim.frame = 240  # A stationary dance beat would otherwise consume it.
        sim.advance()
        self.assertEqual(z.phase, "ladder_climbing")
        sim.advance(120)
        self.assertEqual(z.phase, "dancer_walking")

    def test_dancer_stops_before_summoning(self):
        z = unit(phase="dancer_moonwalk", phase_timer=1)
        sim = FakeSimulator([z])
        sim.advance()
        self.assertEqual(z.phase, "dancer_summoning")
        self.assertEqual(z.phase_timer, social.DANCER_POINT_FRAMES)
        self.assertEqual(len(sim.zombies), 1)
        x = z.x
        sim.advance(social.DANCER_POINT_FRAMES - 1)
        self.assertEqual(z.x, x)
        self.assertEqual(len(sim.zombies), 1)
        sim.advance()
        self.assertEqual(len(sim.zombies), 5)
        self.assertEqual((z.phase, z.phase_timer), ("dancer_hold", 200))

    def test_four_formation_slots_have_source_offsets(self):
        z = unit(phase="dancer_summoning", phase_timer=1)
        sim = FakeSimulator([z])
        sim.advance()
        self.assertEqual([(b.row, b.x) for b in sim.zombies[1:]],
                         [(2, 500), (4, 500), (3, 400), (3, 600)])
        self.assertTrue(all(b.leader == z.id for b in sim.zombies[1:]))

    def test_explicit_initial_follower_occupies_slot_instead_of_being_duplicated(self):
        leader = unit(phase="dancer_summoning", phase_timer=1)
        child = unit("backup_dancer", id="old_child", row=2, leader=leader.id)
        sim = FakeSimulator([leader, child])
        sim.advance()
        self.assertEqual(len(sim.zombies), 5)
        self.assertEqual(len([z for z in sim.zombies if z.row == 2]), 1)

    def test_boundary_row_has_only_three_valid_backup_slots(self):
        for row, rows in [(1, [2, 1, 1]), (5, [4, 5, 5])]:
            with self.subTest(row=row):
                z = unit(row=row, phase="dancer_summoning", phase_timer=1)
                sim = FakeSimulator([z])
                sim.advance()
                self.assertEqual([b.row for b in sim.zombies[1:]], rows)

    def test_newborn_backups_do_not_update_in_birth_frame(self):
        z = unit(phase="dancer_summoning", phase_timer=1)
        sim = FakeSimulator([z])
        sim.advance()
        child = sim.zombies[1]
        self.assertEqual(child.phase_timer, 150)
        self.assertTrue(social.update(sim, child))
        self.assertEqual(child.phase_timer, 150)
        sim.advance()
        self.assertEqual(child.phase_timer, 149)

    def test_backup_rising_finishes_after_150_updates(self):
        z = unit("backup_dancer", phase="backup_rising", phase_timer=150)
        sim = FakeSimulator([z])
        sim.advance(149)
        self.assertEqual(z.phase, "backup_rising")
        sim.advance()
        self.assertEqual(z.phase, "dancer_walking")
        self.assertLess(z.x, 500)

    def test_backup_rising_is_only_hit_by_off_ground_or_all(self):
        z = unit("backup_dancer", phase="backup_rising")
        self.assertFalse(social.targetable(z))
        self.assertFalse(social.targetable(z, "underground"))
        self.assertTrue(social.targetable(z, "off_ground"))
        self.assertTrue(social.targetable(z, "all"))

    def test_dance_uses_460_frame_beat_with_240_frame_walk(self):
        z = unit("backup_dancer")
        sim = FakeSimulator([z])
        sim.advance(239)
        x = z.x
        sim.advance(220)
        self.assertEqual(z.x, x)
        sim.advance()
        self.assertLess(z.x, x)

    def test_stationary_dance_still_checks_chewing(self):
        z = unit("backup_dancer")
        sim = FakeSimulator([z])
        sim.frame = 240
        self.assertTrue(social.update(sim, z))
        self.assertEqual(sim.chewed, [z.id])

    def test_eating_backup_does_not_get_locked_out_by_dance_beat(self):
        z = unit("backup_dancer", eating=True)
        sim = FakeSimulator([z])
        sim.frame = 240
        self.assertFalse(social.update(sim, z))

    def test_leader_death_does_not_freeze_orphaned_backup(self):
        leader = unit(status="dead")
        child = unit("backup_dancer", id="child", leader=leader.id)
        sim = FakeSimulator([leader, child])
        sim.advance()
        self.assertLess(child.x, 500)
        self.assertIsNone(child.leader)

    def test_leader_head_loss_cancels_pending_summon(self):
        leader = unit(headless=True, phase="dancer_summoning", phase_timer=1)
        sim = FakeSimulator([leader])
        sim.advance(20)
        self.assertEqual(len(sim.zombies), 1)
        self.assertLess(leader.x, 500)

    def test_eating_member_stops_linked_formation_movement(self):
        leader = unit(phase="dancer_walking")
        child = unit("backup_dancer", id="child", leader=leader.id, eating=True)
        sim = FakeSimulator([leader, child])
        sim.advance()
        self.assertEqual(leader.x, 500)

    def test_dancer_replaces_only_missing_slots_after_delay_and_beat(self):
        leader = unit(phase="dancer_summoning", phase_timer=1)
        sim = FakeSimulator([leader])
        sim.advance()
        old = sim.zombies[1:]
        old[0].status = "dead"
        leader.phase, leader.phase_timer = "dancer_walking", 0
        sim.advance(100)
        self.assertEqual(len(sim.zombies), 5)
        sim.advance(200)
        self.assertEqual(len(sim.zombies), 6)
        self.assertEqual(len([z for z in sim.active() if z.type == "backup_dancer"]), 4)
        self.assertTrue(all(z in sim.zombies for z in old[1:]))

    def test_bungee_col_uses_grid_origin_without_normal_zombie_offset(self):
        z = unit("bungee", target_col=3, x=170)
        sim = FakeSimulator([z])
        social.initialize(sim, z)
        self.assertEqual(z.x, 200)
        self.assertTrue(375 <= z.phase_timer <= 394)

    def test_bungee_can_infer_target_col_from_x(self):
        z = unit("bungee", x=280)
        social.initialize(FakeSimulator([z]), z)
        self.assertEqual((z.target_col, z.x), (4, 280))

    def test_explicit_bungee_phase_can_infer_missing_target_col(self):
        z = unit("bungee", x=280, phase="bungee_waiting", phase_timer=10)
        social.initialize(FakeSimulator([z]), z)
        self.assertEqual((z.target_col, z.x, z.phase_timer), (4, 280, 10))

    def test_bungee_only_targetable_while_waiting_or_grabbing(self):
        z = unit("bungee")
        for phase in ("initial", "bungee_diving", "bungee_rising", "bungee_exited"):
            z.phase = phase
            for attack in ("ground", "off_ground", "underground", "all"):
                with self.subTest(phase=phase, attack=attack):
                    self.assertFalse(social.targetable(z, attack))
        for phase in ("bungee_waiting", "bungee_grabbing"):
            z.phase = phase
            self.assertTrue(social.targetable(z))
            self.assertTrue(social.targetable(z, "all"))

    def test_bungee_lands_then_waits_300_frames_before_grab(self):
        z = unit("bungee", target_col=3, phase="bungee_diving", phase_timer=1)
        p = plant()
        sim = FakeSimulator([z], [p])
        sim.advance()
        self.assertEqual((z.phase, z.phase_timer), ("bungee_waiting", 300))
        sim.advance(299)
        self.assertEqual(p.hp, 300)
        self.assertEqual(z.phase, "bungee_waiting")
        sim.advance()
        self.assertEqual((z.phase, z.target), ("bungee_grabbing", p.id))

    def test_bungee_steals_only_targeted_cell_and_exits(self):
        z = unit("bungee", target_col=3, phase="bungee_waiting", phase_timer=1)
        target, neighbor = plant(), plant(id="neighbor", col=4)
        sim = FakeSimulator([z], [target, neighbor])
        sim.advance(1 + social.BUNGEE_GRAB_FRAMES)
        self.assertEqual((target.hp, neighbor.hp), (0, 300))
        self.assertEqual(z.phase, "bungee_rising")
        sim.advance(75)
        self.assertEqual(z.status, "exited")
        self.assertEqual(sim.brains[0].hp, 70)
        self.assertEqual(sim.chewed, [])

    def test_umbrella_blocks_bungee_without_destroying_protected_plant(self):
        for row, col in [(3, 3), (2, 2), (4, 4)]:
            with self.subTest(umbrella=(row, col)):
                z = unit("bungee", target_col=3, phase="bungee_diving", phase_timer=1)
                p = plant()
                umbrella = plant("umbrella_leaf", id="umbrella", row=row, col=col)
                sim = FakeSimulator([z], [p, umbrella])
                sim.advance(76)
                self.assertEqual((p.hp, umbrella.hp, z.status), (300, 300, "exited"))
                self.assertTrue(any(e["event"] == "umbrella_block" for e in sim.events))

    def test_dead_umbrella_does_not_block_bungee(self):
        z = unit("bungee", target_col=3, phase="bungee_diving", phase_timer=1)
        sim = FakeSimulator([z], [plant("umbrella_leaf", hp=0)])
        sim.advance()
        self.assertEqual(z.phase, "bungee_waiting")

    def test_empty_cell_bungee_does_not_attack_brain_or_stall_forever(self):
        z = unit("bungee", target_col=1)
        sim = FakeSimulator([z])
        sim.advance(1000)
        self.assertEqual(z.status, "exited")
        self.assertEqual(sim.brains[0].hp, 70)
        self.assertFalse(any(e["event"] == "plant_stolen" for e in sim.events))

    def test_bungee_cannot_steal_airborne_squash(self):
        z = unit("bungee", target_col=3, phase="bungee_waiting", phase_timer=1)
        p = plant("squash", state="airborne")
        sim = FakeSimulator([z], [p])
        sim.advance(1 + social.BUNGEE_GRAB_FRAMES)
        self.assertEqual(p.hp, 300)

    def test_target_destroyed_during_grab_is_not_stolen_twice(self):
        z = unit("bungee", target_col=3, phase="bungee_waiting", phase_timer=1)
        p = plant()
        sim = FakeSimulator([z], [p])
        sim.advance()
        p.hp = 0
        sim.advance(social.BUNGEE_GRAB_FRAMES)
        self.assertFalse(any(e["event"] == "plant_stolen" for e in sim.events))
        self.assertEqual(z.phase, "bungee_rising")

    def test_headless_bungee_abandons_theft_and_exits(self):
        z = unit("bungee", target_col=3, headless=True,
                 phase="bungee_waiting", phase_timer=300)
        p = plant()
        sim = FakeSimulator([z], [p])
        sim.advance(75)
        self.assertEqual((p.hp, z.status), (300, "exited"))

    def test_dead_social_unit_does_not_act(self):
        z = unit(status="dead", phase="dancer_summoning", phase_timer=1)
        sim = FakeSimulator([z])
        self.assertTrue(social.update(sim, z))
        self.assertEqual(len(sim.zombies), 1)


if __name__ == "__main__":
    unittest.main()
