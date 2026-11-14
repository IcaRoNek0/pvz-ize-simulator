"""Independent seeded replicates and empirical, nonconditional winner probabilities."""

from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor
import math
import multiprocessing

from .engine import Simulator
from .model import parse_scenario


def run_seed(seed, index):
    """A documented wraparound sequence in the accepted signed 64-bit seed range."""
    return (seed + index + 2**63) % 2**64 - 2**63


def wilson_interval(count, total):
    """95% Wilson score interval; these are simulation samples, not game certainty."""
    z = 1.959963984540054
    p = count / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def run_batch(data, event_sink=None, initial_sink=None):
    """Reparse each replicate so omitted random initial fields are sampled afresh.

    Explicit cooldowns and other initial values remain fixed. Event streams carry a
    zero-based run_index and seed. Full per-run initial states can be streamed to a
    replay manifest without retaining every state in memory.
    """
    template = parse_scenario(data)
    counts = {winner: 0 for winner in ("plants", "zombies", "undecided")}
    runs = []
    for index in range(template.runs):
        seed = run_seed(template.seed, index)
        replica = deepcopy(data)
        replica.update(seed=seed, runs=1)
        initial = parse_scenario(replica)
        if initial_sink:
            initial_sink({"run_index": index, "seed": seed, "scenario": initial.to_dict()})
        def sink(event):
            if event_sink:
                event_sink({**event, "run_index": index, "seed": seed})
        result = Simulator(initial, event_sink=sink if event_sink else None).run()
        counts[result["winner"]] += 1
        runs.append({**result, "run_index": index, "seed": seed})
    return {
        "batch": True, "runs": template.runs, "seed": template.seed,
        "model": result["model"], "approximate": True,
        "warnings": result["warnings"],
        "seed_strategy": "signed_int64_wrap(base_seed + zero_based_run_index)",
        "probability_basis": "empirical fraction of all runs; undecided runs are included in denominator",
        "outcomes": {winner: {"count": count, "probability": count / template.runs,
                              "wilson_95": wilson_interval(count, template.runs)}
                     for winner, count in counts.items()},
        "results": runs,
    }


def _run_replica(task):
    """Process-pool worker for independent replicas.

    The worker deliberately returns only parseable JSON-shaped values.  This
    keeps the parent process responsible for aggregation and preserves the
    exact serial result format while avoiding the GIL for large batches.
    """
    data, index = task
    template = parse_scenario(data)
    seed = run_seed(template.seed, index)
    replica = deepcopy(data)
    replica.update(seed=seed, runs=1)
    initial = parse_scenario(replica)
    result = Simulator(initial).run()
    return index, seed, initial.to_dict(), result


def run_batch_parallel(data, workers=None):
    """Run a batch in separate Python processes without changing semantics.

    Event/initial streaming is intentionally kept on :func:`run_batch`; the
    parallel path is for high-throughput winner prediction and returns the
    same outcomes/results schema.  A single worker delegates to the proven
    serial implementation.
    """
    template = parse_scenario(data)
    if template.runs <= 1:
        return run_batch(data)
    if workers is None:
        workers = min(32, template.runs)
    workers = max(1, int(workers))
    if workers == 1:
        return run_batch(data)
    tasks = [(data, index) for index in range(template.runs)]
    # ``fork`` is safe here because workers import the pure-Python simulator
    # afresh and receive immutable task dictionaries; it also makes the API
    # usable from notebooks/stdin on macOS/Linux.  Windows falls back to the
    # default spawn context and the CLI's __main__ guard remains sufficient.
    contexts = multiprocessing.get_all_start_methods()
    mp_context = (multiprocessing.get_context("fork") if "fork" in contexts else None)
    kwargs = {"max_workers": min(workers, template.runs)}
    if mp_context is not None:
        kwargs["mp_context"] = mp_context
    with ProcessPoolExecutor(**kwargs) as pool:
        rows = list(pool.map(_run_replica, tasks))
    rows.sort(key=lambda row: row[0])
    counts = {winner: 0 for winner in ("plants", "zombies", "undecided")}
    results = []
    for index, seed, initial, result in rows:
        counts[result["winner"]] += 1
        results.append({**result, "run_index": index, "seed": seed})
    model = results[0]["model"]
    return {
        "batch": True, "runs": template.runs, "seed": template.seed,
        "model": model, "approximate": True,
        "warnings": results[0]["warnings"],
        "seed_strategy": "signed_int64_wrap(base_seed + zero_based_run_index)",
        "probability_basis": "empirical fraction of all runs; undecided runs are included in denominator",
        "outcomes": {winner: {"count": count, "probability": count / template.runs,
                              "wilson_95": wilson_interval(count, template.runs)}
                     for winner, count in counts.items()},
        "results": results,
        "parallel_workers": min(workers, template.runs),
    }
