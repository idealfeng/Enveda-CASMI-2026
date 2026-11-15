# 20261113：生成覆盖扩展与生产修复

- 状态：正式提交已接受，`58309573`，当前PENDING，无有效新分；实时状态以[官方读回](latest_status.json)为准。
- 对照：冠军`58156482`，Public MRR@25 `.488`，Notebook SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。[父版本配方](../../submission/optimization_20261109/mass_guarded_extlib/recipe.json)。
- 假设：通过真正新增候选改善当前生成覆盖，避免继续混合同系checkpoint。既有Class3研究仅提供方向，不代表本版收益；不重做produre1/2。
- 实际算法变化：6→12谱母体、总生成上限150→300、关闭额外同分异构化，保留原每母体60上限与双步。原双神经、160列ranker、MASS、晚接入head、AB均保留。三项同时改变，若涨分先归整体，不能单独归因母体数或去同分异构化。
- 工程修复：原FROZEN先做确定性修改，生成模块必须核对修改后的engine SHA `e4943fb26a8141f47ea95e744910c2d0f4746e36e72ef43e3263e7f327cfc0b5`。上次组件小试未走此生产初始化，正式隐藏异常；修复本身不记算法增益。
- 冻结本版：[Notebook](../../submission/optimization_20261113/generation_production/notebook.ipynb) SHA `a9debc93f59213d3c80a8b3ee0e4808ee930d6ada34c3ee908f1469fa35cfa2c`；[recipe](../../submission/optimization_20261113/generation_production/recipe.json) SHA `9f70ddc759cf3ce5c927c7e0154128768b6f6931f8b19528c8f3649e9e743bae`；[部署清单](../../submission/optimization_20261113/manifest.json)。
- 模型与数据：不新训练，不新增谱库；源数据版本与冠军一致，详见冻结kernel-metadata和四份运行审计。实际公共神经权重SHA `44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642`、v2 SHA `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`；head及E006模型保持原部署指纹。
- 完整生产子集：`runs/generation_production_20261113_r2/`，两query/20谱、所有20个外层代码cell，真实E2→252原始特征/160列选择→GL/ICE→双神经→MASS→head→AB→CSV，2327秒，四份审计均hidden_full/passed。唯一资源适配为cpu_count=4；命令入口[本地运行器](../../scripts/run_generation_production_20261113.py)，运行日志和verification保留，不再重跑。独审未发现必需组件失败回退。
- 候选机制：308个接受候选，两题均实际走12母体，至少211个接受候选来自第7–12母体，1题触及300上限；最终14条raw SMILES与生成记录相交。这些不是相对冠军的正确召回或指标增量。[机制证据](generation_trace_analysis.md)。
- 输入边界：本次测试输入误保留标签元数据；源码审查未发现预测消费者使用这些字段，未运行准确率评价。这不是无标签/清洁CV；原verification中的unlabelled表述有误，以[披露更正](generation_disclosure_addendum.md)和[独审](evidence_generation_release.md)为准。未动态拦截每次字段读取，不扩大证明范围。
- 正式提交路径：私有、离线、GPU V1；云端可见Save&Run为fast_static，仅证明版本/输出审计。真正推理的小样本证据来自上述本地完整生产路径；隐藏全集预算、完整推理成功与榜分仍待正式评测。提交的是云端代码版本，未上传诊断CSV。
- 正式回执：[提交接受](generation_production/submission.json)、[云端版本](generation_production/cloud.json)、[可见输出审计](generation_production/output_audit.json)、[放行指纹](generation_release_gate.json)。后台只读查分，若出现真实新高才按整体来源和归因边界记账；异常不计零分。
- 本轮其他筛选：MassBank可信前体修复无新增合法命中；固定CE支持率回放零增量；固定谱网络小幅负向，均未正式提交。FRNet仅保留研究资产，未部署。[筛选证据](../SUBMISSION_PLAN_2026-11-13.md)。
- 决策：今天先提交这1版，保留其余4次；不以无收益配方填满额度。下一步依据这版隐藏运行及真实分数决定保留/停止，再考虑可解释的单因素对照。原始失败、冻结模型/源码、日志及诊断证据全部保留。

后续决策更新：用户随后明确要求使用剩余四次探索，已按[追加四版说明](exploration_batch.md)执行，不再沿用“保留四次”的先前建议。本版固定源码和正式编号不变，最新评分请看[五版汇总](all_today_status.json)。

11/14官方最终读回：本版58309573为COMPLETE、无error，Public MRR@25 **.473**，低于父版.488，停止当前12/300/noiso整体配方。其余单因素与排序四版各.488，不能将下降单归母体、预算或枚举某项；[最终解释及原值](../ROUND_RESULT_2026-11-13.md)。
