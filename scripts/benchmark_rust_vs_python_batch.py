#!/usr/bin/env python3
"""Reproducible end-to-end benchmark of Python and native Rust batch paths.

Both measurements include backend setup and process startup.  The Python path
uses ``run_batch_parallel`` and the Rust path invokes one ``--batch`` process;
this intentionally does not hide startup overhead.  Winners/frames/seeds are
compared on every repetition before timing statistics are reported.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pvz_ize.batch import run_batch_parallel  # noqa: E402


def _rows(result: dict[str, Any]) -> list[tuple[int, int, str, int]]:
    return [(int(row["run_index"]), int(row["seed"]), str(row["winner"]), int(row["frames"]))
            for row in result.get("results", [])]


def _timed_python(data: dict[str, Any], workers: int) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    result = run_batch_parallel(data, workers=workers)
    return time.perf_counter() - started, result


def _timed_rust(data: dict[str, Any], workers: int, binary: Path) -> tuple[float, dict[str, Any], int, str]:
    started = time.perf_counter()
    completed = subprocess.run(
        [str(binary), "--batch", "--workers", str(workers)],
        input=json.dumps(data, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )
    elapsed = time.perf_counter() - started
    if not completed.stdout.strip():
        return elapsed, {}, completed.returncode, completed.stderr
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return elapsed, {}, completed.returncode, completed.stderr + "\ninvalid JSON stdout"
    return elapsed, result, completed.returncode, completed.stderr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--binary", type=Path, default=ROOT / "native_sim" / "target" / "release" / "pvz-ize-native-sim")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "rust_python_batch_benchmark.latest.json")
    args = parser.parse_args(argv)
    if args.runs < 1 or args.workers < 1 or args.repeats < 1:
        parser.error("runs, workers and repeats must be positive")
    fixture = args.fixture.resolve()
    data = json.loads(fixture.read_text(encoding="utf-8"))
    data["runs"] = args.runs
    binary = args.binary.resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(f"Rust batch binary is not executable: {binary}")

    python_times: list[float] = []
    rust_times: list[float] = []
    comparisons: list[dict[str, Any]] = []
    for repeat in range(args.repeats):
        py_elapsed, py_result = _timed_python(data, args.workers)
        rust_elapsed, rust_result, rust_exit, rust_stderr = _timed_rust(data, args.workers, binary)
        py_rows = _rows(py_result)
        rust_rows = [
            (int(row["run_index"]), int(row["seed"]), str(row["result"]["winner"]), int(row["result"]["frames"]))
            for row in rust_result.get("results", [])
        ] if isinstance(rust_result, dict) else []
        row_match = py_rows == rust_rows
        python_times.append(py_elapsed)
        rust_times.append(rust_elapsed)
        comparisons.append({
            "repeat": repeat,
            "python_seconds": py_elapsed,
            "rust_seconds": rust_elapsed,
            "rust_exit_status": rust_exit,
            "rows_match": row_match,
            "python_rows": len(py_rows),
            "rust_rows": len(rust_rows),
            "rust_stderr": rust_stderr,
        })

    def stats(values: list[float]) -> dict[str, float]:
        return {
            "min": min(values),
            "median": statistics.median(values),
            "max": max(values),
            "mean": statistics.fmean(values),
            "runs_per_second_median": args.runs / statistics.median(values),
        }

    all_match = all(item["rows_match"] and item["rust_exit_status"] == 0 for item in comparisons)
    rust_median = statistics.median(rust_times)
    py_median = statistics.median(python_times)
    report = {
        "schema": "pvz-ize/python-vs-rust-batch-benchmark/v1",
        "fixture": str(fixture),
        "fixture_sha256": __import__("hashlib").sha256(fixture.read_bytes()).hexdigest(),
        "runs": args.runs,
        "workers": args.workers,
        "repeats": args.repeats,
        "correctness": {"status": "match" if all_match else "mismatch", "rows_compared_per_repeat": args.runs},
        "python": {"backend": "python-processpool", "timing": stats(python_times)},
        "rust": {"backend": "rust-simple-rayon-batch", "binary": str(binary), "timing": stats(rust_times)},
        "speedup_python_median_over_rust_median": py_median / rust_median if rust_median else None,
        "repetitions": comparisons,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "rustc": shutil.which("rustc"),
            "cargo": shutil.which("cargo"),
        },
        "notes": [
            "Both timings include backend setup and process startup; no warm-cache or startup subtraction is applied.",
            "This is a simple-slice throughput measurement, not evidence of full Simulator equivalence.",
            "Unsupported scenarios continue through the Python fallback.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0 if all_match else 2


if __name__ == "__main__":
    raise SystemExit(main())
