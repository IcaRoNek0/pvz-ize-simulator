# Rust simple-batch JSON schema

`native_sim --batch` accepts one version-2 scenario object on stdin. The
scenario's `runs` must be positive; `--workers` is clamped to
`1..=runs`. The command returns one JSON object with this stable envelope:

```json
{
  "batch": true,
  "runs": 2,
  "seed": 9223372036854775807,
  "model": "rust-simple-slice",
  "approximate": true,
  "seed_strategy": "signed_int64_wrap(base_seed + zero_based_run_index)",
  "parallel_workers": 2,
  "outcomes": {"undecided": {"count": 2, "probability": 1.0}},
  "results": [
    {"run_index": 0, "seed": 9223372036854775807, "result": {"winner": "undecided", "reason": "max_frames_reached", "frames": 1, "state": {}}},
    {"run_index": 1, "seed": -9223372036854775808, "result": {"winner": "undecided", "reason": "max_frames_reached", "frames": 1, "state": {}}}
  ]
}
```

`results` is always sorted by `run_index`, even though Rayon executes replicas
out of order. The Rust bridge (`pvz_ize.rust_core.run_batch_rust_core`) maps
each nested `result` to the public Python result shape and preserves the same
envelope fields (`batch`, `runs`, `seed`, `outcomes`, `results`,
`parallel_workers`). Unsupported scenarios remain on the Python fallback.

Boundary coverage is in `tests/test_rust_core_backend.py` and the Rust unit
tests: `runs=1`, worker counts larger than `runs`, and signed-64-bit seed
overflow are all checked. `scripts/compare_rust_batch.py` compares ordered
`(run_index, seed, winner, frames)` rows against the Python oracle.
