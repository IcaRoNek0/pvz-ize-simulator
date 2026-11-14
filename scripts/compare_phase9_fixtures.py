#!/usr/bin/env python3
"""Compare the phase-9 cherry-bomb Rust slice with the Python reference."""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "rust_phase9_cherry_bomb.json"
RUST = ROOT / "native_sim" / "target" / "release" / "pvz-ize-native-sim"

def run(cmd, *, stdin=None):
    p = subprocess.run(cmd, cwd=ROOT, text=True, input=stdin, capture_output=True)
    parsed = None
    if p.stdout.strip():
        try: parsed = json.loads(p.stdout)
        except json.JSONDecodeError: pass
    return p, parsed

def compact(value):
    if not value: return None
    out = {k: value[k] for k in ("winner", "reason", "frames", "status") if k in value}
    events = value.get("events")
    if isinstance(events, dict): out["events"] = events
    elif isinstance(events, list):
        counts = {}
        for event in events:
            if isinstance(event, dict) and event.get("event"):
                key = event["event"]; counts[key] = counts.get(key, 0) + 1
        out["events"] = dict(sorted(counts.items()))
    return out

def main():
    py, p = run([sys.executable, "-m", "pvz_ize", "run", str(FIXTURE), "--json"])
    rs, r = run([str(RUST), "--slice", "simple"], stdin=FIXTURE.read_text(encoding="utf-8"))
    comparison = {
        "python_exit_ok": bool(p) and py.returncode in (0, 2),
        "rust_exit_ok": rs.returncode == 0,
        "winner_match": bool(p and r and p.get("winner") == r.get("winner")),
        "reason_match": bool(p and r and p.get("reason") == r.get("reason")),
        "frame_match": bool(p and r and p.get("frames") == r.get("frames")),
    }
    artifact = {
        "schema": "pvz-ize/rust-phase9-fixtures/v1",
        "fixture": str(FIXTURE),
        "sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "python": {"exit_status": py.returncode, "compact": compact(p), "stdout": py.stdout, "stderr": py.stderr},
        "rust": {"exit_status": rs.returncode, "compact": compact(r), "stdout": rs.stdout, "stderr": rs.stderr},
        "comparison": comparison,
    }
    out = ROOT / "docs" / "rust_phase9_comparison.latest.json"
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    return 0 if all(comparison.values()) else 2
if __name__ == "__main__": raise SystemExit(main())
