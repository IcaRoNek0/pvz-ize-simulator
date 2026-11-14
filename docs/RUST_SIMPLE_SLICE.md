# Rust 第一垂直切片

`native_sim` 当前包含一个**不接入默认后端**的极简切片：普通豌豆射手、普通僵尸、固定 tick、直线豌豆、命中扣血、普通啃食和脑子结算。坐标与速度在核心内部使用 1/1000 像素定点整数，JSON 边界仍输出浮点，避免长局累计浮点误差。

构建并运行三份固定 Python/Rust 差分夹具：

```sh
cargo build --release --manifest-path native_sim/Cargo.toml
python3 scripts/diff_rust_simple.py \
  examples/rust_slice_pea.json \
  examples/rust_slice_bite.json \
  examples/rust_slice_empty.json
```

当前三份均应输出 `status: "match"` 并以退出码 0 结束：

- `rust_slice_pea.json`：豌豆命中普通僵尸；
- `rust_slice_bite.json`：普通僵尸啃食植物并吃掉脑子；
- `rust_slice_empty.json`：无植物、初始死亡僵尸，植物立即清场。

该参考实现只覆盖上述固定切片；完整 Python `Simulator` 仍是行为 oracle，复杂植物、特殊僵尸和动画尚未迁移。
