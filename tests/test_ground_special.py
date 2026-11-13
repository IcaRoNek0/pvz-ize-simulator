"""Standalone state-machine checks, independent of CLI/catalog integration."""

from types import SimpleNamespace
import unittest

from pvz_ize import ground_special as ground


def unit(type_="normal", **values):
    defaults = dict(id="z1", type=type_, row=3, x=200.0, hp=500,
                    helmet_hp=0, shield_hp=500 if type_ == "ladder" else 0,
                    speed={"pole_vaulting": .32, "ladder": .38, "digger": .67}.get(type_, .143),
                    age=0, chilled=0, buttered=0, headless=False, eating=False,
                    status="active", phase="initial", phase_timer=0, direction=-1,
                    target_col=None, target=None, tool=True, leader=None)
    defaults.update(values)
    return SimpleNamespace(**defaults)


def plant(type_="wallnut", col=2, **values):
    defaults = dict(id="p1", type=type_, row=3, col=col,
                    x=40 + 80 * (col - 1), hp=4000, state="ready")
    defaults.update(values)
    return SimpleNamespace(**defaults)


class Board:
    def __init__(self, plants=(), brains=()):
        self.plants, self.brains = list(plants), list(brains)
        self.ladders, self.events = set(), []
        self.frame = 0

    def emit(self, name, **values):
        self.events.append((name, values))


class PoleTests(unittest.TestCase):
    def test_running_moves_without_chewing_and_can_jump_once(self):
        sim, z = Board([plant()]), unit("pole_vaulting", x=198)
        self.assertTrue(ground.update(sim, z))
        self.assertEqual(z.phase, "pole_jumping")
        self.assertFalse(z.tool)
        self.assertFalse(ground.targetable(z))
        for _ in range(ground.POLE_JUMP_FRAMES - 1):
            self.assertTrue(ground.update(sim, z))
        self.assertFalse(ground.update(sim, z))
        self.assertEqual(z.phase, "pole_walking")
        self.assertAlmostEqual(z.x, 198 - 180 * (-2 / ground.POLE_JUMP_DURATION) - 150)
        self.assertEqual(z.speed, ground.WALK_SPEED)
        self.assertTrue(ground.targetable(z))
        self.assertFalse(ground.update(sim, z))
        self.assertEqual(sim.plants[0].hp, 4000)

    def test_jump_animation_uses_extracted_43_frames_at_24fps(self):
        self.assertEqual(ground.POLE_JUMP_FRAMES, 180)

    def test_tallnut_blocks_landing_and_becomes_edible(self):
        sim, z = Board([plant("tallnut")]), unit("pole_vaulting", x=198)
        ground.update(sim, z)
        for _ in range(ground.POLE_JUMP_FRAMES):
            ground.update(sim, z)
        self.assertEqual(z.phase, "pole_walking")
        self.assertAlmostEqual(z.x, 120 - ground.WALK_SPEED)
        self.assertIn("pole_blocked", [name for name, _ in sim.events])
        self.assertEqual(ground.mouth(z), (169, 189))
        self.assertFalse(ground.update(sim, z))

    def test_spikeweed_does_not_consume_pole(self):
        sim, z = Board([plant("spikeweed")]), unit("pole_vaulting", x=198)
        old = z.x
        self.assertTrue(ground.update(sim, z))
        self.assertEqual(z.phase, "pole_running")
        self.assertTrue(z.tool)
        self.assertLess(z.x, old)

    def test_pole_is_put_away_at_brain_even_without_obstacle(self):
        sim = Board(brains=[SimpleNamespace(row=3, hp=70)])
        z = unit("pole_vaulting", x=-30)
        self.assertFalse(ground.update(sim, z))
        self.assertEqual(z.phase, "pole_walking")
        self.assertEqual(ground.mouth(z), (20, 40))

    def test_headless_running_pole_keeps_moving_but_does_not_jump(self):
        sim, z = Board([plant()]), unit("pole_vaulting", x=198, headless=True)
        ground.update(sim, z)
        self.assertEqual(z.phase, "pole_running")
        self.assertAlmostEqual(z.x, 197.68)

    def test_jump_finishes_after_head_loss(self):
        sim, z = Board([plant()]), unit("pole_vaulting", x=198)
        ground.update(sim, z)
        z.headless = True
        for _ in range(ground.POLE_JUMP_FRAMES):
            ground.update(sim, z)
        self.assertEqual(z.phase, "pole_walking")

    def test_chill_slows_jump_animation_and_butter_pauses_it(self):
        sim, z = Board([plant()]), unit("pole_vaulting", x=198)
        ground.update(sim, z)
        z.chilled = 1000
        ground.update(sim, z)
        self.assertAlmostEqual(z.phase_timer, ground.POLE_JUMP_DURATION - 1.5)
        z.buttered = 10
        before = z.x, z.phase_timer
        ground.update(sim, z)
        self.assertEqual((z.x, z.phase_timer), before)

    def test_collision_x_does_not_follow_rendered_vault_offset(self):
        sim, z = Board([plant()]), unit("pole_vaulting", x=198.75)
        for _ in range(90):
            ground.update(sim, z)
        velocity = (198 - 120 - 80) / (43 / 24 * 100)
        self.assertAlmostEqual(z.x, 198.75 - 90 * velocity)
        self.assertEqual(z.phase, "pole_jumping")

    def test_tallnut_rechecked_in_animation_window_not_at_landing(self):
        sim, z = Board([plant("tallnut")]), unit("pole_vaulting", x=198)
        for _ in range(108):
            ground.update(sim, z)
        self.assertEqual(z.phase, "pole_jumping")
        ground.update(sim, z)
        self.assertEqual(z.phase, "pole_walking")
        self.assertAlmostEqual(z.x, 120 - ground.WALK_SPEED)

    def test_destroyed_tallnut_does_not_block_from_cached_target(self):
        p = plant("tallnut")
        sim, z = Board([p]), unit("pole_vaulting", x=198)
        for _ in range(108):
            ground.update(sim, z)
        p.hp = 0
        for _ in range(73):
            ground.update(sim, z)
        self.assertEqual(z.phase, "pole_walking")
        self.assertNotIn("pole_blocked", [name for name, _ in sim.events])

    def test_new_tallnut_can_block_instead_of_original_target(self):
        sim, z = Board([plant()]), unit("pole_vaulting", x=198)
        for _ in range(108):
            ground.update(sim, z)
        sim.plants[0] = plant("tallnut", id="replacement")
        ground.update(sim, z)
        self.assertIn("pole_blocked", [name for name, _ in sim.events])

    def test_pumpkin_does_not_mask_tallnut_for_vault_target(self):
        sim = Board([plant("pumpkin", id="shell"), plant("tallnut", id="main")])
        z = unit("pole_vaulting", x=198)
        ground.update(sim, z)
        self.assertEqual(z.target, "main")
        for _ in range(108):
            ground.update(sim, z)
        self.assertEqual(z.phase, "pole_walking")
        self.assertIn("pole_blocked", [name for name, _ in sim.events])

    def test_pumpkin_without_main_plant_still_triggers_vault(self):
        for x, phase in ((189, "pole_jumping"), (190, "pole_running")):
            sim, z = Board([plant("pumpkin")]), unit("pole_vaulting", x=x)
            ground.update(sim, z)
            self.assertEqual(z.phase, phase)

    def test_chill_slows_animation_but_not_jump_collision_displacement(self):
        warm, cold = unit("pole_vaulting", x=198), unit("pole_vaulting", x=198, chilled=1000)
        a, b = Board([plant()]), Board([plant()])
        for _ in range(180):
            ground.update(a, warm)
            ground.update(b, cold)
        self.assertAlmostEqual(warm.x, cold.x)
        self.assertEqual((warm.phase, cold.phase), ("pole_jumping", "pole_jumping"))
        ground.update(a, warm)
        ground.update(b, cold)
        self.assertEqual(warm.phase, "pole_walking")
        self.assertEqual(cold.phase, "pole_jumping")
        for _ in range(179):
            ground.update(b, cold)
        self.assertEqual(cold.phase, "pole_walking")
        self.assertAlmostEqual(cold.x, 198 - 359 * (-2 / ground.POLE_JUMP_DURATION) - 150)


class LadderTests(unittest.TestCase):
    def test_ladder_places_on_nut_without_eating_then_crosses(self):
        sim, z = Board([plant()]), unit("ladder", x=140)
        self.assertTrue(ground.update(sim, z))
        self.assertEqual(z.phase, "ladder_placing")
        for _ in range(ground.LADDER_PLACE_FRAMES):
            ground.update(sim, z)
        self.assertIn((3, 2), sim.ladders)
        self.assertEqual((z.shield_hp, z.tool), (0, False))
        self.assertEqual(z.phase, "ladder_climbing")
        for _ in range(ground.LADDER_CLIMB_FRAMES):
            ground.update(sim, z)
        self.assertEqual(z.phase, "walking")
        self.assertEqual(z.x, 50)
        self.assertEqual(sim.plants[0].hp, 4000)

    def test_ladder_animation_uses_extracted_12_frames_at_24fps(self):
        self.assertEqual(ground.LADDER_PLACE_FRAMES, 50)

    def test_carrying_ladder_does_not_place_on_normal_plant(self):
        sim, z = Board([plant("sunflower")]), unit("ladder", x=140)
        self.assertFalse(ground.update(sim, z))
        self.assertEqual(z.phase, "ladder_carrying")

    def test_removed_ladder_interrupts_placement(self):
        sim, z = Board([plant()]), unit("ladder", x=140)
        ground.update(sim, z)
        ground.remove_tool(sim, z)
        self.assertEqual(z.phase, "walking")
        self.assertEqual(z.shield_hp, 0)
        self.assertFalse(ground.update(sim, z))
        self.assertFalse(sim.ladders)

    def test_broken_ladder_shield_transitions_to_normal_walk(self):
        sim, z = Board(), unit("ladder")
        ground.initialize(sim, z)
        z.shield_hp = 0
        self.assertFalse(ground.update(sim, z))
        self.assertEqual(z.phase, "walking")
        self.assertFalse(z.tool)

    def test_destroyed_target_does_not_leave_floating_ladder(self):
        sim, z = Board([plant()]), unit("ladder", x=140)
        ground.update(sim, z)
        sim.plants[0].hp = 0
        for _ in range(ground.LADDER_PLACE_FRAMES):
            ground.update(sim, z)
        self.assertEqual(z.phase, "ladder_carrying")
        self.assertFalse(sim.ladders)

    def test_any_ground_unit_can_use_an_existing_ladder_once(self):
        sim, z = Board([plant()]), unit(x=120)
        sim.ladders.add((3, 2))
        self.assertTrue(ground.update(sim, z))
        self.assertEqual(z.phase, "ladder_climbing")
        for _ in range(ground.LADDER_CLIMB_FRAMES):
            ground.update(sim, z)
        self.assertEqual(z.x, 50)
        self.assertFalse(ground.update(sim, z))

    def test_miner_does_not_climb_ladders(self):
        sim, z = Board([plant()]), unit("digger", x=120, phase="digger_walking_no_axe")
        sim.ladders.add((3, 2))
        self.assertFalse(ground.update(sim, z))

    def test_ladder_removed_mid_climb_does_not_teleport_zombie_across(self):
        sim, z = Board([plant()]), unit(x=120)
        sim.ladders.add((3, 2))
        ground.update(sim, z)
        sim.ladders.clear()
        ground.update(sim, z)
        self.assertEqual(z.phase, "initial")
        self.assertEqual(z.x, 120)
        self.assertFalse(ground.update(sim, z))

    def test_headless_placement_waits_for_engine_decay_not_new_ladder(self):
        sim, z = Board([plant()]), unit("ladder", x=140)
        ground.update(sim, z)
        z.headless = True
        ground.update(sim, z)
        self.assertEqual(z.phase_timer, ground.LADDER_PLACE_FRAMES)
        self.assertFalse(sim.ladders)


class DiggerTests(unittest.TestCase):
    def test_digger_tunnels_through_plants_then_rises_reverses(self):
        sim, z = Board([plant()]), unit("digger", x=10)
        ground.update(sim, z)
        self.assertEqual(z.phase, "digger_tunneling")
        self.assertAlmostEqual(z.x, 9.33)
        self.assertFalse(ground.targetable(z))
        self.assertTrue(ground.targetable(z, "underground"))
        ground.update(sim, z)
        self.assertEqual((z.phase, z.direction, z.phase_timer), ("digger_rising", 1, 130))
        for _ in range(130):
            ground.update(sim, z)
        self.assertEqual(z.phase, "digger_stunned")
        self.assertTrue(ground.targetable(z))
        for _ in range(ground.DIGGER_STUN_FRAMES):
            ground.update(sim, z)
        self.assertEqual((z.phase, z.direction), ("digger_walking", 1))
        self.assertFalse(ground.update(sim, z))

    def test_underground_axe_loss_pauses_then_surfaces_facing_left(self):
        sim, z = Board(), unit("digger", helmet_hp=100)
        ground.initialize(sim, z)
        ground.remove_tool(sim, z)
        self.assertEqual((z.phase, z.phase_timer), ("digger_axe_pause", 200))
        self.assertEqual(z.helmet_hp, 100)
        before = z.x
        for _ in range(200):
            ground.update(sim, z)
        self.assertEqual(z.phase, "digger_rising_no_axe")
        for _ in range(130):
            ground.update(sim, z)
        self.assertEqual((z.phase, z.direction), ("digger_walking_no_axe", -1))
        self.assertEqual(z.x, before)
        self.assertFalse(ground.update(sim, z))

    def test_surface_axe_loss_does_not_turn_reverse_miner_left(self):
        sim = Board()
        z = unit("digger", phase="digger_walking", direction=1)
        ground.remove_tool(sim, z)
        self.assertFalse(z.tool)
        self.assertEqual((z.phase, z.direction), ("digger_walking", 1))

    def test_reverse_mouth_mirrors_around_120_pixel_sprite(self):
        z = unit("digger", phase="digger_walking", direction=1, x=100)
        self.assertEqual(ground.mouth(z), (150, 170))
        z = unit("dancer", phase="dancer_entering", direction=1, x=100)
        self.assertEqual(ground.mouth(z), (150, 170))

    def test_stun_uses_two_extracted_twenty_one_frame_loops_at_12fps(self):
        self.assertEqual(ground.DIGGER_STUN_FRAMES, 350)

    def test_rising_is_off_ground_but_magnet_can_still_target(self):
        z = unit("digger", phase="digger_rising")
        self.assertFalse(ground.targetable(z))
        self.assertTrue(ground.targetable(z, "off_ground"))
        self.assertTrue(ground.targetable(z, "magnet"))

    def test_tunnel_movement_does_not_use_chilled_ground_multiplier(self):
        sim, z = Board(), unit("digger", chilled=1000)
        ground.update(sim, z)
        self.assertAlmostEqual(z.x, 199.33)

    def test_headless_digger_does_not_stall_underground(self):
        sim, z = Board(), unit("digger", x=9, headless=True)
        ground.update(sim, z)
        for _ in range(130 + ground.DIGGER_STUN_FRAMES):
            ground.update(sim, z)
        self.assertEqual(z.phase, "digger_walking")
        self.assertFalse(ground.update(sim, z))


class GroundIntegrationTests(unittest.TestCase):
    def run_scenario(self, data):
        from pvz_ize.engine import Simulator
        from pvz_ize.model import parse_scenario
        return Simulator(parse_scenario({"max_frames": 15000, **data})).run()

    def test_obstacle_free_pole_eventually_eats_brain(self):
        result = self.run_scenario({"zombies": [
            {"type": "pole_vaulting", "row": 3, "col": 4}]})
        self.assertEqual(result["winner"], "zombies")
        self.assertEqual(result["zombies"][0]["phase"], "pole_walking")

    def test_ladder_leaves_nut_intact_and_reaches_brain(self):
        result = self.run_scenario({
            "plants": [{"type": "wallnut", "row": 3, "col": 2}],
            "zombies": [{"type": "ladder", "row": 3, "col": 4}],
        })
        self.assertEqual(result["winner"], "zombies")
        self.assertEqual(result["plants"][0]["hp"], 4000)
        self.assertIn({"row": 3, "col": 2}, result["ladders"])

    def test_unopposed_miner_reverses_exits_and_does_not_eat_brain(self):
        result = self.run_scenario({"zombies": [
            {"type": "digger", "row": 3, "col": 4}]})
        self.assertEqual(result["winner"], "plants")
        self.assertEqual(result["brains"][0]["hp"], 70)
        self.assertEqual(result["zombies"][0]["status"], "exited")
        self.assertGreater(result["zombies"][0]["x"], 850)


if __name__ == "__main__":
    unittest.main()
