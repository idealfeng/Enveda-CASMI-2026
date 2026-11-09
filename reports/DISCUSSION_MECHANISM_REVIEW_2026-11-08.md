# 讨论区机制审阅：下一实验该改变什么

审阅日期：北京时间2026-11-08。仅阅读根代理已从官方SDK取得的正文及评论，未访问隐藏数据、未提交、未训练。本报告中的他人成绩、覆盖率及误差属于作者自报，不是我们独立复现实测。证据目录：`reports/discussion_review_20261108/`；清单151主题，本次重点完整阅读752356、748524、748068、743254、749412。

## 结论一：新训练面板必须区分“有公开参考谱”与“无公开参考谱”

[验证策略748524](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748524)及[CV问题748068](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748068)里，Aryan比较了250个enveda-np-examples与490个无公开谱Enveda-180留出结构：仅PubChem popularity排序，前者约67%首选正确，后者约0%。Bull另报告ICEBERG在整体本地Class2的增益，在只测MassSpecGym未见结构时约归零。

这些是不同参与者的自报测量，不能据此断言我们数据会得到相同数字；但它们直接解释为何“在公共谱留出里涨分”可能无法迁移。我们现有48查询还有full-refit编码器接触问题，新增一个head分组并不能消除该问题。

**改变下一实验：**保留原48用于排错；新条件融合/异构体头的关键评价另用审计过的未见身份，分别报告public-spectrum-rich与train/public-spectrum-absent层。真正训练前审计正例、负例池、monitor和派生统计。参考谱检索任务与无同结构参考谱的排序任务分开。Enveda-180增量审计若能得到真实train外身份，将优先用于这一面板，而不是直接假定730k谱都是新增。

不采纳帖子根据Public反推的28/20/52类别比例作为真值；“约130个Public分子”也是作者估计。不能把其他人的噪声阈值机械当成本项目提交门槛。

## 结论二：应补齐真正缺失的结构证据，避免把既有碎裂模块再加一次

[752356](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/752356)作者自报depth6→7在旧底座上涨、在新底座反而−.008；candidate gate修复和features-frozen generation合交只有+.001，作者明确无法拆因果。其“主要收益来自更多query获得forward评分”判断来自公开版本链观察，尚不能等同于受控实验。

[743254及评论](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743254)把主要问题定位于同式连接异构体。评论者最初MetFrag-lite四项调整的+.065是在同一241结构面板上选出的最大值；后续冻结配置到四个独立库，合并增益降到+.023。这不是可直接叠到我们的分数上的收益。

**已在0.481实现的内容：**`frag_rescore.py`已有二键切割权重.6、linear intensity、.005 Da、H shifts -2..+3；冻结pipeline cell41已有N1A NH4/脱水proxy及merged-CE路径；cell52已有ICE fallback和N1 treatment上的joint ICE+GL。不能把“新增ICE/GL”“新增NH4 proxy”或四项MetFrag设置再次包装为新组件。

**改变下一实验：**在0.481底座导出每个query/候选的finite ICE/GL覆盖、真实adduct/CE、缺失原因和实际耗时；把“有评分但排序错”与“根本没有适用评分”分开。前者优先试真实CE间候选margin/支持率的小型列表训练头；后者只在确认模型能适用时补覆盖，不把Na/K或未知CE强行伪造为H+。固定候选第一阶段可先测新增证据是否区分当前最高分错误异构体，再决定扩大候选池/训练规模。原EXP003只有14个query具备有效多CE分组，不足以训练和宣称稳定收益。

## 结论三：新增候选应单独检验“统计污染”和排序能力，两个老修复已经有了

752356指出engine1包含rank/z-score/gap/softmax/formula-share等列表相对特征；把生成候选并进原列表可能连原候选分数一起改。作者自报原top5在约半数query重排，薄Class1面板上错误降首18/270；冻结原run、仅第二路加新候选后为0/270。该面板只是安全性检查，不是Public预测；不能从合交+.001推断genfix独立有效。

[749412](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/749412)的engine2首选插rank2，自报在旧两底座均+.002。它来自masked Public probes，不构成独立CV。本项目不需要照着做占位探针或从分数还原隐藏答案。

**已在0.481实现的内容：**候选自身PubChem promotion gate在冻结cell43:48–84按当前leader身份取immutable evidence；engine2 rank2在cell53 `_rank2_overlay`实现。因此这两项不是下一轮新贡献。若未来head/先验后处理再次改动rank2，应明确评估最终排序，不能仅凭早期overlay存在就宣称最终rank2必定保留。

**改变下一实验：**扩展候选池时保留基座原候选的原始分数/原归一化统计，新路单独评分后显式融合；逐query验原候选评分是否被无意改变。除扩池单独对照，还应安排“扩池+能处理新增同式decoy的训练头”组合实验，因为提高召回和增加decoy负担可相互抵消。扩大生成或购买更多计算不应排在实际困难候选排序头之前。

## 与获0.481源码的一致性证明

从公开MASS源码cell11直接base64解码的冻结notebook SHA256为`d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88`，与`third_party/flexonafft_evidence_gap/v56/embedded/frozen_0465.ipynb`逐字节一致；cell41/43/53分别确认N1A、candidate-specific promotion、engine2 rank2。物理模块在旧MASS与V35中同SHA，四项碎裂默认值一致。这些是本地源码核验，不是新增榜分证据。

实施优先级：保留完整0.481底座 → 审计Enveda180真实增量并建立未见身份开发层 → 导出实际错误候选及逐谱证据 → 冻结encoder训练小型列表匹配/聚合头（先500步测速，再完整训练）。不再把V35当默认升级基座，也不靠每日五个轻微权重改动凑额度。
