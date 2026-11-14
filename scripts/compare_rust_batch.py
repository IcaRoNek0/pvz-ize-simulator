#!/usr/bin/env python3
"""Compare the Rust/Rayon simple batch envelope with the Python oracle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pvz_ize.batch import run_batch_parallel  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--binary", type=Path,
                        default=ROOT / "native_sim" / "target" / "release" / "pvz-ize-native-sim")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "docs" / "rust_batch_comparison.latest.json")
    args = parser.parse_args()
    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    python = run_batch_parallel(data, workers=args.workers)
    completed = subprocess.run(
        [str(args.binary), "--batch", "--workers", str(args.workers)],
        input=json.dumps(data, ensure_ascii=False), text=True,
        capture_output=True, check=False, cwd=ROOT,
    )
    rust = None
    if completed.stdout.strip():
        try:
            rust = json.loads(completed.stdout)
        except json.JSONDecodeError:
            rust = None
    py_rows = [(r["run_index"], r["seed"], r["winner"], r["frames"]) for r in python["results"]]
    rust_rows = [] if not isinstance(rust, dict) else [
        (r["run_index"], r["seed"], r["result"]["winner"], r["result"]["frames"])
        for r in rust.get("results", [])
    ]
    match = completed.returncode == 0 and py_rows == rust_rows
    report = {
        "schema": "pvz-ize/rust-simple-batch/v1",
        "fixture": str(args.fixture.resolve()),
        "fixture_sha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
        "workers": args.workers,
        "status": "match" if match else "mismatch",
        "python_rows": py_rows,
        "rust_rows": rust_rows,
        "rust_exit_status": completed.returncode,
        "rust_stderr": completed.stderr,
        "rust_binary": str(args.binary.resolve()),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0 if match else 2


if __name__ == "__main__":
    raise SystemExit(main())
