# 六、建立外部谱库专用验证集（P1-A）

## 结论

- 用冻结的 `cross_development`（200 个身份）建立验证面板，并从官方 train 抽取每个身份的查询谱。
- 外部谱库（Takumu+MassBank）在 200 身份上**匹配覆盖率仅 20%**（40/200），但**匹配精度高（Promotion Precision 0.925）**。
- **MassBank 再次是主要来源**（31 hits / 29 正确，precision 0.935），Takumu 次之（9 hits / 8 正确，precision 0.889）——与第 3 步结论一致。
- **目标身份排除（B 类）假提升率 6.5%**（13/200）：当把真结构从库中移除后，仍有 6.5% 的查询会被错误结构提升。

## A 类：正向匹配（200 身份，target 在库中）

| 指标 | 值 |
|---|---:|
| Match Coverage（有效匹配比例） | **0.20**（40/200） |
| Correct Match Coverage（正确匹配比例） | **0.185**（37/200） |
| Promotion Precision | **0.925**（37/40） |
| False Promotion Rate | 0.075（3/40） |

Bootstrap 95% CI：Match Coverage `[0.145, 0.255]`，Correct Match Coverage `[0.13, 0.24]`。

### 按来源

| 来源 | hits | correct | precision |
|---|---:|---:|---:|
| A（Takumu） | 9 | 8 | 0.889 |
| B（MassBank） | 31 | 29 | 0.935 |

## B 类：目标身份排除（假提升压力测试）

- 移除目标身份的原始 inchikey14 参考谱后重新匹配。
- **False Promotion Rate = 0.065**（13/200 身份仍被错误结构命中并会提升）。

## 结论解读

1. **覆盖率是当前外部库的硬瓶颈**：只有 1/5 的验证身份能被外部库命中。这直接对应任务书"候选库覆盖 vs 排序精度"两个瓶颈的区分——外部库覆盖面还很窄。
2. 命中之后的精度很高（92.5%），说明"阈值 + 提升"逻辑在命中的子集上可靠；风险集中在**误提升**（A 类 7.5%、B 类 6.5%）。
3. MassBank 在更大面板上依旧比 Takumu 更可靠。

## 边界

- 排除是原始 inchikey14 级别，非完整官方身份（互变/立体别名可能有差异）。
- 无管线 base ranking；"提升"是匹配层面的 rank-1 规则。
- 已知预训练曝光，非干净泛化。

## 产物

- `artifacts/step6_validation_summary.json`
- `artifacts/step6_per_identity.csv`
- `artifacts/step6_bclass_exclusion.csv`
