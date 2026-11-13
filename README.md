# PvZ IZE 离线模拟器

输入初始植物、僵尸、脑子和特殊物件状态，在本地预测植物或僵尸获胜。Python 3.11+，无第三方运行依赖，不需要启动游戏。

> 本项目是离线近似模型，不是原版游戏，也不声称已逐帧复刻实机。当前范围不包含僵王；达到 `max_frames` 时返回 `undecided`。

## 安装

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

也可以不安装，直接用 `python3 -m pvz_ize`。

## 命令行

```bash
python3 -m pvz_ize run --plant peashooter,3,1 --zombie normal,3,8
python3 -m pvz_ize predict 'P7|_|_|_|_|_|Z0|_|_' --runs 100
python3 -m pvz_ize run examples/mixed.json --json --output result.json --dump-initial initial.json --trace events.ndjson
python3 -m pvz_ize validate examples/mixed.json
python3 -m pvz_ize catalog --json
```

## 图形化布阵器

```bash
python3 -m pvz_ize editor --port 8765
```

打开 <http://127.0.0.1:8765/>。选择植物、僵尸或特殊物件（钉耙、场上梯子），点击 5×9 地图布阵；可编辑 HP、护甲、位置、礼盒倒计时、阶段计时等属性。悬停时显示放置虚影，右键可选中单位。

## 场景格式

```json
{"version":2,"seed":42,"max_frames":100000,
 "brains":[{"row":3,"hp":70}],
 "plants":[{"type":"peashooter","row":3,"col":1}],
 "zombies":[{"type":"conehead","row":3,"col":8}],
 "rakes":[{"row":3,"col":8}],"ladders":[{"row":3,"col":4}]}
```

行列从 1 开始。植物/僵尸 `hp` 可设置为 0 到默认上限；礼盒支持 `jack_countdown_frames`；特殊僵尸可用 `phase`、`phase_timer` 预置阶段。玉米加农炮在无鼠标输入时使用最近僵尸自动瞄准近似。完整字段见 `docs/INPUT_V2.md`，边界见 `docs/FIDELITY_V2.md`。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 发布范围

本仓库只包含模拟器代码、GUI 静态资源、示例、文档和测试，不包含游戏本体、注入工具、反编译参考仓库或用户录像。
