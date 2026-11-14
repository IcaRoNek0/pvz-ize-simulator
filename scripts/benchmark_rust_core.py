#!/usr/bin/env python3
"""Benchmark the guarded optional Rust-core backend against Python.

This benchmark is deliberately separate from the production CLI default.  It
runs only fixtures accepted by ``pvz_ize.rust_core.supports_scenario`` and
reports winner mismatches rather than hiding them.  A full-engine port must
pass this gate before any backend promotion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from pvz_ize.batch import run_batch, run_batch_parallel  # noqa: E402
from pvz_ize.rust_core import (  # noqa: E402
    run_batch_rust_core,
    rust_core_available,
    supports_scenario,
)


def timed(fn: Callable[[], dict[str, Any]], runs: int) -> tuple[dict[str, Any], float]:
    start = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - start


def winners(result: dict[str, Any]) -> list[str]:
    return [str(row.get("winner")) for row in result.get("results", [])]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fixtures", nargs="+", type=Path)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.runs < 20:
        ap.error("--runs must be at least 20")
    if args.workers < 1:
        ap.error("--workers must be positive")
    if not rust_core_available():
        ap.error("Rust core binary is unavailable; build native_sim first")

    records: list[dict[str, Any]] = []
    failed = False
    for path in args.fixtures:
        original = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(original, dict):
            ap.error(f"{path}: expected scenario object")
        data = {**original, "runs": args.runs}
        record: dict[str, Any] = {"fixture": str(path), "runs": args.runs,
                                  "supported": supports_scenario(data)}
        if not record["supported"]:
            record.update(status="skipped", reason="outside guarded Rust slice")
            records.append(record)
            continue
        try:
            py, py_seconds = timed(lambda: run_batch(data), args.runs)
            py_parallel, py_parallel_seconds = timed(
                lambda: run_batch_parallel(data, workers=args.workers), args.runs)
            rust, rust_seconds = timed(
                lambda: run_batch_rust_core(data, workers=args.workers), args.runs)
            py_winners, parallel_winners, rust_winners = winners(py), winners(py_parallel), winners(rust)
            record.update(
                status="match" if py_winners == rust_winners else "mismatch",
                python={"seconds": py_seconds, "runs_per_second": args.runs / py_seconds,
                        "winners": py_winners},
                python_processpool={"seconds": py_parallel_seconds,
                                    "runs_per_second": args.runs / py_parallel_seconds,
                                    "winners": parallel_winners,
                                    "matches_python": parallel_winners == py_winners},
                rust_core={"seconds": rust_seconds,
                           "runs_per_second": args.runs / rust_seconds,
                           "winners": rust_winners,
                           "matches_python": rust_winners == py_winners},
                mismatch_indexes=[i for i, (a, b) in enumerate(zip(py_winners, rust_winners)) if a != b],
            )
            failed |= record["status"] != "match" or not record["python_processpool"]["matches_python"]
        except Exception as exc:  # benchmark report should identify fixture failures
            record.update(status="error", error=f"{type(exc).__name__}: {exc}")
            failed = True
        records.append(record)

    compared = [r for r in records if r.get("status") == "match"]
    report = {
        "schema": 1,
        "backend": "rust-core-slice",
        "python": platform.python_version(),
        "rust_core_binary": "native_sim/target/release/pvz-ize-native-sim",
        "workers": args.workers,
        "records": records,
        "counts": {
            "match": sum(r.get("status") == "match" for r in records),
            "mismatch": sum(r.get("status") == "mismatch" for r in records),
            "skipped": sum(r.get("status") == "skipped" for r in records),
            "error": sum(r.get("status") == "error" for r in records),
        },
        "all_compared_winners_match": bool(compared) and not failed,
        "default_backend_changed": False,
        "notes": [
            "Python Simulator is the reference oracle; this does not claim full-engine equivalence.",
            "Each fixture has at least 20 independent seeded runs; result order is compared by run_index.",
            "Unsupported or known-unmigrated fixtures are reported as skipped rather than silently using Rust rules.",
        ],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return 0 if report["all_compared_winners_match"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
