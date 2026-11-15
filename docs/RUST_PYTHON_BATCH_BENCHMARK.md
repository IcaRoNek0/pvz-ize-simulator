# Rust/Python batch benchmark

The reproducible benchmark compares the same supported simple-slice fixture through
Python `run_batch_parallel` and the native Rust `--batch` Rayon entry. Both
measurements include backend setup and process startup; no warmup or startup
subtraction is applied.

```sh
cargo build --release --manifest-path native_sim/Cargo.toml
python3 scripts/benchmark_rust_vs_python_batch.py \
  examples/rust_batch_simple.json --runs 100 --workers 4 --repeats 5 \
  --out docs/rust_python_batch_benchmark.latest.json
```

The checked run recorded `status=match` for all 100 ordered
`(run_index, seed, winner, frames)` rows on every repetition. The latest recorded median wall time was 0.014444 s for Python ProcessPool and 0.003418 s for Rust Rayon (4.23x median speedup). The first Rust repetition was 0.518 s because it included a
cold process/build-cache effect; it remains in the report rather than being
hidden. This measures only the migrated simple slice and does not justify
making Rust the default for unsupported mechanics.
