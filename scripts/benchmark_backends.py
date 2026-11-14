#!/usr/bin/env python3
"""Benchmark current simulator backends without changing the default backend.

This is intentionally a correctness/performance gate for the Rust core port:
when a future native-core binary is available it can be added as a separate
backend, while the existing Python simulator remains the reference oracle.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pvz_ize.batch import run_batch, run_batch_parallel  # noqa: E402
from pvz_ize.native_batch import native_available, run_batch_rust  # noqa: E402


def timed(label, fn):
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    return {
        "backend": label,
        "seconds": elapsed,
        "runs_per_second": result["runs"] / elapsed,
        "outcomes": result["outcomes"],
        "winners": [row["winner"] for row in result["results"]],
        "result": result,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--runs", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(args.scenario.read_text(encoding="utf-8"))
    if args.runs is not None:
        data["runs"] = args.runs
    if int(data.get("runs", 1)) < 1:
        parser.error("runs must be positive")

    serial = timed("python-serial", lambda: run_batch(data))
    parallel = timed("python-processpool", lambda: run_batch_parallel(data, args.workers))
    rows = [serial, parallel]
    if native_available():
        rows.append(timed("rust-coordinator-python-workers",
                          lambda: run_batch_rust(data, args.workers)))

    oracle = serial["winners"]
    for row in rows:
        row["outcomes_equal_to_oracle"] = row["winners"] == oracle
        row.pop("winners", None)
        row.pop("result", None)
    report = {
        "scenario": str(args.scenario),
        "runs": int(data["runs"]),
        "workers": args.workers,
        "python": platform.python_version(),
        "rustc": shutil.which("rustc"),
        "cargo": shutil.which("cargo"),
        "native_coordinator_built": native_available(),
        "results": rows,
        "notes": [
            "Python serial is the semantic oracle for this migration gate.",
            "A future full Rust core must match oracle winners and final-state fixtures before it can become default.",
            "Per-game frames remain sequential; only independent seeded runs should be parallelized.",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
