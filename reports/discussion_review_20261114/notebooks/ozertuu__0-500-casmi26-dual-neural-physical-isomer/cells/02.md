# CASMI26 · 0.480 —— 公开 0.479 最强配方 + 私有神经模型分数集成（开源版）

**我们在这份 notebook 上取得的最佳公开榜成绩：`0.480`（MRR@25）**
快照（2026-11-01）：公开榜 **第 36 名 / 4,522 支队伍（前 0.8%）**，银牌区。

## 这份 notebook 在做什么
1. 运行公开的最强管线（Variant M：候选生成 → 神经打分 → 物理碎片校核 → leader-safe 共识重排 → 文档先验 + In-Key 去重）；
2. 把**我们自训的谱→结构模型**（`casmi26-scorer-train-public` 训练产物）与管线内置公开模型的神经分数做**逐分子 z-score 集成**：`0.5*z(public) + 0.5*z(ours)`；
3. 只重排第 2–25 名，第 1 名保持公开管线的 leader-safe 决策。

## 关键发现（负结果同样重要）
| 实验 | 公开榜 |
|---|---|
| 公开 0.479 配方原样 | 0.479 |
| **+ 神经分数集成（公开 + 自训）** | **0.480** |
| 自训模型**单独替换**公开神经模型 | **0.460**（显著变差！） |
| 物理校核 + 溯源重排叠加 | 0.472 |
| 解除 PubChem 门控（aggressive 插入） | 0.466 |
| 外侧候选 20→40 + 3 槽救援 | 0.471 |

**结论**：私有模型必须**集成**而不是**替换**；集成是本文档唯一有效的改进。

## 如何复现 / 改进
1. 运行公开训练内核 [`bgunshui/casmi26-scorer-train-public`](https://www.kaggle.com/code/bgunshui/casmi26-scorer-train-public) 得到你自己的模型（约 2.3h T4）；
2. Fork 本 notebook，把 `kernel_sources` 换成你自己的训练内核（或把模型上传为 Dataset 后挂载）；
3. `_swap_to_ours()` 会自动在 `/kaggle/input` 下寻找 `final_model.pt` + `config_used.json`；
4. 也可以直接扫描集成权重 `w_ours ∈ {0.3, 0.4, 0.5, 0.6}`。

## 致谢与许可
- 基础管线、共识重排、物理碎片校核来自公开 notebook 作者（dmitriigluzdov、sanpier、romanrozen、romantamrazov、busyaprime、alexchilton 等），各数据集许可见其 ATTRIBUTION/SOURCE-LICENSES 文件；
- 本 notebook 的增量：私有神经模型训练（公共训练套件 `sanpier/casmi-spectrum-model-v1`）、神经分数集成、评测/工程化流水线。
