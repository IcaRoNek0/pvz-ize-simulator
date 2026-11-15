#!/usr/bin/env python3
"""Run the Phase 27 one-tick dancing catalog fixture."""
from __future__ import annotations
import hashlib, importlib.util, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [ROOT / "examples" / "rust_phase27_split_pea.json", ROOT / "examples" / "rust_phase27_dancing_defaults.json", ROOT / "examples" / "rust_phase27_backup_dancer_defaults.json"]
RUST = ROOT / "native_sim" / "target" / "release" / "pvz-ize-native-sim"
spec = importlib.util.spec_from_file_location("diff_rust_simple", ROOT / "scripts" / "diff_rust_simple.py")
if spec is None or spec.loader is None: raise RuntimeError("cannot load diff_rust_simple.py")
diff = importlib.util.module_from_spec(spec); spec.loader.exec_module(diff)
def main() -> int:
    rows = []
    for fixture in FIXTURES:
        data = json.loads(fixture.read_text(encoding="utf-8")); expected = diff.python_reference(data)
        p = subprocess.run([str(RUST), "--slice", "simple"], input=json.dumps(data, ensure_ascii=False), text=True, capture_output=True, check=False, cwd=ROOT)
        actual = json.loads(p.stdout) if p.stdout.strip() else None
        rows.append({"fixture":str(fixture), "sha256":hashlib.sha256(fixture.read_bytes()).hexdigest(), "status":"match" if p.returncode == 0 and actual == expected else "mismatch", "python":expected, "rust":actual, "rust_exit_status":p.returncode, "stderr":p.stderr})
    report = {"schema":"pvz-ize/rust-phase27-split-dancing/v3", "rust_binary":str(RUST.resolve()), "fixtures":rows, "status":"match" if all(row["status"] == "match" for row in rows) else "mismatch"}
    out = ROOT / "docs" / "rust_phase27_comparison.latest.json"; out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(out); return 0 if report["status"] == "match" else 2
if __name__ == "__main__": raise SystemExit(main())
