#!/usr/bin/env python3
"""Measure the native Rust/Rayon batch entry without changing the default backend."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--runs", type=int, default=None)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--binary", type=Path, default=Path("native_sim/target/release/pvz-ize-native-sim"))
    args = parser.parse_args()
    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    if args.runs is not None:
        data["runs"] = args.runs
    start = time.perf_counter()
    completed = subprocess.run(
        [str(args.binary), "--batch", "--workers", str(args.workers)],
        input=json.dumps(data, ensure_ascii=False), text=True,
        capture_output=True, check=False,
    )
    elapsed = time.perf_counter() - start
    if completed.returncode:
        print(completed.stderr, end="")
        return completed.returncode
    result = json.loads(completed.stdout)
    print(json.dumps({
        "backend": "rust-simple-rayon-batch",
        "runs": result["runs"],
        "workers": result["parallel_workers"],
        "seconds": elapsed,
        "runs_per_second": result["runs"] / elapsed if elapsed else float("inf"),
        "outcomes": result["outcomes"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
