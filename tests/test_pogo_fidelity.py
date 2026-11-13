"""Pogo cycle contracts backed by the retained native static audit."""

import unittest

from pvz_ize import extended_zombies as ext, ground_special, movement
from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


PRESET = "P23|P4|P23,Z18|P4|P23,Z18|P4|P23,Z18|P4|P14,Z18"


class PogoTests(unittest.TestCase):
    def board(self, plants=(), **values):
        sim = Simulator(parse_scenario({"seed": 2026, "plants": list(plants),
            "zombies": [{"type": "pogo", "row": 3, "x": 100, **values}]}))
        return sim, sim.zombies[0], ext._state(sim, sim.zombies[0])

    def nut(self, kind="tallnut", **values):
        return {"type": kind, "row": 3, "col": 1, **values}

    def test_initial_counter_and_normalized_replay(self):
        sim, z, data = self.board()
        self.assertTrue(1 <= z.phase_timer <= 80)
        self.assertEqual(data["pogo_stage"], "bounce")
        self.assertEqual(data["pogo_velocity"], .45)
        replay = Simulator(parse_scenario(sim.scenario.to_dict()))
        self.assertEqual(replay.zombies[0].phase_timer, z.phase_timer)

    def test_bounce_high_forward_and_first_displacement_order(self):
        sim, z, data = self.board([self.nut("wallnut")], x=80)
        z.phase_timer = 1
        ext.update(sim, z)
        self.assertAlmostEqual(z.x, 79.55)
        self.assertEqual((data["pogo_stage"], z.phase_timer), ("high", 80))
        for _ in range(80):
            ext.update(sim, z)
        self.assertEqual((data["pogo_stage"], z.phase_timer), ("forward", 80))
        self.assertAlmostEqual(z.x, 79.55)  # New forward velocity starts next tick.
        self.assertEqual(data["pogo_velocity"], (79 - 40 + 60) / 80)
        ext.update(sim, z)
        self.assertAlmostEqual(z.x, 79.55 - 99 / 80)
        self.assertFalse(z.eating)

    def test_empty_cycle_resets_without_stopping(self):
        sim, z, data = self.board()
        z.phase_timer = 1
        ext.update(sim, z)
        self.assertEqual((data["pogo_stage"], z.phase_timer), ("bounce", 80))
        self.assertAlmostEqual(z.x, 99.55)

    def test_tallnut_break_is_only_at_forward_counter_70(self):
        for initial, breaks in ((72, False), (71, True), (70, False)):
            with self.subTest(counter=initial):
                sim, z, data = self.board([self.nut()])
                data.update(pogo_stage="forward", pogo_velocity=1)
                z.phase_timer = initial
                self.assertTrue(ext.update(sim, z))
                self.assertEqual(not z.tool, breaks)
                self.assertEqual(sim.plants[0].hp, 8000)
                self.assertAlmostEqual(z.x, 99)
                if breaks:
                    self.assertEqual(z.phase, "pogo_walking")
                    self.assertTrue(data["pogo_falling"])
                    self.assertAlmostEqual(data["altitude"], 48.375)

    def test_rechecks_current_target_not_original_or_shell(self):
        for plants, breaks in (([self.nut(), self.nut("pumpkin")], True),
                                ([self.nut(hp=0)], False),
                                ([self.nut("wallnut")], False)):
            sim, z, data = self.board(plants)
            data.update(pogo_stage="forward", pogo_velocity=1)
            z.phase_timer = 71
            ext.update(sim, z)
            self.assertEqual(not z.tool, breaks)

    def test_lone_pumpkin_vault_rect_uses_its_native_left_edge(self):
        for x, stage in ((70, "high"), (71, "bounce"), (80, "bounce")):
            sim, z, data = self.board([self.nut("pumpkin")], x=x)
            z.phase_timer = 1
            ext.update(sim, z)
            self.assertEqual(data["pogo_stage"], stage)

    def test_chill_slows_direct_motion_not_counter(self):
        sim, z, data = self.board(chilled=999)
        z.phase_timer = 80
        ext.update(sim, z)
        self.assertEqual(z.phase_timer, 79)
        self.assertAlmostEqual(z.x, 100 - .45 * .4)

    def test_animation_mode_also_uses_direct_velocity(self):
        sim = Simulator(parse_scenario({"movement_mode": "animation", "zombies": [
            {"type": "pogo", "row": 3, "x": 100, "velocity_parameter": .6}]}))
        ext.update(sim, sim.zombies[0])
        self.assertAlmostEqual(sim.zombies[0].x, 99.4)

    def test_explicit_speed_is_direct_while_holding_stick(self):
        for mode in ("mean", "animation"):
            initial = parse_scenario({"movement_mode": mode, "zombies": [
                {"type": "pogo", "row": 3, "x": 100, "speed": .1}]})
            sim = Simulator(initial)
            ext.update(sim, sim.zombies[0])
            self.assertAlmostEqual(sim.zombies[0].x, 99.9)
            replay = Simulator(parse_scenario(initial.to_dict()))
            ext.update(replay, replay.zombies[0])
            self.assertEqual(sim.zombies[0].x, replay.zombies[0].x)

    def test_explicit_walking_velocity_survives_tool_false_input(self):
        sim = Simulator(parse_scenario({"movement_mode": "animation", "zombies": [
            {"type": "pogo", "row": 3, "x": 100, "tool": False,
             "velocity_parameter": .6}]}))
        self.assertEqual(sim.zombies[0].velocity_parameter, .6)
        self.assertAlmostEqual(sim.zombies[0].speed, .6 * .47)

    def test_freeze_and_butter_pause_clock_and_motion(self):
        for effect in ("frozen", "buttered"):
            sim, z, data = self.board(**{effect: 100})
            timer = z.phase_timer
            for _ in range(20):
                sim.update_zombie(z)
            self.assertEqual((z.x, z.phase_timer), (100, timer))

    def test_who_hook_boundary_is_strict_float_position_after_walk(self):
        for x, breaks in ((-15, False), (-15.0001, True)):
            sim = Simulator(parse_scenario({"mode": "who_will_win", "zombies": [
                {"type": "pogo", "row": 3, "x": x}]}))
            z = sim.zombies[0]
            ext._state(sim, z).update(pogo_stage="high", pogo_velocity=0)
            z.phase_timer = 50
            ext.update(sim, z)
            self.assertEqual(not z.tool, breaks)

    def test_rectangles_and_walking_track_after_removal(self):
        sim, z, data = self.board()
        self.assertEqual(ground_special.mouth(z), (110, 140))
        self.assertIsNone(movement.track_name(z))
        ext.remove_tool(sim, z)
        self.assertEqual(ground_special.mouth(z), (120, 170))
        self.assertEqual(movement.track_name(z), "Zombie_pogo/anim_walk")
        self.assertTrue(movement.tracks()[movement.track_name(z)])

    def test_head_loss_breaks_stick(self):
        sim, z, data = self.board()
        sim.damage(z, 350, "test")
        self.assertTrue(z.headless)
        self.assertFalse(z.tool)
        self.assertEqual(z.phase, "pogo_walking")

    def test_held_pogo_does_not_bite_opposing_zombie(self):
        sim = Simulator(parse_scenario({"zombies": [
            {"type": "pogo", "row": 3, "x": 100, "hypnotized": True},
            {"type": "normal", "row": 3, "x": 150}]}))
        z, other = sim.zombies
        for _ in range(20):
            sim.update_zombie(z)
        self.assertFalse(z.eating)
        self.assertEqual(other.hp, 270)

    def test_landing_tick_can_bite_opposing_zombie(self):
        sim = Simulator(parse_scenario({"zombies": [
            {"type": "pogo", "row": 3, "x": 100, "tool": False, "hypnotized": True},
            {"type": "normal", "row": 3, "x": 140}]}))
        z, other = sim.zombies
        ext._state(sim, z).update(pogo_falling=True, altitude=.5)
        z.age = 3
        sim.update_zombie(z)
        self.assertEqual(other.hp, 266)
        self.assertFalse(ext._state(sim, z)["pogo_falling"])

    def test_breaking_tick_and_fall_do_not_chew(self):
        sim, z, data = self.board([self.nut()])
        z.phase_timer = 71
        data.update(pogo_stage="forward", pogo_velocity=1)
        sim.update_zombie(z)
        for _ in range(48):
            sim.update_zombie(z)
            self.assertEqual(sim.plants[0].hp, 8000)
        self.assertTrue(data["pogo_falling"])
        for _ in range(8):
            sim.update_zombie(z)
        self.assertFalse(data["pogo_falling"])
        self.assertLess(sim.plants[0].hp, 8000)

    def test_retained_preset_does_not_stall_chewing_mines(self):
        sim = Simulator(parse_scenario({"formation_code": PRESET, "seed": 2026}))
        result = sim.run()
        self.assertNotEqual(result["reason"], "max_frames_reached")
        self.assertFalse(any(z.tool and z.eating for z in sim.zombies))


if __name__ == "__main__":
    unittest.main()
