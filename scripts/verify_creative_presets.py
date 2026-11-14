"""Run the 78 extracted IZC presets; this checks execution/replay, not accuracy."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pvz_ize.creative import PLANT_CODES, ZOMBIE_CODES
from pvz_ize.catalog import PLANTS, ZOMBIES, MODEL
from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--presets", type=Path, default=ROOT / "outputs/who-will-win/reverse/wwwdefaultlevels.txt")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/who-will-win/preset-results.json")
    parser.add_argument("--max-frames", type=int, default=100000)
    args = parser.parse_args()
    rows = []
    for line in args.presets.read_text(encoding="utf-8").splitlines():
        if "|" not in line or line.lstrip().startswith("#"):
            continue
        initial = parse_scenario({"formation_code": line, "seed": 2026, "max_frames": args.max_frames})
        result = Simulator(initial).run()
        replay = Simulator(parse_scenario(initial.to_dict())).run()
        assert result == replay, line
        rows.append({"code": line, "winner": result["winner"], "frames": result["frames"],
                     "reason": result["reason"], "replay_equal": True})
    counts = dict(Counter(row["winner"] for row in rows))
    result = {"model": MODEL, "oracle": None, "note": "Model execution and deterministic replay only; not a game differential.",
              "coverage": {"editor_plants": len(PLANT_CODES), "editor_zombies": len(ZOMBIE_CODES)-1,
                  "missing_plants": sorted(set(PLANT_CODES.values()) - PLANTS.keys()),
                  "missing_zombies": sorted(set(ZOMBIE_CODES.values()) - ZOMBIES.keys())},
              "counts": counts, "presets": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(rows)} presets executed and replayed; {counts}")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
