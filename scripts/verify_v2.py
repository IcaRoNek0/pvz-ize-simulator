"""Audit saved examples, replicate probabilities and normalized-state replays."""

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pvz_ize.catalog import MODEL, PLANTS, ZOMBIES
from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


def main():
    checks = []
    for scene in sorted((ROOT / "examples").glob("*.json")):
        prefix = ROOT / "outputs/examples" / scene.stem
        initial = json.loads(prefix.with_suffix(".initial.json").read_text())
        result = json.loads(prefix.with_suffix(".result.json").read_text())
        events = [json.loads(line) for line in prefix.with_suffix(".events.ndjson").read_text().splitlines()]
        if result.get("batch"):
            counts = Counter(item["winner"] for item in result["results"])
            assert result["runs"] == len(initial["runs"]) == len(result["results"])
            for winner, outcome in result["outcomes"].items():
                assert outcome["count"] == counts[winner]
                assert outcome["probability"] == counts[winner] / result["runs"]
            for record, expected in zip(initial["runs"], result["results"]):
                trace = []
                actual = Simulator(parse_scenario(record["scenario"]), trace.append).run()
                assert actual == {key: value for key, value in expected.items() if key != "run_index"}
                saved = [{key: value for key, value in event.items() if key not in {"run_index", "seed"}}
                         for event in events if event["run_index"] == record["run_index"]]
                assert trace == saved
            checks.append({"scenario": scene.name, "replicates_replayed": result["runs"],
                           "probabilities_verified": True, "results_and_events_equal": True})
        else:
            trace = []
            assert Simulator(parse_scenario(initial), trace.append).run() == result
            assert trace == events
            checks.append({"scenario": scene.name, "replicates_replayed": 1,
                           "winner": result["winner"], "results_and_events_equal": True})
    references = {}
    for name in ("PvZ-Portable", "rpze"):
        proc = subprocess.run(["git", "-C", str(ROOT / "ref" / name), "status", "--short"],
                              capture_output=True, text=True, check=True)
        references[name] = proc.stdout
        assert proc.stdout == "", f"reference repository modified: {name}"
    report = {"model": MODEL, "plants": len(PLANTS), "zombies": len(ZOMBIES),
              "pair_smoke_cases": len(PLANTS)*len(ZOMBIES), "examples": checks,
              "references_clean": references, "original_runtime_differential_tested": False}
    target = ROOT / "outputs/acceptance-v2.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
