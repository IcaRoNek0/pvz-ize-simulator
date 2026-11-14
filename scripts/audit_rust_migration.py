#!/usr/bin/env python3
"""Run explicit Rust migration fixtures and preserve real mismatches.

The fixture manifest marks migrated projectile, armor, rake and ladder slices
as an already-migrated ``simple`` contract. A mismatch is evidence, not a
failure hidden by a compatibility fallback; the report records both outputs
and the expected migration status.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_fixture(fixture, binary, timeout):
    scenario = ROOT / "examples" / fixture["scenario"]
    if fixture["profile"] == "simple":
        command = [sys.executable, str(ROOT / "scripts" / "diff_rust_simple.py"),
                   str(scenario), "--rust-binary", str(binary)]
    else:
        command = [sys.executable, str(ROOT / "scripts" / "diff_rust_python.py"),
                   str(scenario), "--profile", fixture["profile"],
                   "--rust-binary", str(binary)]
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               capture_output=True, timeout=timeout, check=False)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"status": "error", "stderr": completed.stderr,
                   "stdout": completed.stdout}
    if fixture["profile"] == "simple":
        record = payload if isinstance(payload, dict) else {"status": "error", "raw": payload}
        actual = record.get("status")
    else:
        records = payload.get("records", []) if isinstance(payload, dict) else []
        record = records[0] if records else payload
        actual = record.get("status")
    return {
        "id": fixture["id"], "mechanism": fixture["mechanism"],
        "profile": fixture["profile"], "scenario": str(scenario),
        "expected_status": fixture["expected_status"],
        "actual_status": actual, "exit_code": completed.returncode,
        "comparison": record,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "examples" / "rust_migration_fixtures.json")
    parser.add_argument("--rust-binary", type=Path,
                        default=ROOT / "native_sim" / "target" / "release" / "pvz-ize-native-sim")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "docs" / "rust-migration-diff.latest.json")
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = [run_fixture(fixture, args.rust_binary, args.timeout) for fixture in manifest]
    report = {
        "schema": 1,
        "rust_binary": str(args.rust_binary.resolve()),
        "records": records,
        "counts": {status: sum(r["actual_status"] == status for r in records)
                   for status in ("match", "mismatch", "error")},
        "notes": [
            "mismatch_until_ported is intentional evidence for unported Rust mechanisms.",
            "No mismatch is converted into a pass by this audit.",
        ],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    # This audit is a migration report, so expected mismatches do not fail the
    # command; unexpected statuses do, while still preserving the report.
    unexpected = any(
        (r["expected_status"] == "match" and r["actual_status"] != "match") or
        (r["expected_status"] == "mismatch_until_ported" and r["actual_status"] != "mismatch")
        for r in records
    )
    return 2 if unexpected else 0


if __name__ == "__main__":
    raise SystemExit(main())
