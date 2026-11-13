# 第二轮原版对齐检查

后续 0.3.1 / `ize-expanded-v3.1` 的修正与未解决问题见 `REGRESSION_5_7.md`；以下保留 0.3.0 的核查记录。

模型 `ize-expanded-v3`，软件版本0.3.0。这里的“第二轮”指开发轮次，JSON格式为v2。
旧 `MODEL.md` 保留第一轮研究过程；本文件及 `INPUT_V2.md` 对新版行为有优先解释权。

## 证据层级

1. Portable源码与rpze类型/状态表，版本和哈希见 `outputs/provenance.json`。
2. 只读解析本地原版PAK，保留数值轨道、动画帧数与哈希；不输出完整资源。
3. 只读反汇编本地PE的伤害范围分支；没有启动或修改游戏。
4. 本工具单元/集成/重放与批量测试。它们不是原版进程差分测试。

**未完成原版/Portable运行录帧差分，也没有测得通用误差率或胜率准确率。**

## 已核查并改正

- `Zombie::CanBeChilled/CanBeFrozen/ApplyButter`：冰车免疫寒冷；投石车可以寒冷/冻结；地下/出土矿工、出土伴舞等不受寒冷。跳杆、飞行/爆裂气球、抛出小鬼、开盒小丑、跳跳等不能随意冻结；黄油复用冻结资格。
- 寒冰菇首次冻结随机400..600cs，已寒冷时300..400cs；寒冷2000cs。巨人/投石车等可冻结，冰车不行。
- 巨人/红眼、机械、蹦极与飞行气球不套用普通三分之一血掉头规则。大嘴对巨人只咬40伤害，不直接吞杀。
- `Projectile::IsSplashDamage/IsZombieHitBySplash`：持门/梯盾及两种机械抗火球溅射；主目标仍受40普通伤害，持盾时先扣盾。西瓜不沿用此抗火规则。
- `Board::GetTopPlantAt`：啃食顺序shell→main→base；投石/蹦极顺序main→shell→base。被南瓜保护的下层不会因受击矩形不同而提前触发大蒜。巨人/碾压可以毁掉整格，地刺王另算耐久。
- `Zombie::EatZombie`：魅惑阵营相反的僵尸可互咬，绕过手持盾；友军不受植物索敌，剩余友军不阻塞植物胜。
- 磁铁先选场上防具/工具，再选地面梯子；可吸矿工镐并触发出土、跳跳杆、小丑盒。默认距离遵从INIT.md的横距+80×行差；`magnet_distance_mode: "source"` 可对照Portable欧氏距离+80×行差。两者可能选中不同目标，不能混称等价。

## 掩码纠错的原版静态证据

Portable `ConstEnums.h` 中位3是 `DAMAGES_DOG`，off-ground为位4。
此前依据字面值9/11/13推断“含off-ground”是错误的，已撤销。
本地PE的 `0x531b6d` 阶段表跳转到 `0x531c74`，随后 `0x531c76: shr al,4`、
`0x531c7a: and al,1`，直接检验 `0x10`。地下/飞行分支分别检验 `0x40` / `0x02`。

`outputs/alignment/original-damage-range.asm.txt` 保存对应反汇编；
`python3 scripts/check_original_damage_mask.py` 复核指定VA字节并记录PE哈希。
因此猫尾草11、西瓜13、喷菇9不因“位3”而伤到爆裂气球/出土矿工等off-ground阶段；
爆炸127包含该位。这里证明的是本地二进制这条分支，不是所有攻击路径已被动态验证。

## 可选随机步行动画

默认 `movement_mode: "mean"` 保留均速；`animation` 使用包内数值表 `movement_tracks.json`，
不要求运行时访问游戏目录。数值表由 `scripts/build_movement_tracks.py` 从保留的解析记录生成。

已接入普通/路障/桶/门/旗帜、橄榄、小鬼、撑杆持杆/落杆、梯子持梯/失梯、
地上矿工、巨人/红眼、报纸持报/暴走、气球落地的步行段。
根据 `UpdateAnimSpeed` / `GetTrackVelocity` / `GetFrameTime`：

```
rate = velocity_parameter * frame_count / ground_distance * 47
i = floor(animation_phase * (frame_count - 1))
dx = (ground[i+1] - ground[i]) * 0.01 * rate
animation_phase = (animation_phase + 0.01 * rate / frame_count) % 1
```

寒冷将rate减半；冻结/黄油暂停移动与步行相位。初始相位、速度参数和walk/walk2变体按种子采样，
也可全部显式固定。每次初态完整保留这些值，可重放结果和事件。
步行段切换会重置相位，部分恢复速度会重新采样，并记录事件。

**仍属部分复刻**：不实现全部骨骼/混合动画、吃完后的原版随机消耗顺序、完整攻击动画和绘制；
舞王/伴舞、地下矿工、飞行、车辆及部分特殊动作仍由各状态机使用均速/阶段计时。
仅采样但未被对应动作使用的输入参数不构成该动作已实现动画驱动。
Python RNG不等于原版RNG，同seed只保证本工具同版本重放。

## 明确保留的近似

- 仙人掌省略升降动画，高射前摇暂与低射同用34cs；猫尾草有追踪加速度，但碰撞仍用简化矩形。
- 大蒜有恶心等待、可指定/随机方向和边界回退，但换行不连续插值Y。
- 投石车篮球固定120cs延迟落格，投石车死亡后篮球继续；没有完整飞行轨迹。
- 跳杆落点/高坚果时序、爬梯曲线、跳跳高度、舞王节拍、小鬼抛射仍有简化。
- 冰车不产生冰道；扎胎直接结束机械，省略停车死亡动画；三叶草直接让正常飞行气球退场，省略吹飞动画。
- 植物叠种支持独立状态和优先受击；任意同层叠种是显式扩展，不是原版合法性断言。睡莲/花盆不意味着实现水池/屋顶。
- 无道具、经济、后续人工放置、自动刷新、任意原版存档恢复或僵王战。

详情及逐项源码位置见 `research/extended-plants.md` 与 `research/extended-zombies.md`。
