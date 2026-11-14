# Python/Rust 差分验证

`scripts/diff_rust_python.py` 是迁移期间的验收门。它对同一个场景分别运行
Python `Simulator` 和 Rust 核心，并比较：

- `winner`、`reason`、`status`、`frames`；
- 脑子、植物、僵尸的终态数组（包括同格实体，不去重）；
- 飞行物、特殊状态、梯子和事件计数。

Rust 可执行文件协议很小：从 stdin 读取一个 JSON 场景对象，向 stdout 写一个
JSON 结果对象（也可包在 `{ "result": ... }` 中），诊断只能写 stderr。Rust
二进制不存在时脚本返回退出码 3；存在但结果不同返回 2；只有所有记录完全
一致才返回 0。这样“Rust 还没实现”不会被误报为通过。

```sh
# 构建迁移中的核心
cargo build --release --manifest-path native_sim/Cargo.toml

# 比较完整终态（Rust 核心尚未完成时应返回 mismatch）
python3 scripts/diff_rust_python.py \
  examples/plants_win.json examples/zombies_win.json \
  --rust-binary native_sim/target/release/pvz-ize-native-sim \
  --out docs/rust-diff.latest.json

# 比较当前已迁移的状态边界（Phase 1 smoke fixture）
python3 scripts/diff_rust_python.py examples/rust_core_smoke.json \
  --profile core --rust-binary native_sim/target/release/pvz-ize-native-sim
```

当前 `native_sim` 仍处于输入/移动边界阶段，尚未实现完整战斗规则；因此其与
Python 的完整终态差分失败是预期的迁移信号，不应接入默认后端。`--profile core`
用于先验收已迁移的数据/状态边界；`rust_core_smoke.json` 当前应通过，
`rust_core_motion.json` 会暴露尚未统一的终局命名差异。每迁移一个行为模块，
先补固定场景，再运行对应 profile，直到终态投影完全一致后才合并到高速后端。
