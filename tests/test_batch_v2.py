import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from pvz_ize.batch import run_batch, run_seed
from pvz_ize.cli import main
from pvz_ize.model import ScenarioError, parse_scenario
from pvz_ize.catalog import ZOMBIES
from pvz_ize.engine import Simulator


def plant(**values):
    return {"type": "peashooter", "row": 3, "col": 2, **values}


def zombie(**values):
    return {"type": "digger", "row": 3, "col": 7, **values}


class V2InputTests(unittest.TestCase):
    def test_version_one_and_two_replay(self):
        for version in (1, 2):
            value = parse_scenario({"version": version, "plants": [plant()],
                                    "zombies": [zombie(underground=False, hypnotized=True)]})
            normalized = value.to_dict()
            self.assertEqual(normalized, parse_scenario(normalized).to_dict())
            self.assertEqual(value.zombies[0].phase, "digger_walking")
            self.assertEqual(value.zombies[0].direction, 1)
            self.assertEqual(value.zombies[0].speed, .11)

    def test_cross_layer_and_explicit_same_layer_stacking(self):
        p = [plant(layer="base"), plant(layer="main"), plant(layer="shell")]
        self.assertEqual(len(parse_scenario({"plants": p}).plants), 3)
        p.append(plant(layer="main"))
        with self.assertRaises(ScenarioError):
            parse_scenario({"plants": p})
        self.assertEqual(len(parse_scenario({"allow_stacking": True, "plants": p}).plants), 4)

    def test_multiple_zombies_same_cell(self):
        self.assertEqual(len(parse_scenario({"zombies": [zombie(), zombie()]}).zombies), 2)

    def test_animation_phase_and_mode(self):
        value = parse_scenario({"movement_mode": "animation", "plants": [plant(animation_phase=.9)],
                                "zombies": [zombie(animation_phase=0)]})
        self.assertEqual(value.movement_mode, "animation")
        self.assertEqual(value.plants[0].animation_phase, .9)
        self.assertEqual(value.zombies[0].animation_phase, 0)

    def test_garlic_direction_and_separate_health_fields(self):
        for direction in ("up", "down", "random"):
            value = parse_scenario({"plants": [plant(type="garlic", garlic_direction=direction, hp=100)],
                                    "zombies": [zombie(type="buckethead", hp=150, helmet_hp=50,
                                                       frozen=12, tool=False)]})
            self.assertEqual(value.plants[0].garlic_direction, direction)
            self.assertEqual((value.zombies[0].hp, value.zombies[0].helmet_hp,
                              value.zombies[0].frozen, value.zombies[0].tool), (150, 50, 12, False))
            self.assertEqual(value.to_dict(), parse_scenario(value.to_dict()).to_dict())

    def test_animation_sampling_is_replayable(self):
        data = {"movement_mode": "animation", "seed": 8,
                "zombies": [zombie(type="normal"), zombie(type="football"),
                            zombie(type="ladder"), zombie(underground=False)]}
        initial = parse_scenario(data)
        self.assertEqual(initial.to_dict(), parse_scenario(initial.to_dict()).to_dict())
        self.assertEqual(initial.to_dict(), parse_scenario(data).to_dict())
        self.assertTrue(.23 <= initial.zombies[0].velocity_parameter <= .37)
        self.assertTrue(.66 <= initial.zombies[1].velocity_parameter <= .68)
        self.assertTrue(.79 <= initial.zombies[2].velocity_parameter <= .81)
        self.assertEqual(initial.zombies[3].velocity_parameter, .23)
        self.assertTrue(all(0 <= z.animation_phase < 1 for z in initial.zombies))
        self.assertTrue(all(z.walk_variant in (0, 1) for z in initial.zombies))

    def test_explicit_animation_values_and_speed_override(self):
        for speed in (.001, .2, 5):
            data = {"movement_mode": "animation", "zombies": [zombie(type="normal", speed=speed)]}
            initial = parse_scenario(data)
            self.assertEqual(initial.zombies[0].velocity_parameter, speed / .47)
            self.assertEqual(initial.to_dict(), parse_scenario(initial.to_dict()).to_dict())
        initial = parse_scenario({"movement_mode": "animation", "zombies": [
            zombie(type="normal", speed=.5, velocity_parameter=.33, animation_phase=.4)]})
        self.assertEqual(initial.zombies[0].velocity_parameter, .33)
        self.assertEqual(initial.zombies[0].animation_phase, .4)

    def test_mean_mode_does_not_sample_animation_parameters(self):
        initial = parse_scenario({"zombies": [zombie()]})
        self.assertIsNone(initial.zombies[0].velocity_parameter)
        self.assertIsNone(initial.zombies[0].animation_phase)
        self.assertIsNone(initial.zombies[0].walk_variant)

    def test_walk_variant_explicit_and_flag_default(self):
        initial = parse_scenario({"movement_mode": "animation", "zombies": [
            zombie(type="flag"), zombie(type="normal", walk_variant=1)]})
        self.assertEqual([z.walk_variant for z in initial.zombies], [0, 1])
        for value in (-1, 2, True, .5, None):
            with self.subTest(value=value), self.assertRaises(ScenarioError):
                parse_scenario({"zombies": [zombie(walk_variant=value)]})

    def test_magnet_distance_mode_validation_and_replay(self):
        self.assertEqual(parse_scenario({}).magnet_distance_mode, "horizontal")
        for mode in ("horizontal", "source"):
            initial = parse_scenario({"magnet_distance_mode": mode})
            self.assertEqual(initial.to_dict(), parse_scenario(initial.to_dict()).to_dict())
        for mode in ([], None, True, "euclidean"):
            with self.subTest(mode=mode), self.assertRaises(ScenarioError):
                parse_scenario({"magnet_distance_mode": mode})

    def test_low_health_no_head_loss_types_stay_headed(self):
        for name, spec in ZOMBIES.items():
            if not spec.can_lose_head:
                with self.subTest(type=name):
                    initial = parse_scenario({"zombies": [zombie(type=name, hp=1)]})
                    self.assertFalse(initial.zombies[0].headless)
                    result = Simulator(initial).run() if name == "bungee" else Simulator(
                        parse_scenario({**initial.to_dict(), "max_frames": 1})).run()
                    self.assertFalse(result["zombies"][0]["headless"])

    def test_initial_landed_balloon_animation_does_not_crash(self):
        initial = parse_scenario({"movement_mode": "animation", "max_frames": 2,
                                  "zombies": [zombie(type="balloon", tool=False)]})
        self.assertIsNotNone(initial.zombies[0].velocity_parameter)
        self.assertEqual(Simulator(initial).run()["frames"], 2)

    def test_bad_values(self):
        for data in ({"runs": 0}, {"runs": True}, {"runs": 1.5}, {"runs": 100001},
                     {"allow_stacking": 1}, {"movement_mode": []},
                     {"plants": [plant(layer=[])]}, {"plants": [plant(garlic_direction="up")]},
                     {"plants": [plant(animation_phase=1)]},
                     {"zombies": [zombie(underground=1)]},
                     {"zombies": [zombie(type="normal", underground=False)]},
                     {"zombies": [zombie(hypnotized=1)]}):
            with self.subTest(data=data), self.assertRaises(ScenarioError):
                parse_scenario(data)


class BatchTests(unittest.TestCase):
    def test_each_animation_replica_replays_full_state_and_events(self):
        data = {"runs": 3, "seed": -20, "movement_mode": "animation", "max_frames": 30,
                "plants": [plant(type="garlic", garlic_direction="random"), plant(row=2)],
                "zombies": [zombie(type="normal"), zombie(type="balloon", tool=False),
                            zombie(type="jack_in_the_box", row=2), zombie(underground=False)]}
        initial, events = [], []
        batch = run_batch(data, initial_sink=initial.append, event_sink=events.append)
        for index, record in enumerate(initial):
            with self.subTest(index=index):
                replay_events = []
                replay = Simulator(parse_scenario(record["scenario"]), event_sink=replay_events.append).run()
                expected = dict(batch["results"][index])
                expected.pop("run_index")
                self.assertEqual(replay, expected)
                tagged = [{k: v for k, v in e.items() if k not in {"run_index", "seed"}}
                          for e in events if e["run_index"] == index]
                self.assertEqual(replay_events, tagged)

    def test_batch_repeatability_counts_and_initial_resampling(self):
        data = {"runs": 8, "seed": 10, "max_frames": 2, "plants": [plant()],
                "zombies": [zombie(type="normal")]}
        initial, events = [], []
        result = run_batch(data, event_sink=events.append, initial_sink=initial.append)
        self.assertEqual(result, run_batch(data))
        self.assertEqual(result["outcomes"]["undecided"]["count"], 8)
        self.assertEqual(sum(o["probability"] for o in result["outcomes"].values()), 1)
        self.assertEqual([i["seed"] for i in initial], list(range(10, 18)))
        self.assertGreater(len({i["scenario"]["plants"][0]["cooldown"] for i in initial}), 1)
        for item in initial:
            self.assertEqual(item["scenario"]["runs"], 1)
            self.assertEqual(item["scenario"], parse_scenario(item["scenario"]).to_dict())
        self.assertTrue(all("run_index" in e and "seed" in e for e in events))

    def test_fixed_initial_cooldown_remains_fixed(self):
        initial = []
        run_batch({"runs": 3, "plants": [plant(cooldown=7)]}, initial_sink=initial.append)
        self.assertEqual([i["scenario"]["plants"][0]["cooldown"] for i in initial], [7]*3)

    def test_seed_wrap(self):
        self.assertEqual(run_seed(2**63-1, 1), -2**63)

    def test_cli_batch_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scenario, initial, trace = (root / name for name in ("in.json", "initial.json", "trace.ndjson"))
            scenario.write_text(json.dumps({"runs": 2, "zombies": [zombie()], "max_frames": 1}))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["run", str(scenario), "--json", "--dump-initial", str(initial), "--trace", str(trace)])
            self.assertEqual(code, 2)
            result = json.loads(output.getvalue())
            self.assertEqual(result["runs"], 2)
            self.assertEqual(len(json.loads(initial.read_text())["runs"]), 2)
            events = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual({event["run_index"] for event in events}, {0, 1})

    def test_batch_cli_safety_before_opening_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scenario = root / "in.json"
            output = root / "keep.ndjson"
            output.write_text("keep")
            scenario.write_text(json.dumps({"runs": 0}))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["run", str(scenario), "--trace", str(output)]), 1)
            self.assertEqual(output.read_text(), "keep")
            scenario.write_text(json.dumps({"runs": 2}))
            original = scenario.read_text()
            alias = root / "alias.json"
            alias.hardlink_to(scenario)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["run", str(scenario), "--trace", str(alias)]), 1)
            self.assertEqual(scenario.read_text(), original)
