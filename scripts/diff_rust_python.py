#!/usr/bin/env python3
"""Differential smoke harness for the in-progress Rust Simulator core.

The Rust executable is deliberately kept behind a small, stable protocol so
the core can be ported incrementally.  It must read one scenario JSON object
from stdin and write one result JSON object to stdout.  A result may be the
object itself or ``{"result": object}``; diagnostics belong on stderr.

This harness never treats an unavailable Rust binary as a pass.  It returns
exit status 3 in that case, status 2 for a semantic mismatch, and status 0
only when every requested scenario has matching terminal state projections.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pvz_ize.engine import Simulator
from pvz_ize.model import parse_scenario


def python_result(data: dict[str, Any]) -> dict[str, Any]:
    scenario = parse_scenario({**data, "runs": 1})
    return Simulator(scenario).run()


def projection(result: dict[str, Any]) -> dict[str, Any]:
    """Fields that define a terminal simulation result.

    Timing/diagnostic metadata (model version, warning text and seconds) is
    intentionally excluded.  Entity arrays and event counters remain in the
    projection so a Rust implementation cannot merely match the winner while
    silently diverging in its terminal state.
    """
    keys = (
        "winner", "reason", "status", "frames", "brains", "plants", "zombies",
        "projectiles", "pending_effects", "zombie_special_state",
        "plant_head_state", "active_hostile_zombies", "active_friendly_zombies",
        "ladders", "events",
    )
    return {key: result.get(key) for key in keys}


def rust_result(binary: Path, data: dict[str, Any], timeout: float) -> dict[str, Any]:
    completed = subprocess.run(
        [str(binary)], input=json.dumps(data, ensure_ascii=False, allow_nan=False),
        text=True, capture_output=True, timeout=timeout, check=False,
        cwd=str(ROOT),
    )
    if completed.returncode:
        raise RuntimeError(
            f"Rust simulator exited {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Rust simulator returned invalid JSON: {exc}") from exc
    if isinstance(value, dict) and isinstance(value.get("result"), dict):
        value = value["result"]
    if not isinstance(value, dict):
        raise RuntimeError("Rust simulator result must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare Rust and Python Simulator terminal states")
    parser.add_argument("scenarios", nargs="+", type=Path)
    parser.add_argument(
        "--rust-binary", type=Path,
        default=Path(os.environ.get("PVZ_IZE_RUST_SIM", "native_sim/target/release/pvz-ize-native-sim")),
        help="Rust Simulator executable (or PVZ_IZE_RUST_SIM)",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--out", type=Path, help="write the comparison report as JSON")
    args = parser.parse_args(argv)
    binary = args.rust_binary if args.rust_binary.is_absolute() else ROOT / args.rust_binary
    report: dict[str, Any] = {"schema": 1, "rust_binary": str(binary.resolve()), "records": []}
    if not binary.is_file() or not os.access(binary, os.X_OK):
        report.update(status="unavailable", reason="Rust Simulator binary not built")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 3

    failed = False
    for path in args.scenarios:
        record: dict[str, Any] = {"scenario": str(path)}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("scenario must be a JSON object")
            py = python_result(data)
            rust = rust_result(binary, {**data, "runs": 1}, args.timeout)
            py_projection, rust_projection = projection(py), projection(rust)
            record.update(
                status="match" if py_projection == rust_projection else "mismatch",
                python=py_projection, rust=rust_projection,
            )
            failed |= record["status"] != "match"
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            record.update(status="error", error=f"{type(exc).__name__}: {exc}")
            failed = True
        report["records"].append(record)
    report["status"] = "mismatch" if failed else "match"
    report["counts"] = {status: sum(r["status"] == status for r in report["records"])
                         for status in ("match", "mismatch", "error")}
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
