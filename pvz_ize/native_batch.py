"""Optional Rust-coordinated batch execution.

The Rust binary only schedules persistent Python simulator workers; it does not
claim to be a second game engine.  This keeps the Python simulation semantics
and public batch result schema unchanged while moving process coordination out
of the Python parent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .batch import run_batch, run_batch_parallel, run_seed, wilson_interval
from .model import parse_scenario


def native_binary() -> Path:
    override = os.environ.get("PVZ_IZE_NATIVE_BATCH")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "native_batch" / "target" / "release" / "pvz-ize-native-batch"


def native_available() -> bool:
    return native_binary().is_file()


def run_batch_rust(data: dict[str, Any], workers: int | None = None) -> dict[str, Any]:
    """Run independent replicas through the optional Rust process coordinator.

    The worker still calls the canonical :class:`Simulator` in Python, so this
    function has the same winner/result semantics as ``run_batch_parallel``.
    If the binary has not been built, it transparently uses the existing Python
    process-pool implementation.
    """
    template = parse_scenario(data)
    if template.runs <= 1:
        return run_batch(data)
    workers = min(template.runs, max(1, int(workers or (os.cpu_count() or 2))))
    binary = native_binary()
    if not binary.is_file():
        return run_batch_parallel(data, workers=workers)
    try:
        completed = subprocess.run(
            [str(binary), "--workers", str(workers), "--python", sys.executable],
            input=json.dumps(data, ensure_ascii=False, allow_nan=False),
            text=True, capture_output=True, check=False,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
    except OSError:
        return run_batch_parallel(data, workers=workers)
    if completed.returncode:
        raise RuntimeError(
            f"Rust batch coordinator failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Rust batch returned invalid JSON: {exc}") from exc
    rows = envelope.get("results")
    if not isinstance(rows, list) or len(rows) != template.runs:
        raise RuntimeError("Rust batch returned an incomplete result set")
    rows.sort(key=lambda row: int(row["index"]))
    counts = {winner: 0 for winner in ("plants", "zombies", "undecided")}
    results = []
    for row in rows:
        payload = row["payload"]
        result = payload["result"]
        counts[result["winner"]] += 1
        results.append({**result, "run_index": int(payload["index"]), "seed": int(payload["seed"])})
    model = results[0]["model"]
    return {
        "batch": True, "runs": template.runs, "seed": template.seed,
        "model": model, "approximate": True,
        "warnings": results[0]["warnings"],
        "seed_strategy": "signed_int64_wrap(base_seed + zero_based_run_index)",
        "probability_basis": "empirical fraction of all runs; undecided runs are included in denominator",
        "outcomes": {
            winner: {"count": count, "probability": count / template.runs,
                     "wilson_95": wilson_interval(count, template.runs)}
            for winner, count in counts.items()
        },
        "results": results,
        "parallel_workers": int(envelope.get("parallel_workers", workers)),
        "backend": "rust-coordinator-python-workers",
    }
