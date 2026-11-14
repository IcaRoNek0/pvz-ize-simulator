# Rust 第一垂直切片

`native_sim` 当前包含一个**不接入默认后端**的极简切片：普通/寒冰豌豆、普通僵尸、固定 tick、直线投射物、命中扣血、普通啃食、坚果/高坚果默认血量、窝瓜一次性近战、土豆雷、樱桃/辣椒瞬发、地刺/地刺王、寒冷减速和脑子结算。坐标与速度在核心内部使用 1/1000 像素定点整数，JSON 边界仍输出浮点，避免长局累计浮点误差。

构建并运行十六份固定 Python/Rust 差分夹具：

```sh
cargo build --release --manifest-path native_sim/Cargo.toml
python3 scripts/diff_rust_simple.py \
  examples/rust_slice_pea.json examples/rust_slice_bite.json \
  examples/rust_slice_empty.json examples/rust_slice_nuts.json \
  examples/rust_slice_squash.json examples/rust_slice_ice.json \
  examples/rust_slice_repeater.json examples/rust_slice_digger.json \
  examples/rust_slice_armor_helmet.json examples/rust_slice_armor_shield.json \
  examples/rust_slice_ladder.json examples/rust_slice_hypnotized.json \
  examples/rust_slice_who_will_win_row_scope.json \
  examples/rust_slice_cob_cannon_footprint.json \
  examples/rust_slice_potato_mine.json examples/rust_migration_cherry_bomb.json
```

当前十六份均应输出 `status: "match"` 并以退出码 0 结束：

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
- `rust_slice_who_will_win_row_scope.json`：`who_will_win` 模式只检查第三行；仅第二行僵尸时第 0 帧植物胜利。
- `rust_slice_cob_cannon_footprint.json`：玉米加农炮保留 `[col, col+1]` 双格占位。
- `rust_slice_potato_mine.json`：土豆雷在同一行接触后爆炸，击杀该行僵尸并销毁自身。
- `rust_migration_cherry_bomb.json`：樱桃炸弹延迟爆炸并击中相邻范围内僵尸。
- `rust_phase11_spikeweed.json`：地刺接触后等待 25 tick，在 timer=75 脉冲；僵尸不会啃食地刺。
- `rust_phase11_spikerock.json`：地刺王在 timer=70、32 各脉冲一次；脉冲绕过铁门盾但仍消耗头盔耐久，僵尸不会啃食地刺王。

Phase 12 additionally migrates the base armor defaults for `conehead`,
`buckethead`, and `screen_door` (all retain 270 body HP): conehead has 370
helmet HP, buckethead has 1100 helmet HP, and screen-door has 1100 shield HP.
The projectile damage pipeline remains ordered `shield_hp -> helmet_hp -> hp`;
the four default/order fixtures can be checked with the existing differential
harness:

```sh
python3 scripts/compare_phase12_fixtures.py
```

The Rust backend support gate now admits these three zombie types.  No
animation or movement mechanism is changed by this phase.

Phase 13 adds the football zombie's observable catalog defaults to the simple
slice: 270 body HP, 1400 helmet HP, and 0.32 px/tick speed. The straight pea
projectile path uses the existing `shield_hp -> helmet_hp -> hp` order; the
football fixture records a direct hit that reduces its helmet to 1380 while
leaving body HP unchanged. Football charge/animation state is intentionally
not migrated. Run the guarded differential with:

```sh
python3 scripts/compare_phase13_fixtures.py
```

The report is written to `docs/rust_phase13_comparison.latest.json`, and
scenarios outside the support gate continue to use the Python fallback.

Phase 16 audits the two-cell COB cannon state. The Rust slice preserves the
500-tick arming/reload counter and decrements it deterministically (the
fixture observes 500 → 499) without claiming the mouse-targeted lob, splash,
or impact geometry. Scenarios that could reach a shot remain on the Python
fallback. Run:

```sh
python3 scripts/compare_phase16_fixtures.py
```

The guarded report is written to `docs/rust_phase16_comparison.latest.json`.

The native binary also exposes a guarded batch mode for this migrated slice:

```sh
python3 scripts/compare_rust_batch.py examples/rust_batch_simple.json --workers 2
```

`--batch` uses a local Rayon pool, wraps the signed 64-bit seed per
`run_index`, and sorts results before serializing. It is an optional accelerator
for the tested simple contract only; Python remains the fallback for unsupported
plants, zombies, animations, and event-stream features.

Phase 19 adds the flag zombie's deterministic catalog speed (0.22 px/tick)
to the guarded Rust unit set. Its ordinary walk and straight pea damage are
covered by `examples/rust_phase19_flag_defaults.json`; no flag animation
equivalence is claimed. Run `python3 scripts/compare_phase19_fixtures.py` to
write `docs/rust_phase19_comparison.latest.json`.

Phase 18 covers pole-vaulting defaults and direct damage only; a carried pole
near a same-row plant remains gated to Python because jump/landing state is not
in the Rust schema. Phase 20 covers the pre-placed rake and ladder-zombie
placement paths with `scripts/compare_phase20_fixtures.py`; ladder traversal and
pre-placed ladder animation remain Python.

Phase 15 adds the imp's observable catalog defaults (70 HP, 0.423 px/tick),
ordinary movement, and direct pea projectile damage. Imp throwing and landing
animation remains Python because the Rust simple state has no phase/altitude
representation; run `python3 scripts/compare_phase15_fixtures.py` for both
guarded fixtures.

Phase 14 adds the newspaper zombie's catalog defaults (270 body HP, 150 shield
HP, 0.09 px/tick). The reading/rage animation state machine remains Python;
run `python3 scripts/compare_phase14_fixtures.py` for the guarded defaults,
shield-order, and one-tick shield-break audit fixtures. A broken shield does
not claim the Python model's later `newspaper_maddening`/rage speed transition.

Phase 11 固定夹具可单独运行 Python/Rust 对照（Rust 从 stdin 读取场景）：

```sh
cargo build --release --manifest-path native_sim/Cargo.toml
python3 scripts/compare_phase11_fixtures.py
```

脚本写入 `docs/rust_phase11_comparison.latest.json`，并比较终局以及地刺专用的
植物状态、僵尸 HP/头盔和 `damage`/脉冲事件投影；退出码 0 才表示两份夹具均通过。

护甲顺序与 Python `Simulator.damage` 一致：普通投射物先消耗
`shield_hp`，剩余伤害再消耗 `helmet_hp`，最后作用于 `hp`；每层耐久降到零时
记录一个 `armor_lost` 事件。绕过护甲的 `bypass`/`both` 攻击、火豌豆和多目标
机制尚未纳入本切片。

魅惑僵尸的友方移动与终局排除已迁移；友方与敌方僵尸之间的相互攻击、
魅惑持续时间及魅惑菇触发过程仍由 Python `Simulator` 处理。

`who_will_win` 的第三行终局谓词已迁移；其他模式仍使用全场敌对僵尸终局谓词。

Rust 输入解析器会拒绝 `cob_cannon` 放在第 9 列，并在 `Plant.footprint` 输出左右两格；
当前仅迁移占位不含玉米炮弹攻击。

土豆雷切片采用已验证的简单接触范围（同一行、植物中心右侧 55 像素内）；复杂地下、撑杆
和跳跳僵尸的特殊触发条件仍由 Python `Simulator` 处理。

该参考实现只覆盖上述固定切片；完整 Python `Simulator` 仍是行为 oracle，复杂植物、特殊僵尸和动画尚未迁移。
