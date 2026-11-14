"""Recreate example results, normalized starts and event traces."""

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    dest = ROOT / "outputs" / "examples"
    dest.mkdir(parents=True, exist_ok=True)
    summary = []
    for scene in sorted((ROOT / "examples").glob("*.json")):
        prefix = dest / scene.stem
        command = [sys.executable, "-m", "pvz_ize", "run", str(scene), "--json",
                   "--output", str(prefix.with_suffix(".result.json")),
                   "--dump-initial", str(prefix.with_suffix(".initial.json")),
                   "--trace", str(prefix.with_suffix(".events.ndjson"))]
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if proc.returncode not in (0, 2):
            raise RuntimeError(f"{scene.name}: {proc.stderr}")
        result = json.loads(proc.stdout)
        if result.get("batch"):
            summary.append({"scenario": scene.name, "runs": result["runs"],
                            "outcomes": result["outcomes"], "exit_code": proc.returncode})
            print(f"{scene.name}: {result['runs']} runs, {result['outcomes']}")
        else:
            summary.append({"scenario": scene.name, "winner": result["winner"],
                            "frames": result["frames"], "reason": result["reason"],
                            "brains": result["brains"], "exit_code": proc.returncode})
            print(f"{scene.name}: {result['winner']}, {result['frames']} frames")
    (dest / "index.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
