# 工程任务书：CASMI 2026 外部实测谱库优化与可靠性审计

**项目：** Enveda CASMI 2026  
**任务编号：** EXT-LIB-001  
**优先级：** P0  
**任务性质：** 算法优化、实验验证、数据审计、工程实现  
**核心目标：** 拆解当前 0.488 Public LB 的外部谱库贡献，建立可靠的外部质谱匹配体系，并探索 Enveda-180 的增量价值。

---

# 一、项目背景

当前 CASMI 2026 项目已经具备较成熟的多阶段质谱结构鉴定系统。

目前最优正式提交：

- Submission ID：58156482
- Public LB：0.488
- 基础方案：0.482 MASS + guarded learned-head-tail pipeline
- 新增证据：Alex V12 external measured-library overlay

新增外部参考谱来源：

1. Takumu extlib v2
2. MassBank harmonized v1

当前外部库规模记录：

| 数据源 | 版本 | 谱图数量 |
|---|---|---:|
| Takumu extlib | v2 | 200,724 |
| MassBank harmonized | v1 | 124,160 |

目前的外部匹配方案主要采用：

- 前体质量匹配。
- Ion Mode 兼容。
- sqrt intensity cosine similarity。
- 碎片质量容差约 0.015 Da。
- 最少匹配 4 个碎片峰。
- cosine 阈值约 0.80。
- 外部谱匹配结构满足条件后直接提升至候选首位。

现有正式结果表明，加入外部参考谱后 Public LB 从 0.482 提升到 0.488。

但目前仍存在几个没有得到充分回答的问题：

1. Takumu 和 MassBank 分别贡献了多少？
2. 0.488 的提升是否来自真正正确的结构鉴定？
3. 是否存在错误结构被高分匹配并提升到第一名的情况？
4. Adduct、前体中性质量和碰撞能量约束是否可以提高匹配可靠性？
5. 多谱查询采用最高单谱匹配分数是否容易产生偶然高分？
6. Enveda-180 是否能够提供额外的有效参考谱证据？

本任务的目标是将当前外部谱库从一个有效的附加模块，发展成一个有独立验证体系、能够量化可信度的结构鉴定通道。

# 二、最高优先级：固定基座与复现当前 0.488 方案

在开始任何实验之前，必须固定当前正式预测方案。

## 2.1 固定两个核心版本

**Baseline A：0.482 基座**

使用原始 MASS + guarded learned-head-tail 方案，不启用新增外部谱库 overlay。

**Baseline B：0.488 当前完整方案**

在 0.482 基座上启用：

- Takumu extlib v2
- MassBank harmonized v1
- 当前外部匹配逻辑
- 当前候选提升逻辑

必须确认能够复现两套方案的实际预测输出。

## 2.2 固定实验资产

记录：

- Notebook SHA256。
- Python 源码 SHA256。
- 模型权重 SHA256。
- 外部谱库文件 SHA256。
- 外部谱库 metadata SHA256。
- RDKit 版本。
- 评分身份标准。
- 随机种子。
- 运行参数。
- 最终候选文件 SHA256。

不能使用两个不同版本的基础模型进行外部谱库消融。

不能因为后续修改了模型或候选池，就将实验提升归因于外部谱库。

**0.482 基座必须保持完全一致。**

如果无法恢复准确的 0.482 资产，应先报告复现障碍，不得用近似版本冒充原始基座。

## 2.3 正式提交保护

当前 0.488 正式提交作为只读参照。

未经授权不得：

- 修改正式提交 Notebook。
- 覆盖正式模型。
- 修改现有正式提交结果。
- 执行 Kaggle 正式提交。

所有新实验使用独立目录和独立分支。

# 三、P0：Takumu 与 MassBank 贡献归因

这是第一轮必须完成的实验。

保持 0.482 基座完全不变，只改变外部参考谱来源。

## 3.1 实验矩阵

| 实验 | 外部数据 | 目标 |
|---|---|---|
| BASE | 无外部 overlay | 0.482 基准 |
| A | Takumu only | 测量 Takumu 独立贡献 |
| B | MassBank only | 测量 MassBank 独立贡献 |
| AB | Takumu + MassBank 原始方案 | 复现 0.488 |
| AB-STRICT | A+B 严格 Adduct 兼容 | 测量化学约束的增量价值 |

所有实验必须使用完全相同的查询、模型、候选池和排序基座。

## 3.2 贡献归因指标

分别计算：

\[
\Delta_A=MRR(A)-MRR(BASE)
\]

\[
\Delta_B=MRR(B)-MRR(BASE)
\]

\[
\Delta_{AB}=MRR(AB)-MRR(BASE)
\]

同时计算交互贡献：

\[
I_{AB}=MRR(AB)-MRR(A)-MRR(B)+MRR(BASE)
\]

用来判断两个数据库是否存在互补价值。

需要特别分析：

- A 单独命中的查询。
- B 单独命中的查询。
- A、B 同时命中的查询。
- 两者给出不同结构的冲突查询。
- 两者都没有有效命中的查询。

输出逐查询贡献归因文件。

不能仅报告整体 MRR，还必须给出具体查询层面的变化。

# 四、P0：外部谱匹配可靠性审计

重点检查当前实现：

`scripts/external_library_overlay_20261109.py`

同时检查正式 Notebook 中嵌入的实际执行代码。

不能只修改独立 Python 脚本而忘记正式 Notebook 中的代码副本。

## 4.1 Adduct 兼容性

初步审计发现：

- Takumu metadata 存在 Adduct 字段，但当前匹配逻辑没有充分利用。
- MassBank 存在相关 metadata，但当前读取列没有完整纳入匹配过程。

必须重新检查实际数据 schema 和字段映射。

实现严格的加合物兼容检查。

至少考虑：

- [M+H]+
- [M+Na]+
- [M+NH4]+
- [M+K]+
- [M-H]-
- [M+Cl]-
- 多电荷离子。

具体支持范围以实际数据为准。

不能将未知 Adduct 默认视为兼容。

对于不同 Adduct，只有在能够可靠计算中性质量时才允许跨 Adduct 匹配。

需要建立明确的加合物精确质量映射和电荷处理逻辑。

建议采用：

\[
M_{\mathrm{neutral}}
=
|z|\cdot(m/z)-\Delta m_{\mathrm{adduct}}
\]

其中加合物质量偏移和电荷必须采用明确的离子化学定义，不能简单使用整数质量近似。

必须分别测试：

1. 同 Adduct 匹配。
2. 不同但可转换 Adduct 匹配。
3. 未知 Adduct 匹配。
4. Ion Mode 冲突。
5. 电荷状态不一致。

对于无法可靠转换的情况，应拒绝匹配或降低可信度，而不是静默放行。

## 4.2 前体质量匹配

当前前体质量窗口约为：

10 ppm + 0.002 Da。

需要明确它究竟作用于：

- 原始 precursor m/z；
- 中性分子质量；
- 还是经过 Adduct 转换后的质量。

比较：

A. 原始方案。

B. 相同 Adduct 下直接比较 precursor m/z。

C. 不同 Adduct 下转换中性质量后比较。

记录各方案的：

- 有效匹配数量。
- 错误匹配数量。
- 正确结构命中率。
- 前体质量误差分布。
- 不同质量区间的表现。

不要为了提高命中数量而无限放宽质量窗口。

## 4.3 Cosine 和碎片匹配质量

当前实现使用：

- sqrt intensity cosine similarity。
- fragment tolerance 约 0.015 Da。
- 最少 4 个匹配峰。
- cosine 阈值约 0.80。

需要研究：

**匹配峰数量**

比较：

- 3 个峰。
- 4 个峰。
- 5 个峰。
- 6 个峰及以上。

**Cosine 阈值**

比较：

- 0.75
- 0.80
- 0.85
- 0.90

以上是候选实验点，最终阈值必须根据独立验证结果确定。

**匹配峰独特性**

不能将任意 4 个匹配峰都视为同等强度的证据。

研究：

- 低质量区常见碎片的权重。
- 高质量特征碎片的权重。
- 高频出现碎片的降权。
- 稀有碎片的证据价值。
- 匹配碎片占查询总强度的比例。
- 匹配碎片占参考谱总强度的比例。
- 碎片质量误差。

可以探索类似 IDF 的碎片稀有度加权：

\[
w_i=\log\frac{N+1}{df_i+1}
\]

其中 \(df_i\) 表示某类碎片在参考谱库中的出现频率。

但需要防止稀有噪声峰被赋予过高权重。

实现峰匹配的一对一约束，避免一个峰被重复匹配到多个参考峰。

## 4.4 多谱聚合策略

目前一个查询可能具有多个碰撞能量或多个采集条件的质谱。

不能默认：

\[
Score=\max(S_1,S_2,\ldots,S_n)
\]

一定是最合理的聚合方式。

比较以下策略：

1. Max：最高单谱分数。
2. Mean：所有有效谱平均。
3. Top-k Mean：最高 k 张谱的平均。
4. Weighted Mean：根据 CE、谱峰数量和有效强度加权。
5. Consensus：要求多个独立查询谱支持同一结构。
6. Robust Aggregation：对异常高分进行抑制。

必须保留单谱证据和多谱聚合结果，不能只保存最终一个分数。

注意：

- 不同 CE 不应简单视为完全独立的样本。
- 不同 Adduct 的谱应分别处理。
- 不能因为严格要求多谱一致而误伤只有一张有效谱的查询。

需要针对只有一张有效谱的情况设计合理 fallback。

# 五、P0：外部候选提升机制审计

当前系统在满足匹配条件后，可以直接将外部谱库匹配结构提升至第一名。

这是本任务必须重点研究的环节。

## 5.1 Promotion Precision

定义：

\[
PromotionPrecision=
\frac{\text{提升后第一名为真实结构的查询数}}
{\text{发生候选提升的查询数}}
\]

同时计算：

\[
FalsePromotionRate=
\frac{\text{错误结构被提升的查询数}}
{\text{发生候选提升的查询数}}
\]

必须逐查询保存：

- 原始 Top-1。
- 外部匹配 Top-1。
- 原始候选是否包含外部匹配结构。
- 外部库来源。
- Adduct。
- 前体质量误差。
- 匹配峰数。
- Cosine。
- 各张查询谱的独立匹配分数。
- 最终是否发生提升。
- 提升后真实排名。

## 5.2 外部候选与原候选池的一致性

研究以下三种情况：

A. 外部匹配结构已经存在于原候选池。

B. 外部匹配结构不在原候选池，但具有高可信度直接谱证据。

C. 外部匹配结构不在原候选池，并且与原候选排序给出的证据明显冲突。

不能简单规定外部结构必须存在于原候选池，否则可能损失外部谱库补充新结构的价值。

应比较不同提升策略：

- 当前无条件满足阈值即提升。
- 原候选池存在同身份结构时允许提升。
- 原候选池不存在时采用更严格的证据门槛。
- 多张独立查询谱一致支持时允许提升。
- 多个外部数据库独立支持时允许提升。

目标是找到兼顾召回与准确率的策略。

# 六、P1：建立外部谱库专用验证集

这是本项目需要长期保留的验证基础设施。

建议建立 200–500 个唯一分子身份的专用验证面板。

具体规模以可获得的独立数据为准，不允许为了达到数量要求而引入泄漏样本。

## 6.1 A 类：正向匹配验证

目标：检验正确结构能否被外部谱库正确匹配。

要求：

- 查询谱与参考谱来自不同采集记录。
- 排除精确重复谱。
- 排除近重复谱。
- 尽可能保证不同采集批次或独立来源。
- 以官方 InChIKey14 身份匹配真实结构。

重点计算正确结构的 Match Coverage 和 Promotion Precision。

## 6.2 B 类：目标身份排除验证

目标：检验目标结构不在外部参考谱库时，系统是否会错误地提升其他结构。

操作：

1. 选取具有真实结构标签的查询分子。
2. 从 Takumu 和 MassBank 匹配库中移除目标身份的全部参考谱。
3. 保留查询谱作为未知输入。
4. 让外部匹配器正常运行。
5. 统计其他错误结构是否被提升。

这类实验是重要的假阳性压力测试。

不能只删除一条谱，必须删除该身份对应的全部记录。

## 6.3 身份和数据隔离

必须统一使用项目官方身份标准：

`chem.score_key()`

按照官方 InChIKey14 处理身份。

不能按原始 SMILES 或单条谱图进行随机切分。

需要排查：

- 同一结构不同 SMILES。
- 不同 tautomer。
- 同一结构在不同谱库中的重复。
- 同一采集记录的重复副本。
- 近重复谱。
- 查询谱与参考谱的潜在来源泄漏。

所有身份划分在实验开始前固定。

建议提供 query manifest 和 identity manifest，后续实验共享同一划分。

## 6.4 必须报告的指标

| 指标 | 说明 |
|---|---|
| Match Coverage | 外部库产生有效匹配的查询比例 |
| Correct Match Coverage | 正确结构实际被匹配到的比例 |
| Promotion Precision | 被提升的第一名中正确结构比例 |
| False Promotion Rate | 被错误提升的比例 |
| Top-1 Accuracy | 第一名准确率 |
| Recall@25 | 正确结构进入前25的比例 |
| MRR@25 | 比赛核心评价指标 |
| Per-Adduct Precision | 不同 Adduct 的可靠性 |
| Per-Source Precision | 不同来源的可靠性 |

所有主要指标同时提供：

- 样本数量。
- 分子身份数量。
- Bootstrap 95% 置信区间。
- 按数据来源分组的统计。

需要进行按分子身份的配对 Bootstrap，而不是将同一分子的多张谱当成独立样本。

## 6.5 预训练曝光与验证边界

现有48查询开发面板存在预训练模型曝光问题。

不能将它直接称为独立泛化验证。

新验证集需要：

- 明确训练集身份重叠。
- 明确预训练模型可能见过的身份。
- 明确查询谱与参考谱的独立性。
- 对不能确认独立性的样本单独标记。

报告中必须区分：

1. 接口可运行。
2. 真实谱匹配成功。
3. 独立身份验证成功。
4. 真正未见身份泛化成功。

不能将这四者混为一谈。

# 七、P1：Enveda-180 接入

现有项目已经审计过 Enveda-180。

此前报告记录：

- 730,252 条参考谱。
- 3,720 条 source-only aliases。
- 3,717 个规范化评分身份。
- 431 个身份存在 H+/H− 参考谱记录。
- 这些记录关联约1,600张谱。

这些数据属于此前审计结果，必须在正式接入前重新核实。

参考：

`reports/external_reference_pilot_20261107/README.md`

## 7.1 Membership 审计

首先对431个身份进行官方身份检查。

需要判断：

- 是否存在于训练集。
- 是否存在于 Takumu。
- 是否存在于 MassBank。
- 是否存在于 PubChem。
- 是否存在于 COCONUT。
- 是否存在于其他已有候选来源。

将身份划分为：

A. 已在训练集出现。

B. 已在现有候选数据库出现。

C. 已有其他外部参考谱。

D. 当前系统尚未覆盖的结构。

不能直接将431个身份全部称为训练集外的新结构。

## 7.2 谱图去重与清洗

对 Enveda-180 进行：

- 官方身份标准化。
- Adduct 标准化。
- Ion Mode 检查。
- 前体质量核验。
- 碎片峰格式标准化。
- 精确重复谱去除。
- 近重复谱识别。
- 来源和仪器 metadata 检查。

必须保留原始数据与清洗后数据之间的映射。

不能破坏原始数据。

## 7.3 独立 Overlay

在完成 membership 审计和谱图清洗之后，建立独立 Enveda-180 overlay。

第一轮不与 Takumu、MassBank 混合。

实验矩阵：

| 实验 | 外部参考谱 |
|---|---|
| BASE | 无 |
| TAKUMU | Takumu |
| MASSBANK | MassBank |
| ENVEDA180 | Enveda-180 |
| ALL | Takumu + MassBank + Enveda-180 |

先在本地固定验证集评估。

如果 Enveda-180 不能提供稳定的独立增量，不应直接加入正式提交方案。

# 八、神经网络方向：本任务暂不扩大训练

目前不要求直接训练新的神经网络。

此前同分子式新 head 实验：

| 指标 | 原 v2 | 新 head |
|---|---:|---:|
| Monitor MRR | 0.786099 | 0.782516 |
| Eval MRR | 0.829744 | 0.836054 |
| Monitor 同式 MRR | 0.816231 | 0.812379 |
| Eval 同式 MRR | 0.855306 | 0.860547 |

由于 Monitor 下降、bootstrap 区间跨零，以及预训练曝光问题，目前证据不足以支持扩大训练。

但需要为后续研究形成设计方案。

## 8.1 Candidate-conditioned Multi-spectrum Matching

未来模型目标：

\[
f(C,S_1,S_2,\ldots,S_n)
\]

其中：

- C：候选分子结构。
- S：不同 CE、Adduct 和采集条件下的质谱。
- 输出：候选结构解释整组质谱的匹配可信度。

与现有分别计算候选分子特征和谱图特征、最后进行融合的方式不同，新模型应显式学习候选结构与多张质谱之间的条件关系。

重点考虑：

- 分子结构图表示。
- 多谱特征编码。
- 不同 CE 的条件信息。
- Adduct 条件信息。
- 碎片峰对齐。
- 候选结构与碎片的解释关系。
- 同分子式困难负例。
- 原始排序器产生的 hard negatives。

本任务只要求形成架构设计与数据准备建议，不启动大规模训练。

# 九、工程目录与文件交付

建议建立：

`reports/external_library_audit_20261110/`

`reports/external_library_validation/`

`reports/enveda180_overlay/`

新增脚本根据现有项目组织调整，建议包括：

- `scripts/audit_external_library.py`
- `scripts/build_external_library_validation.py`
- `scripts/run_external_overlay_ablation.py`
- `scripts/audit_enveda180_membership.py`
- `scripts/build_enveda180_overlay.py`

建议实验产物：

```text
reports/external_library_audit_20261110/
    README.md
    baseline_manifest.json
    source_schema_audit.json
    source_attribution.csv
    per_query_attribution.csv
    adduct_audit.csv
    precursor_mass_audit.csv
    fragment_match_audit.csv
    promotion_audit.csv
    ablation_summary.csv
    run_manifest.json

reports/external_library_validation/
    identity_manifest.csv
    query_manifest.csv
    leakage_audit.json
    validation_results.parquet
    per_adduct_metrics.csv
    per_source_metrics.csv
    bootstrap_ci.json
    README.md

reports/enveda180_overlay/
    membership_audit.csv
    spectrum_dedup_audit.json
    source_overlap.csv
    overlay_ablation.csv
    README.md
```

所有实验必须保留：

- 代码版本。
- 数据版本。
- 模型版本。
- 运行参数。
- 运行时间。
- 随机种子。
- SHA256。

大规模谱图和候选记录使用 Parquet，不要生成不必要的巨大 CSV。

# 十、执行顺序与验收标准

## 阶段 P0-A：复现与审计

交付：

1. 0.482 基座可复现。
2. 0.488 原始 overlay 可复现。
3. 两个外部谱库的 metadata schema。
4. 当前匹配逻辑完整调用链。
5. 当前提升规则和所有阈值。

验收：能够明确解释当前0.488的实际实现，不存在只修改独立脚本而未修改正式 Notebook 的情况。

## 阶段 P0-B：来源贡献归因

完成：

- BASE。
- TAKUMU only。
- MASSBANK only。
- A+B 原始方案。
- A+B 严格 Adduct 方案。

验收：获得来源独立贡献、交互贡献、逐查询变化和配对统计结果。

## 阶段 P0-C：匹配可靠性改进

完成：

- Adduct 约束。
- 中性质量核验。
- 碎片匹配质量分析。
- 多谱聚合消融。
- Promotion Precision。
- False Promotion Rate。

验收：能够解释当前提升规则是否可靠，以及哪些约束真正减少错误提升。

## 阶段 P1-A：独立验证集

建立200–500个身份的专用验证面板。

验收：完成身份隔离、参考谱去重、正向匹配和目标身份排除测试。

## 阶段 P1-B：Enveda-180

完成431个身份的 membership 审计和独立 overlay。

验收：明确新谱库究竟带来了多少新的有效身份和匹配证据。

## 阶段 P2：后续模型设计

交付 Candidate-conditioned Multi-spectrum Matching 架构方案。

不要求训练模型。

# 十一、执行约束

1. 先审计，再修改。
2. 先做本地验证，再考虑 Kaggle 提交。
3. 所有实验固定0.482基座。
4. 不允许将 Public LB 的一次涨分当作独立泛化证明。
5. 不允许用同一批验证数据无限调参。
6. 不允许将未知 Adduct 默认为兼容。
7. 不允许静默吞掉谱图匹配失败。
8. 不允许修改正式提交结果。
9. 不允许覆盖原始参考谱库。
10. 不允许未经授权提交 Kaggle。
11. 不允许将 Class 3 生成器任务混入本任务。
12. 每个实验必须有独立配置、结果和 SHA。

如果某项实验因为数据缺失、身份无法核验或环境限制而不能完成，必须明确报告原因，不得使用模拟数据冒充真实实验。

# 十二、最终研究报告必须回答的问题

1. Takumu 和 MassBank 各自贡献多少？
2. 两个数据库是否存在互补价值？
3. 0.488 中有多少提升来自正确结构匹配？
4. 错误结构被提升的比例是多少？
5. Adduct 约束是否改善匹配精度？
6. 中性质量转换是否改善跨 Adduct 匹配？
7. 固定 cosine 0.80 是否合理？
8. 碎片峰稀有度是否能提高匹配可靠性？
9. 多谱最高分策略是否产生偶然高分？
10. 是否应该允许外部结构直接进入第一名？
11. 对于原候选池不存在的结构，应当采用什么提升门槛？
12. Enveda-180 是否提供了真正的新证据？
13. 下一步应该优先扩大谱库，还是优化谱匹配算法？
14. 是否已经具备开展 Candidate-conditioned Multi-spectrum Matching 的数据基础？

最终报告必须给出明确的技术路线、数据证据和实验结果。

---

# 最终执行指令

请直接在当前 GitHub 仓库开展工作。

第一步先完成 P0-A，不要直接开始训练或修改正式 Notebook。

在确认能够复现 0.482 和 0.488 后，按实验矩阵执行来源归因。

随后建立独立验证集，开展匹配可靠性分析。

最后才接入 Enveda-180。

每个阶段完成后输出阶段报告，并保留可以独立复现的实验配置。

**本任务的成功标准不是把 Public LB 从0.488提高到某个预设数字，而是明确证明外部谱库为什么有效、在哪些条件下有效、什么时候会误判，以及如何安全地利用这些证据。**

如果最终发现某些外部匹配规则并不可靠，也应如实报告，并提出保守的替代策略。

