#!/usr/bin/env python3
"""Benchmark the current Rust ``--slice simple`` vertical migration.

The slice is intentionally compared against the *same small Python contract*
implemented by ``scripts/diff_rust_simple.py``.  This is not a claim that the
slice matches the full pvz_ize Simulator; ``--full-engine`` comparisons belong
to the differential gate.  The slice is never selected as the production
backend by this script.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import subprocess
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIFF_PATH = ROOT / "scripts" / "diff_rust_simple.py"
_spec = importlib.util.spec_from_file_location("rust_slice_contract", DIFF_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load diff_rust_simple.py")
_contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_contract)
python_reference = _contract.python_reference


def _python_one(data: dict[str, Any]) -> dict[str, Any]:
    return python_reference(data)


def _rust_one(task: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    binary, data = task
    completed = subprocess.run(
        [binary, "--slice", "simple"],
        input=json.dumps(data, ensure_ascii=False, allow_nan=False),
        text=True, capture_output=True, check=False, cwd=ROOT,
    )
    if completed.returncode:
        raise RuntimeError(f"Rust slice exited {completed.returncode}: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def _timed(label: str, fn, total: int, oracle: list[dict[str, Any]]) -> dict[str, Any]:
    start = time.perf_counter()
    results = fn()
    elapsed = time.perf_counter() - start
    winners = [str(item.get("winner")) for item in results]
    oracle_winners = [str(item.get("winner")) for item in oracle]
    return {
        "backend": label,
        "seconds": elapsed,
        "runs_per_second": total / elapsed if elapsed else float("inf"),
        "winner_counts": dict(Counter(winners)),
        "matches_oracle": winners == oracle_winners,
        "mismatch_indexes": [i for i, (a, b) in enumerate(zip(winners, oracle_winners)) if a != b],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="+", type=Path,
                    help="small-slice scenario JSON files")
    ap.add_argument("--runs", type=int, default=100,
                    help="number of independent scenarios (cycled through inputs)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rust-binary", type=Path,
                    default=ROOT / "native_sim" / "target" / "release" / "pvz-ize-native-sim")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.runs < 1 or args.workers < 1:
        ap.error("runs and workers must be positive")
    binary = args.rust_binary if args.rust_binary.is_absolute() else ROOT / args.rust_binary
    if not binary.is_file():
        ap.error(f"Rust binary not found: {binary}; build native_sim first")

    templates = []
    for path in args.scenarios:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            ap.error(f"{path}: scenario must be a JSON object")
        templates.append(data)
    scenarios = []
    for i in range(args.runs):
        data = dict(templates[i % len(templates)])
        data["runs"] = 1
        # The slice contract is deterministic; preserving a distinct seed in the
        # manifest makes future RNG migrations measurable without changing it now.
        data["seed"] = int(data.get("seed", 0)) + i
        scenarios.append(data)

    # Sequential reference contract.
    reference = [_python_one(data) for data in scenarios]
    rows = [_timed("python-reference", lambda: [_python_one(d) for d in scenarios], args.runs, reference)]

    def processpool_run():
        with ProcessPoolExecutor(max_workers=min(args.workers, args.runs)) as pool:
            return list(pool.map(_python_one, scenarios))
    rows.append(_timed("python-processpool-reference", processpool_run, args.runs, reference))

    def rust_run():
        tasks = [(str(binary), data) for data in scenarios]
        with ThreadPoolExecutor(max_workers=min(args.workers, args.runs)) as pool:
            return list(pool.map(_rust_one, tasks))
    rows.append(_timed("rust-slice", rust_run, args.runs, reference))

    report = {
        "schema": 1,
        "slice": "peashooter/normal projectile-bite contract",
        "scenarios": [str(path) for path in args.scenarios],
        "runs": args.runs,
        "workers": args.workers,
        "rust_binary": str(binary.resolve()),
        "results": rows,
        "production_backend_changed": False,
        "notes": [
            "Python reference and Rust --slice use the same deliberately small contract.",
            "Python processpool uses independent scenarios; Rust subprocesses are launched concurrently.",
            "A full Simulator migration must pass scripts/diff_rust_python.py before replacing the default backend.",
        ],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return 0 if all(row["matches_oracle"] for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
