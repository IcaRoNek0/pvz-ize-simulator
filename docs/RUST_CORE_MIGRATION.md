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
