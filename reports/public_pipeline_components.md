# 三套公开管线：共同骨干与首个验证实验

仅根据 2026-11-04 已冻结在本地的源码静态比较；本页不是新的模型执行或榜分评估。

| 组件 | Canqiang E006 V1 | prvsiyan V43 | Flexonafft V56 |
| --- | --- | --- | --- |
| 主 Engine 1 | Ahmed v4b/FE、FPNet full1、预计算候选指纹/碎片、LightGBM | 同一谱系 | 冻结 0.465 基线中保留同一谱系 |
| Engine 2 | 谱库匹配、analog propagation、FPNet A/B、MetFrag-lite、双 GBM 排序 | 同一骨干，加入 PubChemLite | 同一骨干和 PubChemLite，增加 GBM 种子袋装等改动 |
| Engine 2 候选来源 | COCONUT、ChEBI/LIPID MAPS、训练结构 | 再加 PubChemLite | 再加 PubChemLite；部分目录/来源换成 attributed bundle |
| PubChem 通道 | FPNet A/B；文献/物质数量先验 0.25 | 先验 0.15 | 先验 0.15；加入 panel-excluded fold0 FPNet 等增强 |
| 正向谱模拟 | ICEBERG + GLACIER，同分子式内重排 | 保留；增加 N1 的 NH4/失水代理谱与 merged-CE 分支 | 冻结基线同样继承 N1；之后还有独立神经候选打分 |
| 融合与尾部 | 40 候选窗口、官方 identity 合票/去重、GL 盲区 ICE fallback | 再加无正向证据时的 fragment gap，以及 Engine 2 领头候选 rank2 插入 | 冻结基线继承上述分支，再叠加下列最终层 |
| 独有后处理 | E006 overlay | 本页 V43 没有 Saner 神经层 | Saner v1 SpectrumCandidateModel；CUSTOM 神经 RRF 权重 top=0.25 / tail=0.75；V2 物理碎片检查与 m1 合并；末层文档/谱/天然产物先验、官方 identity 去重、outsider 补位 |

三者不是三个完全独立模型。它们高度共享候选池、谱库、FPNet 权重、排序特征、正向谱模拟器和融合祖先，甚至许多函数体完全相同。给三个最终列表等权投票，会重复计算同一来源的证据；必须先在验证集量化错误相关性和互补召回。Flex 使用更多 Engine 2 种子，不等于获得独立的科学证据。具体函数体及种子差异见 `third_party/prvsiyan_analog/ENGINE2_CACHE_BOUNDARIES.md`。

当前 12 个 smoke 查询是可见占位数据，谱本来来自训练库；它们主要检验程序、模型覆盖和输出格式。强库匹配使若干关键盲区/leader-move 分支不能触发，因此既不能用它们选三套方案的冠军，也不能据此调融合权重或推断银牌分数。

## 首个实验：固定候选集，检验 Saner 神经排序是否提供增量

实验 ID 建议为 `VAL001_NEURAL_INCREMENT`。从 Flex 的冻结基础输出 V0 出发，只比较 V0 与加入 Saner 神经项的预先固定配置；保留相同候选、同一身份规范化和同一查询谱。先不用 physical、文档先验、outsider 插入等层，避免多因素混在一起。固定使用公开配置 V1（0.25/0.25）及 CUSTOM（0.25/0.75），不在最终留出集上搜索权重。候选召回在本实验中应完全相同，变化来自排序；后续再逐项测新候选来源与 N1 覆盖。

1. 按官方 RDKit 2026.03.3 的 tautomer-canonical InChIKey14 分组，冻结查询清单、开发/最终留出清单和内容哈希。保留同仪器 250 天然产物面板，并建立多个来源的结构级代理集；禁止按谱图行随机拆分。同仪器面板已被公开方案开发者使用，不称它为从未见过的新外部测试。
2. 先构造 Class 2 的留库诊断：从全部参考谱库、representative、analog 父本和相关缓存中移除查询身份的谱，但保留候选池中的真结构。Class 1 独立复测另列，不允许查询谱自身或重复采集自匹配。暂不把 Class 3 生成问题混入这次排序消融。
3. 对每个公共预训练 checkpoint 审计训练身份与 split。fold0 的 panel-excluded 声明只证明该组件的排除，不能替整个 FPNet/ICEBERG/GLACIER/Saner/ranker 栈担保。无法证明全栈排除时，此轮明确标为“潜在训练污染的留库诊断”；真正独立结论必须来自可审计的排除身份或全栈 OOF/重训/新外部样本，不能仅靠删参考库改名为干净验证。
4. 分子级报告 MRR@25、top1/top5/top25、候选召回、同分子式排序；分层列出库相似度、[M+H]+ 是否存在、正/负模式、加合物、质量范围、天然产物与跨库来源。配对 bootstrap 按分子重采样，报告增量区间及退化；同时保存耗时和显存。
5. 冻结最终留出集只评估一次。仅有小面板或潜在污染诊断上的提升，先保留分支；两个来源的验证方向一致、关键分层不退化且时间预算可行，才将神经项作为冲银主线。三套完整最终输出可另作观测对照，不能替代这个单因素实验。

源码定位：E006 原 Notebook cells 10–31；V43 cells 12、14、21、32–34；Flex V56 配置 cell 1、运行 cells 11–17，及 `v56/embedded/{neural_scores,consensus,parallax_physical}.py`、`frozen_0465.ipynb`。
