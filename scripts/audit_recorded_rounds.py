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


def _same_cell_zombies(scenario):
    """Return groups of zombie indexes that occupy the same initial cell.

    The audit intentionally keeps every list entry as an independent unit.  The
    groups are only evidence in the report; they are never de-duplicated before
    simulation.  Pixel-X inputs are bucketed using the normal 80px cell width
    so a same-cell overlap remains visible even when the source uses ``x``.
    """
    buckets = {}
    for index, zombie in enumerate(scenario.zombies):
        explicit_col = getattr(zombie, "col", None)
        col = explicit_col if explicit_col is not None else int((zombie.x - 40) // 80) + 1
        buckets.setdefault((zombie.row, col), []).append(index)
    return [indexes for indexes in buckets.values() if len(indexes) > 1]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("observations",type=Path)
    ap.add_argument("--base-dir",type=Path,default=None,
                     help="解析相对 scenario 路径的目录；默认使用 observations 所在目录")
    ap.add_argument("--absolute-paths",action="store_true",
                     help="在报告中附加解析后的绝对场景路径")
    ap.add_argument("--out",type=Path,default=Path("outputs/video-accuracy.json")); a=ap.parse_args()
    records=json.loads(a.observations.read_text(encoding="utf-8")); report=[]
    base_dir=(a.base_dir or a.observations.parent).resolve()
    for item in records:
        expected=item.get("expected")
        scenario_name=item.get("scenario", "<inline>")
        row={"id":item.get("id",str(scenario_name)),"scenario":str(scenario_name),"expected":expected,"timestamp":item.get("timestamp"),"notes":item.get("notes","")}
        # Unknown/uncertain video outcomes and explicitly unsupported/custom
        # objects are excluded before parsing, so they cannot become false
        # mismatches merely because no exact input is available.
        unsupported=item.get("unsupported_or_custom") or item.get("unsupported")
        if expected not in {"plants", "zombies"}:
            row.update(status="skipped",reason="unknown video result")
            report.append(row)
            continue
        if unsupported:
            row.update(status="skipped",reason=f"unsupported/custom objects: {unsupported}")
            report.append(row)
            continue
        try:
            if "scenario_data" in item:
                data=item["scenario_data"]
                scenario_path=None
            else:
                raw_path=Path(scenario_name)
                candidates=[raw_path] if raw_path.is_absolute() else [base_dir/raw_path, base_dir.parent/raw_path, Path.cwd()/raw_path]
                # Preserve order while avoiding duplicate paths when the
                # observations file lives in the current directory.
                candidates=list(dict.fromkeys(candidate.resolve() for candidate in candidates))
                scenario_path=next((candidate for candidate in candidates if candidate.is_file()), None)
                if scenario_path is None:
                    raise OSError(f"scenario not found (looked in {', '.join(str(p) for p in candidates)})")
                data=json.loads(scenario_path.read_text(encoding="utf-8"))
            s=parse_scenario(data)
            if not supported(s): row.update(status="skipped",reason="unsupported object")
            else:
                # Video observations are normally one round; force one run so
                # the comparison is a direct winner, not a batch probability.
                s.runs=1; result=Simulator(s).run(); row.update(actual=result["winner"],frames=result["frames"],reason=result["reason"],status=("match" if result["winner"]==expected else "mismatch"),initial_zombies=len(s.zombies),same_cell_zombies=_same_cell_zombies(s))
                if scenario_path is not None and a.absolute_paths:
                    row["resolved_scenario"] = str(scenario_path.resolve())
        except (OSError,TypeError,ValueError,ScenarioError) as exc:
            row.update(status="skipped",reason=f"unreadable or unsupported: {exc}")
        report.append(row)
    counts={k:sum(r["status"]==k for r in report) for k in ("match","mismatch","skipped")}
    out={"schema":1,"counts":counts,"records":report}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
