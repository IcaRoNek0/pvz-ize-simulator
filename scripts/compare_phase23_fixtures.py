#!/usr/bin/env python3
"""Run the Phase 23 fume-shroom guarded fixture."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [ROOT / "examples" / "rust_phase23_fume_shroom.json"]
RUST = ROOT / "native_sim" / "target" / "release" / "pvz-ize-native-sim"
spec = importlib.util.spec_from_file_location("diff_rust_simple", ROOT / "scripts" / "diff_rust_simple.py")
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load diff_rust_simple.py")
diff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diff)

def main() -> int:
    rows = []
    for fixture in FIXTURES:
        data = json.loads(fixture.read_text(encoding="utf-8"))
        expected = diff.python_reference(data)
        completed = subprocess.run([str(RUST), "--slice", "simple"], input=json.dumps(data, ensure_ascii=False), text=True, capture_output=True, check=False, cwd=ROOT)
        actual = None
        if completed.stdout.strip():
            try:
                actual = json.loads(completed.stdout)
            except json.JSONDecodeError:
                pass
        rows.append({"fixture": str(fixture), "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(), "status": "match" if completed.returncode == 0 and actual == expected else "mismatch", "python": expected, "rust": actual, "rust_exit_status": completed.returncode, "stderr": completed.stderr})
    report = {"schema": "pvz-ize/rust-phase23-fume-shroom/v1", "rust_binary": str(RUST.resolve()), "fixtures": rows, "status": "match" if all(row["status"] == "match" for row in rows) else "mismatch"}
    out = ROOT / "docs" / "rust_phase23_comparison.latest.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    return 0 if report["status"] == "match" else 2

if __name__ == "__main__":
    raise SystemExit(main())
