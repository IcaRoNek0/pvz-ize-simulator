"""Reproduce reported layouts without overwriting user-owned run artifacts."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


class MuzzleProbe(Simulator):
    stem_delta = 0

    def add_projectile(self, p, row, x, kind, direction=1, **state):
        if p.type == "split_pea":
            x += self.stem_delta
        return super().add_projectile(p, row, x, kind, direction, **state)


def main():
    destination = ROOT / "outputs/regressions/5-7"
    destination.mkdir(parents=True, exist_ok=True)
    summary = []
    for number in (5, 7):
        original = json.loads((ROOT / f"run/{number}.json").read_text())
        for mode in ("mean", "animation"):
            # Check both ends of the extracted idle stem's integer x range.
            for delta in ((0, 10) if number == 7 else (0,)):
                outcomes, first_events, explosions = {}, [], []
                for index in range(original.get("runs", 1)):
                    data = {**original, "movement_mode": mode,
                            "seed": original.get("seed", 0) + index}
                    def capture(event):
                        if index == 0 and event["event"] in {
                                "plant_died", "zombie_died", "head_lost", "finished"}:
                            first_events.append(event)
                        if event["event"] == "explosion":
                            explosions.append({"run_index": index, "frame": sim.frame,
                                "zombies": [{"id": z.id, "x": z.x, "hp": z.hp}
                                            for z in sim.zombies]})
                    sim = MuzzleProbe(parse_scenario(data), capture)
                    sim.stem_delta = delta
                    result = sim.run()
                    winner = result["winner"]
                    outcomes[winner] = outcomes.get(winner, 0) + 1
                summary.append({"layout": number, "movement_mode": mode,
                    "stem_delta_probe": delta, "outcomes": outcomes,
                    "first_run_events": first_events, "explosions": explosions})
    path = destination / "comparison.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print(path)
    for row in summary:
        print(row["layout"], row["movement_mode"], row["stem_delta_probe"], row["outcomes"])


if __name__ == "__main__":
    main()
