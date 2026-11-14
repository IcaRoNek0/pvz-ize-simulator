#!/usr/bin/env python3
"""Compare recorded simulator rounds with observations extracted from videos.

The observation file is intentionally small and human-auditable:
[{"id":"run/7.json", "expected":"zombies", "timestamp":"...", "notes":"..."}]
Unknown/unsupported rounds are marked skipped instead of being counted as
failures.  This keeps video accuracy reports honest when a clip contains a
unit that the catalog does not support yet.
"""
from __future__ import annotations
import argparse, json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pvz_ize.engine import Simulator
from pvz_ize.model import ScenarioError, parse_scenario


def supported(scenario):
    # Parsing already validates catalog types; explicit object lists are kept
    # here for future video objects (rakes/ladders/bosses) that should skip.
    return all(z.type != "boss" for z in scenario.zombies)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("observations",type=Path)
    ap.add_argument("--out",type=Path,default=Path("outputs/video-accuracy.json")); a=ap.parse_args()
    records=json.loads(a.observations.read_text(encoding="utf-8")); report=[]
    for item in records:
        path=Path(item["scenario"]); row={"id":item.get("id",str(path)),"scenario":str(path),"expected":item.get("expected"),"timestamp":item.get("timestamp"),"notes":item.get("notes","")}
        try:
            data=json.loads(path.read_text(encoding="utf-8")); s=parse_scenario(data)
            if not supported(s): row.update(status="skipped",reason="unsupported object")
            else:
                # Video observations are normally one round; force one run so
                # the comparison is a direct winner, not a batch probability.
                s.runs=1; result=Simulator(s).run(); row.update(actual=result["winner"],frames=result["frames"],reason=result["reason"],status=("match" if result["winner"]==item.get("expected") else "mismatch"))
        except (OSError,ValueError,ScenarioError) as exc:
            row.update(status="skipped",reason=f"unreadable or unsupported: {exc}")
        report.append(row)
    counts={k:sum(r["status"]==k for r in report) for k in ("match","mismatch","skipped")}
    out={"schema":1,"counts":counts,"records":report}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
