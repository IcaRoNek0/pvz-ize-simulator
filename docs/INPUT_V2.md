# 第二轮输入与批量统计

`version: 1` 和 `version: 2` 都可读取，规范化输出使用 `version: 2`。
未知字段、错误类型、负数血量仍拒绝；不静默忽略拼写错误。
各植物 `hp`、各僵尸 `hp` / `helmet_hp` / `shield_hp` 可独立指定，
范围是零到该单位目录默认最大值。血量为零的单位不参与存活结算。

```json
{
  "version": 2,
  "seed": 2026,
  "runs": 100,
  "max_frames": 100000,
  "movement_mode": "mean",
  "brains": [3],
  "plants": [
    {"type": "garlic", "row": 3, "col": 4, "hp": 200, "garlic_direction": "up"},
    {"type": "peashooter", "row": 3, "col": 2, "hp": 123, "layer": "main"},
    {"type": "pumpkin", "row": 3, "col": 2, "layer": "shell"}
  ],
  "zombies": [
    {"type": "digger", "row": 3, "col": 7, "underground": false, "hp": 200},
    {"type": "normal", "row": 3, "col": 7, "hypnotized": true, "hp": 180}
  ]
}
```

## 新增字段

- `runs`：1 至 100000 的整数，默认 1；CLI `--runs` 可覆盖。
- `movement_mode`：`mean`（默认，均速）或 `animation`（动画轨道驱动的可选模式；具体可用单位见对齐说明）。
- `magnet_distance_mode`：`horizontal`（默认，按 init.md 要求，像素水平距离 `abs(z.hitbox_left - p.x)` 加 `80*行差`）或 `source`（Portable 源码欧氏距离加 `80*行差`，用于源码对照）。两种模式均先找场上防具/工具，再找已放梯子物品；距离公式不同可能改变优先吸取目标。
- 植物 `garlic_direction`：仅大蒜；`up` / `down` / `random`，默认随机。
- 植物 `layer`：`base` / `main` / `shell`。南瓜默认 shell，睡莲/花盆默认 base，其他默认 main。
- 顶层 `allow_stacking`：默认 false；同格不同层允许，同格同层需显式 true。允许叠种不等于模拟了原版所有种植合法性限制。
- 僵尸 `underground`：仅矿工，默认 true；false 为已经出土、向右行走，默认速度 .11。
- 僵尸 `hypnotized`：布尔，默认 false，表示初始已魅惑。
- 僵尸 `tool`：布尔，默认 true，可表示矿工镐、撑杆、跳跳杆、气球等工具的初始存在状态（各类型实现规则不同）。
- 僵尸 `frozen`、`chilled`、`buttered`：非负整数剩余逻辑帧，分别是冻结、减速、黄油定身。
- 植物/僵尸 `animation_phase`：可选，区间 [0,1)；只影响支持该入口的动画机制，不是任意原版动画存档恢复接口。
- 僵尸 `velocity_parameter`：可选正数，原版 `mVelX` 动画驱动参数，不等于每帧实际位移；输入范围 .001 至 5/.47。动画模式省略时按类型采样或使用固定值；若仅显式指定 `speed` 则用 `speed/.47` 反推，显式 velocity_parameter 优先。
- 僵尸 `walk_variant`：可选整数 0 或 1，0 选择 walk2（资源存在时），1 选择 walk；动画模式省略时随机，旗帜默认 0。

`movement_mode: "animation"` 时，省略的僵尸动画相位按 [0,.99] 均匀采样。
普通/路障/桶/门/报纸/巨人/红眼/气球的速度参数为 [.23,.37]；橄榄/撑杆/地下矿工/小丑为 [.66,.68]；
梯子 [.79,.81]，小鬼 .9，旗帜/跳跳/舞王/伴舞 .45，地上矿工 .23。
机器没有对应地面轨道时不强制生成速度参数，采用相应行为模块的速度；气球的参数在落地行走阶段使用。
这些实际采样值在规范初态中保存，批量重放无需再次抽取。
`mean` 模式不自动采样这些字段，避免改变第一轮既有冷却与随机流；显式字段仍保留。

同格多个僵尸一直允许，每个实体都有全局唯一 `id`；省略 id 时自动生成。
叠种每个植物也独立保留血量、攻击冷却、状态和最终输出。

## 多次模拟及重放

每次使用种子 `signed_int64_wrap(base_seed + zero_based_run_index)`。
显式指定的血量、冷却、动画相位等值固定；省略的随机初始字段每次重新按该种子生成。
随机数由 Python 独立伪随机流提供，**不是原版随机流复刻**。

批量结果提供 `outcomes.plants` / `zombies` / `undecided` 的 `count`、
`probability` 与 `wilson_95`。概率分母包含全部模拟，包括达到帧数上限的未决，
不会剔除未决后虚增胜率。Wilson 区间只是独立模拟样本的 95% 统计区间，
不覆盖模型与原版之间的系统误差。`results` 保留每次完整最终状态。

```sh
python3 -m pvz_ize run examples/v2_random.json --json \
  --output outputs/v2-batch.result.json \
  --trace outputs/v2-batch.events.ndjson \
  --dump-initial outputs/v2-batch.initial.json
```

批量事件日志每条附 `run_index`（从零起）和 `seed`。
批量初态输出是 `batch_replay: true` 的清单，`runs` 中每项含 `run_index`、`seed`、
`scenario`；取任意 `scenario` 对象写为 JSON 即可单次精确重放（其 runs 已设为 1）。
这不是普通场景文件，不应直接传回 run。若输入固定了所有随机初始值，多次模拟仍会采样战斗过程随机性。

退出码：全部已决为 0，任一未决为 2，输入或文件错误为 1。
大批次数和逐事件日志可能占用较多时间/磁盘；工具不会自动降低用户指定次数。

## 最终状态补充

每次结果包含所有植物/僵尸独立末态（含层、血量、阶段、方向、阵营和计时）、弹丸、已放梯子、事件计数。`pending_effects` 额外保存尚未落地篮球及大蒜恶心等待；`zombie_special_state` 保存投石车剩余弹药等模块状态；`active_hostile_zombies` / `active_friendly_zombies` 分开统计敌友。最终输出用于诊断，不是可重新输入的中途存档。

初始工具例外：撑杆/梯子/跳跳失去工具后使用普通步行速度；梯子 `tool: false` 同时移除梯盾。读报 `shield_hp: 0` 直接使用暴走阶段，动画模式默认速度参数 [.89,.91]；初始落地气球 `tool: false` 使用地面步行，并恢复普通掉头规则。
