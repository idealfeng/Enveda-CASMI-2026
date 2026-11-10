# 二、固定基座与复现 0.488（P0-A）

## 结论

- **0.488 的冻结状态已完整固定并可核验**：5 个外部库文件 SHA-256 全部与 recipe 一致（本轮重新哈希验证通过）。
- 匹配逻辑已从上游 Alex V12 源码 cell 14 逐行提取并复刻，参数与 recipe 完全一致。
- **本轮未做一次全新的 GPU 全流程复现**：0.488 已由官方 API 确认（COMPLETE），重新跑一遍需要 GPU + 完整模型/权重 + 数小时，超出本步"只读审计"的定位；本步做的是"资产完整性校验 + 匹配逻辑固化 + 字段 schema 固化"，这正是任务书 2.1/2.2 要求的复现前提。

## 资产 SHA 校验（本轮重算，全部通过）

| 文件 | 大小 | SHA-256 | 结果 |
|---|---|---|---|
| Takumu ext_meta.parquet | 7,120,766 | 9b0c2d67…3f7d37f | ✅ |
| Takumu ext_mass.parquet | 7,979,821 | e82a878f…af12e | ✅ |
| Takumu ext_mz.npy | 102,770,816 | a14f750d…5fad5 | ✅ |
| Takumu ext_in.npy | 102,770,816 | e47b359f…1be841 | ✅ |
| MassBank spectra.parquet | 43,941,912 | 6ebb46b3…c9477 | ✅ |

## 冻结的匹配参数（`recipe.json` 与源码一致）

- `TAU = 0.80`（cosine 阈值）、`K_PEAKS = 4`、`LIB_TAU = 0.90`（保护阈值）
- 前体窗 `10 ppm + 0.002 Da`、碎片容差 `0.015 Da`、sqrt-intensity cosine、一对一片段匹配
- 保护规则：`frozen_candidate_evidence.parquet` 的 `library_max >= 0.90` 时跳过 overlay
- 提升规则：命中即 rank-1（结构已在列表则前置，否则插入并截断到 25）

## 源码出处

- 上游：`third_party/public_scan_alexchilton__casmi26-lb-0-484-peaks-to-structures-extlib_20261109/source.ipynb`（cell 14，`_apex_extlib_overlay`）
- 复刻：`produre1/attribution.py`（按来源参数化，用于 step03）

## 复现障碍（诚实记录）

- 0.482 MASS 基座从未在 48 查询开发面板上运行，因此无法在该面板上直接"复现 0.482 输出"。step03 用 Flex48 V0 作为一致基座做归因，属受控替代，已在结果中标注。
