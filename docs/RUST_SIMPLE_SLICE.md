# Rust 第一垂直切片

`native_sim` 当前包含一个**不接入默认后端**的极简切片：普通/寒冰豌豆、普通僵尸、固定 tick、直线投射物、命中扣血、普通啃食、坚果/高坚果默认血量、窝瓜一次性近战、寒冷减速和脑子结算。坐标与速度在核心内部使用 1/1000 像素定点整数，JSON 边界仍输出浮点，避免长局累计浮点误差。

构建并运行十一份固定 Python/Rust 差分夹具：

```sh
cargo build --release --manifest-path native_sim/Cargo.toml
python3 scripts/diff_rust_simple.py \
  examples/rust_slice_pea.json examples/rust_slice_bite.json \
  examples/rust_slice_empty.json examples/rust_slice_nuts.json \
  examples/rust_slice_squash.json examples/rust_slice_ice.json \
  examples/rust_slice_repeater.json examples/rust_slice_digger.json \
  examples/rust_slice_armor_helmet.json examples/rust_slice_armor_shield.json \
  examples/rust_slice_ladder.json examples/rust_slice_hypnotized.json
```

当前十一份均应输出 `status: "match"` 并以退出码 0 结束：

- `rust_slice_pea.json`：豌豆命中普通僵尸；
- `rust_slice_bite.json`：普通僵尸啃食植物并吃掉脑子；
- `rust_slice_empty.json`：无植物、初始死亡僵尸，植物立即清场；
- `rust_slice_nuts.json`：坚果默认血量和啃食；
- `rust_slice_squash.json`：窝瓜一次性近距离击杀；
- `rust_slice_ice.json`：寒冰豌豆的减速状态。
- `rust_slice_repeater.json`：双发豌豆的两枚投射物。
- `rust_slice_digger.json`：矿工地下两帧后出土。
- `rust_slice_armor_helmet.json`：普通豌豆先扣除铁桶僵尸的帽子耐久，再扣本体。
- `rust_slice_armor_shield.json`：普通豌豆先扣除铁门僵尸的盾牌耐久，再扣本体。
- `rust_slice_ladder.json`：带梯僵尸在坚果前放置梯子。
- `rust_slice_hypnotized.json`：魅惑僵尸转为友方，向右行走并离场，不啃食植物或脑子。

护甲顺序与 Python `Simulator.damage` 一致：普通投射物先消耗
`shield_hp`，剩余伤害再消耗 `helmet_hp`，最后作用于 `hp`；每层耐久降到零时
记录一个 `armor_lost` 事件。绕过护甲的 `bypass`/`both` 攻击、火豌豆和多目标
机制尚未纳入本切片。

魅惑僵尸的友方移动与终局排除已迁移；友方与敌方僵尸之间的相互攻击、
魅惑持续时间及魅惑菇触发过程仍由 Python `Simulator` 处理。

该参考实现只覆盖上述固定切片；完整 Python `Simulator` 仍是行为 oracle，复杂植物、特殊僵尸和动画尚未迁移。
