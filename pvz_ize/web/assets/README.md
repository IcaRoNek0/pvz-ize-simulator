# PvZ1 sprite assets

每个 GUI 单位现在使用一张完整角色图，不再把 reanimation 的脸、帽子或
单独身体部件当作图标。能从本地 reanimation 正确合成的单位使用透明的
PvZ1 图层合成图；其余单位使用 [Plants vs. Zombies Wiki](https://plantsvszombies.wiki.gg/)
的完整 `*1.png` 缩略图。两者都对应原版 Plants vs. Zombies（PvZ1），下载
映射可由 `scripts/fetch_sprite_assets.py` 重复执行，合成可由
`scripts/compose_reanim_assets.py` 重复执行；因此没有引入 PvZ2 的角色图。
`rake.png`、`ladder_object.png` 是模拟器的场景道具图。

僵尸图标由 `scripts/generate_sprite_assets.py` 的同一 PvZ1 reanimation
导出流程生成（源数据为 FregD156/PvZ_Assets 的原版 reanim 图层）；普通、
旗帜、路障、铁桶、铁门、橄榄球、撑杆、扶梯、矿工、舞王、伴舞、蹦极、
巨人、红眼巨人、小鬼、冰车、投石车、气球、读报、礼盒、跳跳和雪人均为
完整角色合成图。仓库中已包含生成后的 PNG，运行 GUI 不需要 Pillow。

原始图像版权归 PopCap/EA；这些文件只作为本地模拟器预览资源随项目分发，
不声明为开源素材，也不改变原作者授权。
