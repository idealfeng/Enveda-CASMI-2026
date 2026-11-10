# 一、项目背景

## 结论

背景已在 `produre1.md` 第一节完整给出，本步只是固化关键事实，无新增实验。

## 固化的事实

- 当前最优正式提交：**58156482**（`stormseye/casmi26-mass-guarded-extlib-1109`），Public LB **0.488**，COMPLETE、无错误。
- 0.488 = 0.482 基座（MASS + guarded learned-head-tail）+ Alex V12 外部实测谱库 overlay。
- 两个外部参考谱源：
  | 数据源 | 版本 | 谱图数量（发布口径） |
  |---|---|---:|
  | Takumu extlib | v2 | 200,724 |
  | MassBank harmonized | v1 | 124,160 |

- 当前外部匹配方案（已从源码核实）：前体质量匹配（10 ppm + 0.002 Da）、ion mode 兼容、sqrt-intensity cosine、碎片容差 0.015 Da、最少 4 个匹配峰、cosine 阈值 0.80、命中后直接提升至 rank-1。

## 待回答的问题（来自任务书）

1. Takumu 和 MassBank 各自贡献多少？（→ step03）
2. 0.488 的提升是否来自正确鉴定？（→ step05）
3. 是否存在错误结构被提升？（→ step05）
4. Adduct / 前体质量 / 碰撞能量约束能否提高可靠性？（→ step04）
5. 多谱取最高分是否产生偶然高分？（→ step04）
6. Enveda-180 是否有增量？（不在前五步范围）

## 依据

- `reports/improvement_ledger.json`（`current_best: 0.488`）
- `reports/optimization_20261109/mass_guarded_extlib/score.json`
- `submission/optimization_20261109/mass_guarded_extlib/recipe.json`
