# Rust 第一垂直切片

`native_sim` 目前包含一个**不接入默认后端**的极简切片：普通豌豆射手、普通僵尸、固定 tick、直线豌豆、命中扣血、普通啃食和脑子结算。它不代表完整 PvZ 规则。

构建并运行差分门：

```sh
cargo build --release --manifest-path native_sim/Cargo.toml
python3 scripts/diff_rust_simple.py examples/rust_slice_pea.json
```

只有 Rust 输出与固定 Python slice reference 完全一致时退出码才为 0。完整 Python `Simulator` 仍是行为 oracle；复杂植物、特殊僵尸和动画尚未迁移。
