import unittest
from types import SimpleNamespace

from pvz_ize import plant_animation as animation


class PlantAnimationTests(unittest.TestCase):
    def plant(self, kind="peashooter", phase=0):
        return SimpleNamespace(type=kind, animation_phase=phase, animation_rate=17.5)

    def test_resource_metadata(self):
        self.assertEqual(set(animation.tracks()), animation.TYPES)
        for track in animation.tracks().values():
            self.assertEqual(track["frame_count"], 25)
            self.assertEqual(len(track["xy"]), 25)
            self.assertEqual(len(track["sha256"]), 64)
        self.assertEqual(animation.tracks()["peashooter"]["asset"], "PeaShooterSingle.reanim.compiled")
        self.assertEqual(animation.tracks()["repeater"]["asset"], "PeaShooter.reanim.compiled")

    def test_loop_uses_n_minus_one_and_linear_interpolation(self):
        for kind in animation.TYPES:
            xy = animation.tracks()[kind]["xy"]
            self.assertEqual(animation.sample_transform(kind, 0), tuple(xy[0]))
            self.assertEqual(animation.sample_transform(kind, .5), tuple(xy[12]))
            sampled = animation.sample_transform(kind, 12.5 / 24)
            for value, a, b in zip(sampled, xy[12], xy[13]):
                self.assertAlmostEqual(value, (a + b) / 2)

    def test_integer_truncation_and_fire_offsets(self):
        for kind in animation.TYPES:
            p = self.plant(kind, .3123)
            x, y = animation.sample_transform(kind, p.animation_phase)
            dx, dy = animation.muzzle_offset(p)
            self.assertEqual(dx, int(x) + (34 if kind == "gatling_pea" else 24))
            self.assertEqual(dy, int(y) - 33)

    def test_split_front_rear_separation(self):
        for phase in (0, .1, .5, .99):
            p = self.plant("split_pea", phase)
            front, back = animation.muzzle_offset(p), animation.muzzle_offset(p, -1)
            self.assertEqual(front[0] - back[0], 88)
            self.assertEqual(front[1], back[1])

    def test_advance_formula_and_wrap(self):
        self.assertAlmostEqual(animation.advance_phase("peashooter", .999, 20), .007)
        p = self.plant(phase=None)
        animation.advance(p)
        self.assertAlmostEqual(p.animation_phase, .01 * 17.5 / 25)

    def test_unknown_type_and_invalid_rear_fail(self):
        with self.assertRaises(KeyError):
            animation.sample_transform("sunflower", 0)
        with self.assertRaises(ValueError):
            animation.muzzle_offset(self.plant(), -1)

    def test_phase_changes_muzzle(self):
        p = self.plant("split_pea")
        positions = set()
        for _ in range(200):
            animation.advance(p)
            positions.add(animation.muzzle_offset(p, -1)[0])
        self.assertGreater(len(positions), 5)


if __name__ == "__main__":
    unittest.main()
