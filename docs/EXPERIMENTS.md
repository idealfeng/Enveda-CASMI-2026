# 实验路线索引

2026-11-11整理。状态以所链接的正式回执及后续更新为准；本文件用于定位，不自行制造新指标。

| 路线 | 状态 | 入口与产物 |
| --- | --- | --- |
| 冠军：MASS＋晚接入head＋AB外库 | 已确认Public .488，保底主线 | [固定版本](../submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb)、[配方](../submission/optimization_20261109/mass_guarded_extlib/recipe.json) |
| A-only/B-only来源归因 | 已出分：A .482、B .488 | [正式结果](../reports/ROUND_RESULT_2026-11-11.md) |
| AB＋Enveda补缺/竞争 | 已出分：各.484，暂停这两种直接升首接法 | [正式结果](../reports/ROUND_RESULT_2026-11-11.md)；[实现](../reports/ENVEDA_MATCHING_IMPLEMENTATION_2026-11-11.md) |
| AB身份别名修复 | 已出分58222489=.488，无新高分 | [结果](../reports/ROUND_RESULT_2026-11-11.md)、[说明](../reports/IDENTITY_ALIAS_PROMOTION_2026-11-11.md) |
| 可信B前体纠偏 | 11/13可见400题真实匹配无新增合法身份命中，暂不提交 | [实际差异](../reports/optimization_20261113/massbank_match_delta.json)、[旧草稿](../submission/optimization_20261110/extlib_ab_bprec_trusted/recipe.json) |
| ozertuu V18及V80组件 | 源码/资产审查完成，未推理；第三权重读取403 | [比较与下一步](../reports/public_update_20261111/ensemble_comparison.md)、[资产](../reports/public_update_20261111/public_asset_audit.md) |
| produre1/2诊断基础 | 用户明确已完成，不重做；作为排雷和收缩探索空间的参考 | [定位与边界](../reports/ROUND_RESULT_2026-11-11.md)、[既有Q345复核](../reports/produre_review_20261111/Q345_NEW_REVIEW.md) |
| 11/12独立checkpoint、新匹配、生成及组合 | 最终匹配.488、Sanerbest .478、popwenman best及组合各.481；生成r3隐藏异常，无新高分 | [最终官方复核](../reports/optimization_20261113/prior_batch_reverified.json) |
| 11/13生成生产修复及扩展 | 正式58309573最终.473，低于冠军.488；生产修复成功不等于算法提升，停止当前整体配方 | [最终结果](../reports/ROUND_RESULT_2026-11-13.md)、[原实验记录](../reports/optimization_20261113/generation_experiment.md) |
| 11/13新证据预筛 | CE固定支持率零增量未提交；谱网络旧诊断小幅负向，后按用户要求固定策略探索提交；FRNet仅保留研究资产 | [筛选与边界](../reports/SUBMISSION_PLAN_2026-11-13.md) |
| 11/13用户指定追加四次探索 | noiso 58310788、budget 58310627、谱网络58310918、mean＋AB 58310818最终均.488，无确认新高。覆盖此前暂留四次建议 | [最终结果](../reports/ROUND_RESULT_2026-11-13.md)、[原实验说明](../reports/optimization_20261113/exploration_batch.md) |
| 11/13最终官方复核 | 生成扩展.473，其余四版.488，无新高；API未暴露更多小数 | [最终结果与下一轮取舍](../reports/ROUND_RESULT_2026-11-13.md)、[原值与指纹](../reports/optimization_20261114/prior_batch_final.json) |
| 11/14五次早位排序探索 | 已全部接受；目前head .470、GL .481、dual .449，mean58341597/library58341606待分，无新高。停止当前已降分配方 | [独立官方读回](../reports/discussion_review_20261114/latest_our_scores.json)、[实际接受汇总](../reports/optimization_20261114/formal_acceptance_summary.json)、[本轮评分](../reports/optimization_20261114/latest_status.json) |
| 11/14讨论与新信号路线 | extlib2 v1已取7文件约129MB，待净增覆盖核查；MIST MSG-only源码已取得，输入/正离子/4096FP限制已查。两路线均未新推理、训练或提交 | [论坛与源码结论](../reports/discussion_review_20261114/RECOMMENDATIONS.md)、[MIST可行性](../reports/discussion_review_20261114/mist_feasibility.md)、[新库下载回执](../reports/discussion_review_20261114/notebooks/extlib2_download_receipt.json) |
| 冠军错误驱动的候选证据融合 | 新主线待执行，先确认信息能纠正当前错误，再训练/提交；不重做produre | [路线依据](../reports/ROUND_REVIEW_2026-11-12.md) |
| 同仪器/跨库验证 | 已有诊断面板，曝光边界仍需保留 | [验证说明](../VALIDATION.md)、[48面板](../reports/VALIDATION_FLEX_48_2026-11-05.md)、[曝光审计](../reports/pretrained_exposure_audit.md) |
| EXP003逐谱GL证据 | 全量导出/核验与特征定义已有，非正式榜增益 | [设计](../experiments/EXP003_FORWARD_SPECTRUM_CONSISTENCY.md)、[全量证据](../reports/EXP003_GL_TRACE_FULL_2026-11-06.md) |
| EXP004公共神经固定候选 | 组件诊断已完成，tri实榜曾负向 | [报告](../reports/EXP004_PUBLIC_NEURAL_2026-11-06.md) |
| 原全量head、旧v4 tri、激进RR、V35 | 暂停原配方；保留负向结果 | [失败与再启动条件](LESSONS.md)、[全部正式分数](SUBMISSIONS.md) |
| Na GL异常 | 保留独立故障支线，未认定整管线修复 | [说明](../reports/OPTIMIZATION_BATCH_2026-11-08.md) |

## 模型和脚本怎么接起来

- 自训练多谱head：`runs/candidate_head_20261108/`；[训练说明](../reports/CANDIDATE_HEAD_TRAINING_2026-11-08.md)。`head_features.pt`是特征缓存，不是部署模型。
- 自训练同式残差head：`runs/isomer_head_20261109/`；[训练说明](../reports/ISOMER_HEAD_TRAINING_2026-11-09.md)。
- 公共Saner/v2/V80和E006组件：[逐文件模型表](MODELS.md)。嵌入Notebook的部署payload要以该版本recipe/observer为准。
- 提交工具：[说明](../reports/KAGGLE_BATCH_TOOL_2026-11-07.md)、`scripts/kaggle_batch.py`；旧批次脚本保持原名和原路径。

新实验使用 [模板](EXPERIMENT_TEMPLATE.md)，先登记父版本、假设和预期证据，再运行。失败也补结论，不只记录成功实验。
