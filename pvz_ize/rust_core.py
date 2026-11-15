"""Optional bridge to the migrated Rust vertical-slice core.

The bridge is deliberately conservative: it only dispatches scenarios whose
plants/zombies are covered by the Rust differential fixtures.  Everything else
falls back to the Python ``Simulator`` instead of silently applying an
incomplete rule set.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from .batch import run_seed, wilson_interval

SUPPORTED_PLANTS = {"peashooter", "repeater", "snow_pea", "threepeater", "split_pea", "fume_shroom", "pumpkin", "wallnut", "tallnut", "squash", "potato_mine", "cherry_bomb", "jalapeno", "spikeweed", "spikerock", "cob_cannon"}
SUPPORTED_ZOMBIES = {
    "normal", "digger", "ladder", "conehead", "buckethead", "screen_door", "football", "newspaper", "imp", "pole_vaulting", "flag", "zamboni", "balloon", "pogo",
}


def rust_core_binary() -> Path:
    override = os.environ.get("PVZ_IZE_RUST_CORE")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "native_sim" / "target" / "release" / "pvz-ize-native-sim"


def rust_core_available() -> bool:
    binary = rust_core_binary()
    return binary.is_file() and os.access(binary, os.X_OK)


def supports_scenario(data: dict[str, Any]) -> bool:
    """Return true only for the exact rules currently covered by Rust diffs."""
    if data.get("mode", "ize") not in {"ize", "who_will_win"}:
        return False
    if data.get("time_limit_frames") is not None or data.get("timeout_winner") not in (None, "undecided"):
        return False
    if data.get("ladders"):
        return False
    plants = data.get("plants", [])
    zombies = data.get("zombies", [])
    if not isinstance(plants, list) or not isinstance(zombies, list):
        return False
    if not all(item.get("type") in SUPPORTED_PLANTS for item in plants):
        return False
    if not all(item.get("type") in SUPPORTED_ZOMBIES for item in zombies):
        return False
    # Pole-vaulting's jump/landing state is not represented by SimpleState.
    # Permit only clear walking/projectile cases where no same-row plant is in
    # its vault approach; those cases use the catalog speed/HP defaults. Any
    # potential vault collision stays on the complete Python engine.
    for zombie in zombies:
        if zombie.get("type") != "pole_vaulting":
            continue
        if zombie.get("tool", True) is False:
            continue
        zx = zombie.get("x")
        if zx is None:
            zx = 10.0 + 80.0 * (int(zombie.get("col", 7)) - 1)
        zrow = int(zombie.get("row", 3))
        for plant in plants:
            if int(plant.get("row", 3)) != zrow or plant.get("type") in {"spikeweed", "spikerock"}:
                continue
            px = 40.0 + 80.0 * (int(plant.get("col", 1)) - 1)
            if abs(float(zx) - px) <= 180.0:
                return False
    for zombie in zombies:
        if zombie.get("type") == "zamboni" and plants:
            # The machine's tire-crush/ice-trail scheduler is not in the
            # simple state. Keep all board interactions on Python; a
            # no-plant row is a deterministic catalog-speed walk only.
            return False
        if zombie.get("type") == "balloon" and zombie.get("tool", True):
            # Flying/popping phases are animation-driven and have distinct
            # targetability; only an already-popped balloon may use this slice.
            return False
        if zombie.get("type") == "pogo" and zombie.get("tool", True):
            # Bouncing/landing and nut-blocking phases require altitude and
            # phase timers absent from SimpleState; spent pogo sticks walk.
            return False
    # The Rust slice currently verifies only COB's two-cell footprint and
    # arming/reload counter.  Keep targeted lob/splash combat on Python until
    # its projectile contract has a differential fixture.
    cob_plants = [item for item in plants if item.get("type") == "cob_cannon"]
    if cob_plants and zombies:
        max_frames = int(data.get("max_frames", 100_000))
        for item in cob_plants:
            if "cooldown" not in item:
                return False
            try:
                cooldown = int(item["cooldown"])
            except (TypeError, ValueError):
                return False
            if cooldown <= max_frames:
                return False
    # Python samples an initial firing cooldown when it is omitted.  The Rust
    # slice has no equivalent random wind-up, so only explicitly seeded
    # shooter cooldowns may cross the backend boundary.
    for item in plants:
        if item.get("type") in {"peashooter", "repeater", "snow_pea", "threepeater", "split_pea", "fume_shroom"} and "cooldown" not in item:
            return False
    return True


def _public_result(raw: dict[str, Any], elapsed: float) -> dict[str, Any]:
    state = raw.get("state", {})
    zombies = state.get("zombies", [])
    active_hostile = sum(1 for z in zombies if z.get("status") == "active" and z.get("hp", 0) > 0 and not z.get("hypnotized"))
    active_friendly = sum(1 for z in zombies if z.get("status") == "active" and z.get("hp", 0) > 0 and z.get("hypnotized"))
    return {
        "winner": raw.get("winner", "undecided"),
        "reason": raw.get("reason"),
        "frames": raw.get("frames", state.get("frame", 0)),
        "seconds": elapsed,
        "model": "rust-simple-slice",
        "approximate": True,
        "warnings": ["Rust backend covers only the migrated vertical-slice unit set; unsupported scenarios use Python fallback."],
        "plants": state.get("plants", []),
        "zombies": zombies,
        "brains": state.get("brains", []),
        "projectiles": state.get("projectiles", []),
        "events": state.get("events", {}),
        "pending_effects": [],
        "zombie_special_state": {},
        "plant_head_state": {},
        "active_hostile_zombies": active_hostile,
        "active_friendly_zombies": active_friendly,
        "ladders": state.get("ladders", []),
        "rakes": state.get("rakes", []),
        "status": "finished" if raw.get("winner") != "undecided" else "max_frames_reached",
        "backend": "rust-core-slice",
    }


def run_rust_core(data: dict[str, Any], *, binary: Path | None = None) -> dict[str, Any]:
    """Run one supported scenario through Rust and return the public result."""
    if not supports_scenario(data):
        raise ValueError("scenario is outside the migrated Rust slice")
    binary = binary or rust_core_binary()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise FileNotFoundError(f"Rust core binary not found: {binary}")
    started = time.perf_counter()
    completed = subprocess.run(
        [str(binary), "--slice", "simple"],
        input=json.dumps(data, ensure_ascii=False, allow_nan=False),
        text=True, capture_output=True, check=False,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    elapsed = time.perf_counter() - started
    if completed.returncode:
        raise RuntimeError(f"Rust core failed ({completed.returncode}): {completed.stderr.strip()}")
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Rust core returned invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Rust core result must be an object")
    return _public_result(raw, elapsed)


def run_batch_rust_core(data: dict[str, Any], workers: int | None = None) -> dict[str, Any]:
    """Run independent supported replicas concurrently through Rust.

    Newer native binaries expose one-process ``--batch``/Rayon execution.  Use
    that path first so the optional Rust backend does not pay one subprocess
    startup per replica; retain the older per-run path as a compatibility
    fallback for binaries built before the batch entry was introduced.
    """
    if not supports_scenario(data):
        raise ValueError("scenario is outside the migrated Rust slice")
    raw_runs = data.get("runs", 1)
    if isinstance(raw_runs, bool) or not isinstance(raw_runs, int) or raw_runs <= 0:
        raise ValueError("runs must be a positive integer")
    runs = raw_runs
    workers = min(runs, max(1, int(workers or (os.cpu_count() or 2))))
    binary = rust_core_binary()
    started = time.perf_counter()
    completed = subprocess.run(
        [str(binary), "--batch", "--workers", str(workers)],
        input=json.dumps(data, ensure_ascii=False, allow_nan=False),
        text=True,
        capture_output=True,
        check=False,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    if completed.returncode == 0:
        try:
            raw = json.loads(completed.stdout)
            raw_rows = raw["results"]
            if raw.get("batch") is True and len(raw_rows) == runs:
                per_run_elapsed = (time.perf_counter() - started) / max(1, runs)
                rows = []
                for row in raw_rows:
                    public = _public_result(row["result"], per_run_elapsed)
                    public.update(run_index=int(row["run_index"]), seed=int(row["seed"]))
                    rows.append(public)
                rows.sort(key=lambda row: row["run_index"])
                counts = {winner: 0 for winner in ("plants", "zombies", "undecided")}
                for row in rows:
                    counts[row["winner"]] += 1
                return {
                    "batch": True,
                    "runs": runs,
                    "seed": int(data.get("seed", 0)),
                    "model": "rust-simple-slice",
                    "approximate": True,
                    "warnings": rows[0]["warnings"] if rows else [],
                    "seed_strategy": "signed_int64_wrap(base_seed + zero_based_run_index)",
                    "probability_basis": "empirical fraction of all runs; undecided runs are included in denominator",
                    "outcomes": {
                        winner: {"count": count, "probability": count / runs,
                                 "wilson_95": wilson_interval(count, runs)}
                        for winner, count in counts.items()
                    },
                    "results": rows,
                    "parallel_workers": workers,
                    "backend": "rust-core-slice-rayon",
                }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass

    # Compatibility fallback for an older native binary or a malformed batch
    # response.  It preserves the pre-Rayon optional backend contract.
    tasks = []
    for index in range(runs):
        replica = deepcopy(data)
        replica.update(seed=run_seed(int(data.get("seed", 0)), index), runs=1)
        tasks.append(replica)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run_rust_core, tasks))
    counts = {winner: 0 for winner in ("plants", "zombies", "undecided")}
    for result in results:
        counts[result["winner"]] += 1
    return {
        "batch": True,
        "runs": runs,
        "seed": int(data.get("seed", 0)),
        "model": "rust-simple-slice",
        "approximate": True,
        "warnings": results[0]["warnings"] if results else [],
        "seed_strategy": "signed_int64_wrap(base_seed + zero_based_run_index)",
        "probability_basis": "empirical fraction of all runs; undecided runs are included in denominator",
        "outcomes": {
            winner: {"count": count, "probability": count / runs,
                     "wilson_95": wilson_interval(count, runs)}
            for winner, count in counts.items()
        },
        "results": [{**result, "run_index": index, "seed": run_seed(int(data.get("seed", 0)), index)}
                    for index, result in enumerate(results)],
        "parallel_workers": workers,
        "backend": "rust-core-slice",
    }
