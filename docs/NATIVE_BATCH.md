# 可选 Rust 批量协调器

`pvz_ize` 的游戏规则和 `Simulator` 仍由 Python 维护。`native_batch/` 是一个可选的 Rust 进程协调器：它启动固定数量的持久 Python worker，把独立的随机轮次分发给 worker，再按 `run_index` 排序汇总。这样不会产生第二套不一致的游戏规则；未构建 Rust 二进制时，Python API 自动回退到现有 `ProcessPoolExecutor` 实现。

## 构建

```bash
cargo build --release --manifest-path native_batch/Cargo.toml
```

生成：`native_batch/target/release/pvz-ize-native-batch`。

## Python API

```python
from pvz_ize.native_batch import run_batch_rust
result = run_batch_rust(scenario_dict, workers=4)
```

函数返回与 `run_batch_parallel` 相同的批量结果结构；`backend` 字段为 `rust-coordinator-python-workers`。如果二进制不存在，会透明回退到 Python 并行实现。

## CLI

```bash
pvz-ize run examples/v2_random.json --runs 100 \
  --workers 4 --backend rust --json
```

带 `--trace` 或 `--dump-initial` 时 CLI 保持串行路径，以保证事件和可重放初态的顺序。Rust 协调器不是完整 Rust 引擎重写；其作用是复用 Python 规则并减少父进程调度开销。
