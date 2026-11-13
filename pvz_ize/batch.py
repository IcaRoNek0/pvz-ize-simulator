"""Independent seeded replicates and empirical, nonconditional winner probabilities."""

from copy import deepcopy
import math

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
