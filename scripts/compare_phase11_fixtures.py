#!/usr/bin/env python3
"""Compare Rust spikeweed/spikerock hazard slices with the Python reference."""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [ROOT / "examples" / "rust_phase11_spikeweed.json",
            ROOT / "examples" / "rust_phase11_spikerock.json"]
RUST = ROOT / "native_sim" / "target" / "release" / "pvz-ize-native-sim"

def run(cmd, *, stdin=None):
    p = subprocess.run(cmd, cwd=ROOT, input=stdin, text=True, capture_output=True)
    value = None
    if p.stdout.strip():
        try: value = json.loads(p.stdout)
        except json.JSONDecodeError: pass
    return p, value

def compact(value):
    if not value: return None
    out = {k: value[k] for k in ("winner", "reason", "frames") if k in value}
    if "state" in value:
        state = value["state"]
        out["events"] = state.get("events", {})
        out["zombies"] = [{k: z.get(k) for k in ("id", "status", "hp", "helmet_hp")} for z in state.get("zombies", [])]
        out["plants"] = [{k: p.get(k) for k in ("id", "type", "hp", "state", "state_timer")} for p in state.get("plants", [])]
    else:
        out["events"] = value.get("events", {})
        out["zombies"] = [{k: z.get(k) for k in ("id", "status", "hp", "helmet_hp")} for z in value.get("zombies", [])]
        out["plants"] = [{k: p.get(k) for k in ("id", "type", "hp", "state", "state_timer")} for p in value.get("plants", [])]
    return out

def main():
    rows = []
    for fixture in FIXTURES:
        py, p = run([sys.executable, "-m", "pvz_ize", "run", str(fixture), "--json"])
        rs, r = run([str(RUST), "--slice", "simple"],
                    stdin=fixture.read_text(encoding="utf-8"))
        comparison = {
            "python_exit_ok": bool(p) and py.returncode in (0, 2),
            "rust_exit_ok": rs.returncode == 0,
            "winner_match": bool(p and r and p.get("winner") == r.get("winner")),
            "reason_match": bool(p and r and p.get("reason") == r.get("reason")),
            "frame_match": bool(p and r and p.get("frames") == r.get("frames")),
        }
        rows.append({"fixture": str(fixture),
                     "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                     "python": {"exit_status": py.returncode, "compact": compact(p), "stdout": py.stdout, "stderr": py.stderr},
                     "rust": {"exit_status": rs.returncode, "compact": compact(r), "stdout": rs.stdout, "stderr": rs.stderr},
                     "comparison": comparison})
    artifact = {"schema": "pvz-ize/rust-phase11-fixtures/v1", "rust_binary": str(RUST), "fixtures": rows}
    out = ROOT / "docs" / "rust_phase11_comparison.latest.json"
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    return 0 if all(all(row["comparison"].values()) for row in rows) else 2
if __name__ == "__main__": raise SystemExit(main())
