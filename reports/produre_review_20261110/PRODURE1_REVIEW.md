# produre1 独立复核（2026-11-10）

结论：工作提供了有用的代码梳理、开发面板记录和 Enveda-180 新信息线索，但目前不能用它认定“0.488 主要由 MassBank 贡献、Takumu 低质量”，也不能将 431 个 alias 称为已证实新增结构。今天应保留真实 0.488 不变，在准确父版本上做来源消融和新参考谱接入；不据此删除某个库。

本复核没有改动 `produre1/` 原始产物、任何冻结 Notebook/模型或现有提交，也没有训练、下载、GPU 或外部写入。独立计算写在本目录。没有重新执行用户脚本的 main，避免覆盖结果。

## 已确认有用的部分

- `reference_cell14.py` 中匹配函数 AST 与实际 Alex V12 **cell24** 完全相同；文档称 cell14 是索引笔误。
- 对逐查询 CSV 独立重算，48-query MRR 算术与 JSON 一致：BASE .8573908730、A .8628472222、B .8782242063、AB .8871527778、AB_STRICT .8678075397。
- 载入 A/B 实测库、原 mode/precursor/sqrt-cosine/4峰阈值基本按原匹配数学实现，确实能用于提出后续机制假设。
- Enveda-180 的 200-query 结果给出了值得继续检查的新增参考信号；它是开发匹配覆盖实验，不是完整 .488 系统 MRR，也不是隐藏泛化结论。

## 必须修正的归因问题

1. **基座不同。** `attribution.py:98` 读取旧 `runs/validation_flex_c2_20261105d/baseline_submission.csv`，该文件 SHA 为 `0c50e7a89bc3b2dd0c3362df7d628837f1c0a0a4445cafa85ee84616187e48ab`。它不是已正式得 .482 的完整 MASS+late-head 输出。README 已承认这一边界，但报告中的“AB即0.488方案”“MassBank主贡献”表述仍超出了证据。

2. **正式输出身份保护遗漏。** `attribution.py:192` 的 `promote()` 只按原 SMILES 操作，未复刻正式 `external_library_overlay_20261109.py` 的官方身份合法性保护。B 的9个“正确提升”proposal均有重复评分身份，其中8个是对合法旧列表新引入的重复；另1个来自旧 base 本来就有问题。AB有10个不合法proposal（9个新引入）。原 base 的 `np_JYGXADMDTFJGBT` 也已有重复身份，正式 helper 会在匹配前拒绝整个不合法 control。因此该面板不是直接可运行的生产 control。

   仅逐 query 套输出保护的诊断重算如下，**不是运行正式 helper，也不是生产 MRR**：A .8732638889、B .8573908730、AB .8767361111、AB_STRICT .8573908730。这个变化足以说明原来的来源质量结论不可直接沿用；不能反过来宣称 B 在隐藏集无收益。

3. **“13/200假命中”含正确别名。** `step6_validation_panel.py:148` 只按发布者 raw key 过滤。独立按官方身份复核13条 false_smi，其中2条仍等于真结构：`VXVNYCRICCVPTD`、`BGYJFSXPRMOZJK`；其余11条才是错误评分身份。报告6.5%不能当严格身份隔离后的假提升率，11/200也仅是当前未隔离充分压力面板中的错误命中计数。

4. **按来源统计的是 AB 赢家子集。** step6 的 A9/8正确、B31/29正确来自 combined-best 输出，不是分别独立运行 A-only/B-only 的准确率；样本数也小。它不支持给数据库贴固定“高质量/低质量”标签。

5. **431 membership 比较不完整。** `step7_enveda180.py:108` 用14字符 official ID 查询 MassBank 的完整27字符 `inchikey`，格式不一致。该文件139744个非空key全为27字符。将前缀修正后本431样本仍为0个命中，但官方 tautomer 身份未全量核对的问题仍在。`POOL` 指向275810行 `train_structs.parquet`，不是710701行 `pool_meta.parquet`，所以不能据此证明候选库不存在这些身份。其余 publisher key 与官方身份混用也需规范化。

6. **签名唯一不等于完整谱去重/跨库隔离。** step7 只统计发布者的 `spectrum_signature`。本审计额外对首4096条 Enveda 谱按排序后正有限峰、float32 basepeak归一强度、原adduct和neutral_mass做内容签名，4096条中没有重复；这只覆盖一个有界样本，没有证明全部730252谱无重复或与 train/reference 无重叠。200-query提升覆盖不能排除相同采集谱泄漏。

## 第四提交槽：MassBank 前体元数据修复的独立可行性

独立流式读取全部 MassBank 数据，只加载8192行一批。原逻辑可用124160条参考中：

| 检查 | 行数 |
| --- | ---: |
| 有有限正值 `precursor_mz` | 101807 |
| 缺失或无效实测 precursor | 22353 |
| 实测偏离旧 `neutral_mass ± H` 的10ppm+.002窗 | 25480 |
| 已知adduct实测记录 | 91408 |
| 与已知adduct换算及neutral_mass仍不一致 | 15434 |
| 实测与adduct理论一致、mode兼容且明显偏离旧±H窗 | **1281** |

因此，直接使用全部有限 precursor 也不安全。建议预先固定保守规则：只有**已知adduct、mode同号、实测m/z与按电荷/adduct换算的理论m/z在同一质量窗内**时使用实测 precursor；缺失、未知、冲突全部保留原 fallback。A、原输出身份保护、阈值、候选及排序基座不改。这是一个明确元数据机制分支；1281是可作用的参考行数，不能当隐藏命中或预期提分。

如果只希望局部改变，可进一步只替换实测超出旧搜索窗的1281条（规则须训练/看分前固定）。若对所有化学一致记录替换，会连旧窗内小数值差也改变，属于另一配方，不能两种写法混称同一方案。

## 今日提交建议

推荐5个机制槽：准确 .482 父版本上 A-only、B-only；原 .488 加 Enveda-180 的竞争最高分版；上述受化学一致性保护的 B-precursor 修复版；原 .488 加 Enveda-180 的仅填补原 AB 未获合法高置信命中版。新 Enveda 信号限其真实支持的 H+/H−同adduct匹配，保留原强内部库保护。第三与第五只有外部来源冲突决策不同，便于归因。

所有版本还需正式嵌入代码同步、缺失输入/动态hidden测试、实际小试与源码/输出绑定核验后才具备提交条件。本次任务是规划，未执行新的 Kaggle 写操作。

证据：[独立数值与身份核验](produre1_independent_checks.json)、[MassBank前体审计](massbank_precursor_metadata.json)。
