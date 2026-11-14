# IZE 命令行模拟器

输入初始植物、僵尸与脑子，在本地计算胜负。Python 3.11+，无第三方运行依赖，无需启动游戏。

**版本 0.5.6：可视化布阵器 + 非僵王预测。** 支持全部 38 种植物、28 种非僵王僵尸，覆盖配套生成页全部名单。支持代码/完整属性 JSON 导入导出、逐单位编辑、礼盒开盒倒计时和预测。按本轮范围不处理限时，达到帧数上限返回未决；尚未完成实机差分校准。

0.5.6 修正火炬的整数坐标转换、反向豌豆转火及原生提前碰撞豁免（torchwood clip）。保留之前的弹道排序、啃食、火豌豆、爆胎、停吃重启、跳跳及土豆雷修正；第 5 阵容的已知胜负偏差仍待解释。

启动布阵器：`python3 -m pvz_ize editor`，浏览器访问 `http://127.0.0.1:8765`。完整用法见 `docs/EDITOR.md`。

```bash
python3 -m pvz_ize predict 'P7|_|_|_|_|_|Z0|_|_' --runs 100
python3 -m pvz_ize run examples/creative-who.json --json
python3 -m pvz_ize run examples/creative-100s.json --json
python3 -m pvz_ize run examples/creative-boss.json --json
```

“谁会赢”只判第三行，源码未发现默认 100 秒硬时限；100 秒预设对应“时空回廊”第一阶段的**固定初态预测**，不包含后两阶段的操作历史回放。僵王按新版出生在第一行，不属于谁会赢生成页名单，实战预测使用 `ize` 全行规则。详见 `docs/CREATIVE.md`。

0.3.1 修正裂荚后射炮口及动画模式停止啃食后的步速重抽。第 7 阵容现与报告的胜负一致，第 5 阵容仍待校准，详见 `docs/REGRESSION_5_7.md`。

## 快速开始

在本目录执行：

```sh
# 默认仅第三行有脑子；所有僵尸从第 0 帧开始行动
python3 -m pvz_ize run --plant peashooter,3,1 --zombie normal,3,8

# 任意行脑子；可输入多个植物、多个僵尸
python3 -m pvz_ize run --brain-row 2 --plant snow_pea,2,1 --zombie buckethead,2,6

# 文件场景，输出完整结果及有用中间产物
python3 -m pvz_ize run examples/mixed.json --json \
  --output outputs/my-run.result.json \
  --dump-initial outputs/my-run.initial.json \
  --trace outputs/my-run.events.ndjson

# 验证、单位列表、帮助
python3 -m pvz_ize validate examples/mixed.json
python3 -m pvz_ize catalog
python3 -m pvz_ize run --help
```

可选安装：`python3 -m pip install -e .`，然后使用 `pvz-ize` 命令；直接用 `python3 -m pvz_ize` 不需要安装或联网。

## 场景格式

```json
{
  "version": 1,
  "seed": 42,
  "max_frames": 100000,
  "brains": [3],
  "plants": [
    {"type": "peashooter", "row": 3, "col": 1, "cooldown": 1},
    {"type": "wallnut", "row": 3, "col": 4}
  ],
  "zombies": [
    {"type": "conehead", "row": 3, "col": 6},
    {"type": "imp", "row": 3, "x": 570.5}
  ]
}
```

- 行列均从 **1** 开始：5 行、9 列。同格僵尸可重叠；植物支持 base/main/shell 分层叠种，同层叠种需显式 `allow_stacking: true`。僵尸 `col` 可为小数，`x` 与 `col` 必须且只能填一个。
- 蹦极的 `col` 必须为整数，表示抓取目标列；使用 `x` 时按最近格推定，也可显式提供 `target_col`。蹦极落点与普通僵尸出生横坐标不同。
- `brains` 省略即 `[3]`，可用 `[1,3,5]`；也可用 `[{"row":3,"hp":20}]` 指定剩余啃食次数。初始脑子集合不能为空，且每行至多一个。
- 植物可覆盖 `id`、`hp`、`cooldown`、`state_timer`；僵尸可覆盖 `id`、`hp`、`helmet_hp`、`shield_hp`、`speed`、`age`、`chilled`、`buttered`、`headless`。HP/护甲不能超过该类型初始上限，ID 必须全局唯一。
- `cooldown` 是距离下一次攻击周期重置的帧数，不是第一颗弹丸的实际出手时间；还需经过前摇。省略时按固定种子采样平稳剩余周期。`cooldown=0` 与 `1` 均在第一次植物更新触发。
- `state_timer` 用于特殊植物初始等待，默认 0；不是完整游戏中间态导入。无法导入正在跳跃、正在吞咽或已经在飞行的弹丸等原版存档状态。
- `speed` 是本模型实际均速，单位 **像素/逻辑帧**，不是原版 `mVelX`；`age`、`chilled`、`cooldown` 等均以 10 ms 逻辑帧计。100 帧=1 秒。
- 不提供后续外部刷怪、延迟放置、经济系统、道具、水池/屋顶；支持魅惑与显式叠种，详见 `docs/INPUT_V2.md`。未知字段、未支持类型和不合法值会报错，不静默忽略。
- 命令行 `--zombie-x normal,3,570.5` 可直接指定像素位置；文件输入也支持 `-` 从 stdin 读取。文件场景不能混用直接布阵参数，但可用 `--seed`、`--max-frames` 覆盖运行设置。

## 支持范围

|植物|英文类型|rpze 简写|
|---|---|---|
|豌豆 / 寒冰 / 双发|`peashooter` / `snow_pea` / `repeater`|`1` / `b` / `2`|
|三线 / 裂荚|`threepeater` / `split_pea`|`3` / `l`|
|小喷 / 大喷 / 胆小|`puff_shroom` / `fume_shroom` / `scaredy_shroom`|`p` / `d` / `x`|
|向日葵 / 坚果 / 高坚果|`sunflower` / `wallnut` / `tallnut`|`h` / `o` / 无|
|地刺 / 土豆雷 / 窝瓜|`spikeweed` / `potato_mine` / `squash`|`_` / `t` / `w`|
|火炬 / 磁力菇 / 大嘴花|`torchwood` / `magnet_shroom` / `chomper`|`j` / `c` / `z`|
|叶子保护伞|`umbrella_leaf`|`s`|
|杨桃 / 玉米投手|`starfruit` / `kernelpult`|`5` / `y`|

僵尸：普通 `normal`、路障 `conehead`/`lz`、铁桶 `buckethead`/`tt`、铁门 `screen_door`、橄榄 `football`/`gl`、小鬼 `imp`/`xg`。

特殊僵尸：撑杆 `pole_vaulting`/`cg`、梯子 `ladder`/`tz`/`ft`、矿工 `digger`/`kg`、舞王 `dancing`/`ww`/`mj`、蹦极 `bungee`/`bj`/`xt`；舞王可召唤实际参与结算的伴舞 `backup_dancer`。

大喷盾身同时群伤、裂荚后射、铁门挡冰、火炬转化与溅射、磁铁吸金属、土豆雷已出土、窝瓜预跳、大嘴吞噬、地刺不可啃食等均有独立行为。新增单位支持五向星星、玉米抛射/黄油定身、一次跳杆/高坚果阻挡、放梯及跨越、矿工出土反向与失镐、舞王召唤补员、蹦极偷取和保护伞防御。向日葵不模拟产阳光。

**第二轮新增植物**：仙人掌 `cactus`、猫尾草 `cattail`、大蒜 `garlic`、机枪 `gatling_pea`、卷心菜 `cabbage_pult`、西瓜 `melon_pult`、冰瓜 `winter_melon`、忧郁菇 `gloom_shroom`、樱桃 `cherry_bomb`、辣椒 `jalapeno`、寒冰菇 `ice_shroom`、毁灭菇 `doom_shroom`、魅惑菇 `hypno_shroom`、南瓜 `pumpkin`、睡莲 `lily_pad`、花盆 `flower_pot`、地刺王 `spikerock`、三叶草 `blover`。新增类型使用英文全名。

**第二轮新增僵尸**：巨人 `gargantuar`、红眼 `red_eye_gargantuar`、投石车 `catapult`、冰车 `zamboni`、气球 `balloon`、读报 `newspaper`、小丑 `jack_in_the_box`、旗帜 `flag`、跳跳 `pogo`、雪人 `yeti`。巨人能砸植物/投小鬼，投石车能投篮/碾压，保护伞也能挡篮球。

**仍不支持**：僵王、水生/雪橇小队等特殊单位与地形，玉米炮手动点火、任意中途存档恢复。睡莲/花盆只提供叠种承载层，不代表支持水池/屋顶。爬梯、跳跃、舞步、部分弹道与动画仍近似。详见 `docs/FIDELITY_V2.md`。

## 结算与输出

1. 输入中的脑子全部吃掉：僵尸胜，立即结束，其他行僵尸无需退场。
2. 仍有脑子且场上无敌方活僵尸：植物胜；进家/出界僵尸不计入场上。没有脑子的行被穿过不算僵尸胜；魅惑僵尸属植物方，不阻塞植物胜。
3. 无头僵尸仍有血且在场：继续模拟，不能直接按已清场结算。死亡动画不保留。
4. 达到帧数上限：`undecided`，不伪造胜负。默认 100000 帧（1000 秒）。

退出码：**0**=已决胜负或验证成功；**1**=输入/文件错误；**2**=模拟超时未决。植物胜和僵尸胜都返回 0，用 JSON 的 `winner` 区分。

`--json` 输出 `winner`、`reason`、逻辑帧数、剩余脑子 HP、各实体最终状态、在飞弹丸、事件计数和模型告警。文本模式也显示近似告警。`--trace` 是带帧号的逐事件 NDJSON，不保存每一帧快照，避免日志膨胀。

`--dump-initial` 保存实际采样后的、可再次输入的初态，同版本可重放相同结果与轨迹；**最终结果不是可恢复的存档**。输出路径不得与输入或其他产物相同（含软/硬链接）；显式指定已存在的其他输出文件会被覆盖。

## 验证和保留产物

### 参考视频准确率复现

视频对照只读取每局开始前的阵容；同格僵尸按列表中的独立实体保留，不做去重；记录含
`unsupported_or_custom` 或 `expected: "unknown"` 的轮次会跳过，不进入准确率分母。仓库内的
`examples/video_round_5.json` 与 `examples/video_round_7.json` 是可复现的两份输入，当前报告
明确保留 `run/5` 的已知偏差，不把它伪装成通过：

```sh
python3 scripts/audit_recorded_rounds.py \
  outputs/video-observations.example.json \
  --out outputs/video_accuracy.json
```

脚本输出 `match`、`mismatch`、`skipped` 三类计数，并记录初始僵尸数量及
`same_cell_zombies` 证据；需要绝对路径时加 `--absolute-paths`。视频原始文件不随仓库分发；抽帧和人工观察记录见
`docs/video_accuracy_report.md` 与 `outputs/video_accuracy.json`。

```sh
python3 -m unittest discover -v
python3 scripts/run_examples.py
python3 scripts/record_provenance.py
python3 scripts/build_movement_tracks.py
python3 scripts/inspect_reanimations.py --output outputs/reanimation-inspection.json
```

- `docs/PLAN.md`：先行实施方案；`docs/research/`：带源码引用的规则研究。
- `docs/MODEL.md`：实现约定、均速/动画差异、下一阶段原版校准清单。
- `examples/`：可编辑场景；`outputs/examples/`：初态、结果、事件、索引。
- `outputs/provenance.json`：参考项目提交、源码及本地游戏文件 SHA-256，仅记录元数据，不复制游戏资源。
- `outputs/test-results.txt`：本轮实际自动测试记录。
- `docs/ACCEPTANCE.md`：需求验收与未验证事项；`outputs/acceptance.json`：CLI实测及初态重放核验。
- `outputs/reanimation-inspection.json`：只读解析本地PAK所得动画帧数、地面轨道数值与哈希，不复制完整资源；脚本支持 `--asset`、`--track`、`--frame` 查询。
- `examples/special_ize.json`：包含新增特殊单位的组合示例；`outputs/examples-v1/` 保留升级前的结果。

参考 `ref/PvZ-Portable`（GOTY 社区重实现）和 `ref/rpze`（1.0.0.1051 Windows 注入测试框架）。本工具没有注入、修改游戏，也未把运行自身的测试包装成与原版一致性的证明。

## 第二轮输入与概率

完整字段、叠种规则和重放格式见 `docs/INPUT_V2.md`。

```sh
# 20次模拟，显示植物胜/僵尸胜/未决概率及95% Wilson区间
python3 -m pvz_ize run examples/v2_random.json

# 含新增单位与随机步行动画的组合示例
python3 -m pvz_ize run examples/v2_extended.json --json

# 可用 --runs 覆盖JSON次数，保存每次初态及事件
python3 -m pvz_ize run examples/v2_animation.json --runs 100 --json \
  --output outputs/batch.result.json --dump-initial outputs/batch.initial.json \
  --trace outputs/batch.events.ndjson

# 大批量预测可启用多进程（结果与串行逐轮一致；trace/初态清单会自动走串行）
python3 -m pvz_ize run examples/v2_random.json --runs 1000 --workers 4 --json
python3 scripts/benchmark_batch.py examples/v2_random.json --runs 100 --workers 4

# 可选 Rust 协调器（先 cargo build；规则仍由 Python Simulator 执行）
cargo build --release --manifest-path native_batch/Cargo.toml
python3 -m pvz_ize run examples/v2_random.json --runs 100 --workers 4 --backend rust --json
```

大蒜 `garlic_direction: "up"/"down"/"random"`；矿工 `underground: false` 指地上向右走；
僵尸 `hypnotized: true` 指初始魅惑。可逐体设置HP/头盔/盾及冻结/寒冷/黄油剩余帧。
批量概率包含未决分母，是本模型的样本频率，不是已经验证的原版胜率。Python ProcessPool 是默认高速后端；Rust 协调器为显式可选后端，基准见 `docs/NATIVE_BATCH.md`。

动画模式使用 `movement_mode: "animation"`，可固定 `animation_phase`、`velocity_parameter` 和 `walk_variant`；
只对已列出的步行段使用数值轨道，未覆盖动作明确保留近似，见对齐说明。
第二轮验收见 `docs/ACCEPTANCE_V2.md`；升级前示例保留于 `outputs/round1-examples/`。
