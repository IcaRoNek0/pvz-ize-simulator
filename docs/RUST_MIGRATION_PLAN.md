# Simulator Rust 迁移计划

## 目标

把 `pvz_ize/engine.py` 的核心状态机逐步迁移到 Rust，保持 Python 版本为参考实现和 fallback。迁移期间不把未完成的 Rust 实现设为默认后端。

## 不变量

- 输入 JSON、随机种子、逻辑帧、终局 `winner/reason/frames` 保持可比较。
- 同格僵尸按独立实体处理，不做去重。
- 每个迁移阶段都必须有 Python/Rust 差分测试；差分失败时保留 Python 结果并报告失败样本。
- `--trace`、`--dump-initial` 在 Rust 尚未提供完全一致的事件流前继续走 Python。
- Rust 后端缺失或崩溃时可回退 Python，但不能静默宣称已完成 Rust 模拟。

## 阶段

### Phase 0：基线（已完成）

- Python `ProcessPoolExecutor`：约 106–115 runs/s（4 workers，100 轮基准）。
- 当前 Rust coordinator 只负责并发调度持久 Python workers，约 104 runs/s；结果与 Python 一致。
- 已保留 `native_batch/` 作为迁移期间的可运行 fallback/对照入口。

### Phase 1：数据模型与解析（进行中）

迁移 `Scenario`、`Plant`、`Zombie`、`Brain`、`Projectile` 的 Rust 表示，支持版本、种子、位置、HP、护甲、叠种和同格单位。先只验证解析和规范化 JSON，不进入终局判定。

### Phase 2：最小核心循环

迁移普通僵尸移动、植物基础攻击、直线投射物、啃食、脑子结算和 `max_frames`。要求固定简单场景逐帧结果一致。

### Phase 3：特殊机制

依次迁移土豆雷/窝瓜/地刺、矿工/撑杆/梯子、魅惑/舞王、投石车/气球/礼盒、植物头僵尸、钉耙和其它已支持单位。每组机制加入独立 fixture 与差分测试。

### Phase 4：批量并发

使用 Rust 线程或 Rayon 并行运行独立 replicate，结果按 `run_index` 排序；比较吞吐、内存和启动成本。只有当结果和基准都通过，才考虑将 Rust 设为默认后端。

### Phase 5：发布切换

保留 `--backend python|rust`，默认值只有在全量差分测试、视频回归和性能测试均通过后才切换。任何未迁移单位自动回退或明确报错，不套用普通单位规则。

## 当前热点基线

最近一次 cProfile（单轮 `examples/v2_random.json`）显示主要耗时为：

- `Simulator.run`
- `Simulator.update_zombie`
- `Simulator.update_plant`
- `Simulator.zombie_combat`
- `Simulator.chew`

这些函数是 Phase 2/3 的首要迁移目标。
