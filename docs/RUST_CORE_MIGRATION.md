# Rust Simulator 核心迁移路线

## 目标

把 `pvz_ize.engine.Simulator` 迁移到 Rust，同时保留 Python 实现作为参考模型和 fallback。迁移不是只替换进程调度器；Rust 核心必须能独立解析场景、逐帧运行并输出与 Python 相同的 winner、frames、终态和关键事件。

## 并发边界

- 单局内部帧之间存在因果依赖，不能简单并行化帧更新。
- 独立 seed 的对局可以用 `rayon::par_iter` 并行。
- 输出按 `run_index` 排序，避免线程完成顺序影响可重放结果。
- 随机数流必须按 `base_seed + run_index` 固定分配，不能共享一个全局 RNG。

建议的数据布局为 SoA（植物、僵尸、投射物分别存储字段数组），并将目标筛选、碰撞矩形和死亡实体 compaction 放在每帧的明确阶段。这样可以减少 Python 对象和哈希/生成器开销，但必须先通过差分测试。

## 分阶段验收门

1. **输入层**：Rust `serde` 解析 version 2 场景，拒绝未知字段、非法行列和不支持单位。
2. **最小核心**：普通植物/普通僵尸、脑子结算、帧上限；固定 fixture 的 winner/frames/终态一致。
3. **战斗层**：投射物、啃食、护甲、同格僵尸；事件序列一致。
4. **特殊层**：矿工、撑杆、梯子、钉耙、魅惑、植物头僵尸等逐类加入。
5. **批量层**：Rayon 并行独立 seed，和 Python oracle 比较所有 run 的 winner；再比较终态字段。
6. **性能门**：在同一机器、同一场景、同一 runs/workers 下，Rust 单线程和 Rayon 结果均须正确；性能不得以减少模拟规则或跳过事件换取。

运行当前基线：

```bash
python3 scripts/benchmark_backends.py examples/v2_random.json \
  --runs 100 --workers 4 --json
```

当前 Python ProcessPool 是默认高速后端；现有 Rust coordinator 只负责调度 Python worker，不能代表完整 Rust 核心性能。完整 Rust 核心通过全部差分门后再接入 `--backend rust-core`，未验证前不替换默认后端。

## 当前 vertical slice 基准

当前 `native_sim --slice simple` 已迁移一个可验证的最小闭环：豌豆射手/寒冰豌豆、普通僵尸、直线投射物、固定 4 帧啃食、坚果/高坚果默认血量、窝瓜一次性攻击、减速状态与脑子结算。它不代表完整 `Simulator`，只能用专用基准比较同一小契约：

```bash
cargo build --release --manifest-path native_sim/Cargo.toml
python3 scripts/benchmark_rust_slice.py \
  examples/rust_slice_benchmark.json --runs 100 --workers 4 \
  --out docs/benchmark_rust_slice.latest.json
```

最近一次 100 轮结果（独立场景、4 workers）写入
`docs/benchmark_rust_slice.latest.json`；该文件是可重跑的证据，不把一次机器时延写死在路线文档中。当前运行仍验证 100/100 winner 与 Python oracle 一致。

该数字包含每轮启动 Rust 子进程的开销；未来完整 Rust 核心应改为单进程批量/Rayon 调度后再重新测量。此 slice 仍未接入生产默认后端。

### Rust/Rayon 批量入口（simple slice）

`native_sim --batch` 在已通过差分门的 simple slice 上并行执行独立轮次；每轮
使用有符号 64 位环绕种子 `base_seed + run_index`，结果按 `run_index` 排序。
它不改变 Python 默认后端，也不覆盖事件流或未迁移机制；复杂场景仍由 Python
batch/fallback 处理。构建并检查批量顺序与 Python winner/frames 投影：

```sh
cargo build --release --manifest-path native_sim/Cargo.toml
python3 scripts/compare_rust_batch.py examples/rust_batch_simple.json --workers 2
python3 scripts/benchmark_rust_simple_batch.py examples/rust_batch_simple.json --runs 20 --workers 2
```

差分报告写入 `docs/rust_batch_comparison.latest.json`；单元测试覆盖 worker
数限制、种子溢出和稳定排序。这只证明当前 simple slice 的批量调度契约，不能
据此宣称完整 `Simulator` 已 Rust 等价。

`pvz_ize run --backend rust-core --runs N --workers W` 在该二进制支持批量入口
时复用同一个 Rayon 进程；旧版二进制仍自动退回逐轮子进程路径。

## 可选 Rust 后端

`pvz-ize run/predict --backend rust-core` 仅调度已通过差分门的切片单位（包括钉耙、梯子、土豆雷、延迟樱桃炸弹和同排火爆辣椒）；不满足支持门（例如玉米炮弹、未迁移僵尸，或省略射击植物的初始 `cooldown`）时使用 Python `Simulator`，不会套用错误规则。默认后端仍是 Python。

### Phase 9：延迟爆炸与同排灼烧

- `cherry_bomb`：激活延迟 100 tick，在自身及相邻行的 115px 范围内造成 1800 点伤害。
- `jalapeno`：激活延迟 100 tick，消灭同排敌方僵尸并清除该行梯子。
- 樱桃炸弹固定夹具：`examples/rust_phase9_cherry_bomb.json`，比较脚本：
  `scripts/compare_phase9_fixtures.py`，报告：
  `docs/rust_phase9_comparison.latest.json`。
- 火爆辣椒基础夹具：`examples/rust_slice_jalapeno.json`，使用
  `scripts/diff_rust_simple.py` 做完整终态差分。

这些夹具要求 Python/Rust 的 winner、reason、frames 和可比较的终态投影一致；尚未迁移的动画随机性、玉米加农炮弹道、礼盒和僵王继续走 Python fallback。

可重复运行 guarded backend 基准：

```sh
python3 scripts/benchmark_rust_core.py \
  examples/rust_slice_repeater.json examples/rust_slice_potato_mine.json \
  examples/rust_slice_hypnotized.json --runs 20 --workers 4 \
  --out docs/benchmark_rust_core.latest.json
```

当前报告只证明 winner 与 Python oracle 一致；每次启动 Rust 子进程的切片基准不代表完整 Rust 引擎性能，且可能慢于 Python 进程池。完成单进程批量/Rayon 核心后才能重新评估速度。

### Phase 11：地刺与地刺王

`spikeweed` 与 `spikerock` 已加入 Rust slice：它们不会成为啃食目标，重叠僵尸后进入攻击计时；地刺在 75 tick 脉冲一次，地刺王在 70/32 tick 脉冲两次，伤害绕过铁门盾牌但保留头盔吸收。固定夹具为 `examples/rust_phase11_spikeweed.json` 与 `examples/rust_phase11_spikerock.json`，由 `scripts/compare_phase11_fixtures.py` 写入 `docs/rust_phase11_comparison.latest.json`。当前 gate 比较 winner、reason、frames 与关键终态字段；事件名称仍保留用于后续逐帧校准。

### Phase 12：基础护甲默认值

Rust slice 现在与 `catalog.ZOMBIES` 对齐三种基础护甲僵尸：`conehead`（本体
270、头盔 370）、`buckethead`（本体 270、头盔 1100）和 `screen_door`
（本体 270、盾牌 1100）。普通投射物严格按盾牌、头盔、本体的顺序扣除，保留
`armor_lost` 事件；动画与移动机制未在本阶段改动。默认值及跨层顺序夹具为：
`examples/rust_phase12_conehead_defaults.json`、
`examples/rust_phase12_buckethead_defaults.json`、
`examples/rust_phase12_screen_door_defaults.json`、
`examples/rust_phase12_armor_order.json`，可用
`scripts/compare_phase12_fixtures.py` 运行 Python/Rust 差分并写入
`docs/rust_phase12_comparison.latest.json`。

`pvz_ize.rust_core.SUPPORTED_ZOMBIES` 同步扩展为允许这三种单位通过 Rust
后端支持门；不满足其他切片条件的场景仍回退 Python。

### Phase 13：橄榄球僵尸基础默认值

Rust simple slice now accepts `football` through the guarded backend gate and
uses the catalog defaults that are observable without animation: body HP 270,
helmet HP 1400, and speed 0.32 px/tick. The existing straight projectile
pipeline is exercised by `examples/rust_phase13_football_defaults.json`; one
pea hit consumes 20 helmet HP (1400 → 1380) and leaves body HP at 270. No
football charge animation or special movement state is claimed. Run
`python3 scripts/compare_phase13_fixtures.py` to regenerate
`docs/rust_phase13_comparison.latest.json`; unsupported scenarios retain the
Python fallback.

### Phase 14：报纸僵尸基础默认值

Rust simple slice now accepts `newspaper` with catalog defaults: body HP 270,
shield HP 150, and speed 0.09 px/tick. The guarded scope covers ordinary
projectile shield damage only; the reading/maddening/rage animation state
machine remains in Python. Fixtures `examples/rust_phase14_newspaper_defaults.json`
and `examples/rust_phase14_newspaper_armor_order.json` are checked by
`scripts/compare_phase14_fixtures.py` and recorded in
`docs/rust_phase14_comparison.latest.json`.

The additional `rust_phase14_newspaper_shield_break.json` audit fixture uses a
20-HP shield so one ordinary pea breaks it. Rust records `armor_lost`, leaves
body HP unchanged, and keeps the catalog speed (0.09) for this one-tick slice.
The Python oracle then transitions the full model through
`newspaper_maddening` and eventually speed 0.4; that animation/state-machine
behavior is intentionally not implemented here. Scenarios whose result depends
on that transition must continue through the Python fallback.

### Phase 15：小鬼僵尸基础默认值

Rust simple slice now accepts `imp` with catalog defaults: body HP 70 and
speed 0.423 px/tick. Its ordinary walk and straight pea projectile path are
covered by `examples/rust_phase15_imp_defaults.json` and
`examples/rust_phase15_imp_projectile.json`, checked by
`scripts/compare_phase15_fixtures.py` and recorded in
`docs/rust_phase15_comparison.latest.json`. The Python model's giant-triggered
`imp_thrown`/`imp_landing` phases are deliberately not represented in the Rust
schema (which has no phase/altitude fields); those animation and throw paths
continue through the Python fallback rather than being approximated.

### Phase 16：玉米加农炮安全状态边界

The existing `[col, col+1]` footprint is extended with one verifiable state:
the Rust slice applies the catalog's 500-tick COB arming/reload counter. The
fixture `examples/rust_phase16_cob_arming.json` observes one deterministic
tick (`500 → 499`) with no projectile or splash event. Target selection,
parabolic lob, impact timing, and 115px adjacent-row damage remain explicitly
outside this slice; scenarios that could reach a shot stay on the Python
fallback. Run `python3 scripts/compare_phase16_fixtures.py` to write
`docs/rust_phase16_comparison.latest.json`.

### Phase 18：撑杆僵尸安全步行边界

The guarded slice normalizes pole-vaulting defaults: body HP 500, speed 0.32 px/tick while the pole is carried, and 0.143 after the tool is spent. `examples/rust_phase18_pole_defaults.json` and `examples/rust_phase18_pole_projectile.json` exercise ordinary movement and direct pea damage. A carried pole approaching a same-row plant is rejected by the support gate because `pole_running`/`pole_jumping` collision and landing phases are not represented in `SimpleState`; those scenarios continue through the Python fallback.

### Phase 19：旗帜僵尸基础速度

The Rust simple slice accepts `flag` with catalog walk speed 0.22 px/tick and reuses the straight pea path. `examples/rust_phase19_flag_defaults.json` is checked by `scripts/compare_phase19_fixtures.py`; flag animation is not asserted equivalent.

### Phase 21：三线射手与冰车僵尸安全切片

`threepeater` emits one straight pea into each valid adjacent row (one, two, or three projectiles at board edges). `zamboni` is limited to catalog default HP/speed and movement when no plant target or machine interaction is present. The fixtures `examples/rust_phase21_threepeater.json` and `examples/rust_phase21_zamboni_defaults.json` are checked by `scripts/compare_phase21_fixtures.py`; ice trails, crushing, and other animation-driven behavior remain Python fallback.

### Phase 22：钉耙与梯子僵尸对象交互

The Rust slice has guarded differentials for a pre-placed rake consuming the first overlapping hostile zombie and a ladder zombie placing its ladder on a wallnut. `examples/rust_migration_rake.json` and `examples/rust_migration_ladder.json` are checked by `scripts/compare_phase22_fixtures.py` and recorded in `docs/rust_phase22_comparison.latest.json`. Pre-placed ladder objects and ladder traversal animation remain Python fallback.
