# 经验与失败路线

更新：2026-11-11。这里记录可复用的判断和适用边界；原始日志保留在原处。负向结论针对具体配方，不能扩大成整个方法无效。新证据出现时修订状态，并保留旧证据链接。

| 路线/问题 | 实测或发现 | 当前判断与再次尝试条件 | 证据 |
| --- | --- | --- | --- |
| public/v2双神经 | Flex .479→.480 | 有一次正向Public实测；不是所有基座上都保证提升 | [归因](../reports/ROUND2_ATTRIBUTION_2026-11-07.md) |
| 原v4三模型组合 | .5public/.25v2/.25v4得到.475，低于dual .480 | 暂停原v4比例。新checkpoint须先查SHA；V80 final实为现用v2重复，验证阶段best才是不同权重 | [归因](../reports/ROUND2_ATTRIBUTION_2026-11-07.md)、[SHA核对](../reports/optimization_20261112/v80_identity_discovery.json) |
| 公开V80 final被误当新权重 | 11/12发现其SHA与现用v2完全相同；两条原计划都是重复配方 | 已取消，未浪费提交；验证阶段best checkpoint才是实际不同候选。模型先按SHA确认独立性，再讨论互补 | [实际文件核对](../reports/optimization_20261112/v80_identity_discovery.json) |
| 强学习RR | 激进版本.436 | 停止原强度直接叠加；先验证特征、分布与可动名次 | [归因](../reports/ROUND2_ATTRIBUTION_2026-11-07.md) |
| V35整版及其调整 | baseline .469、弱先验 .476、v2强调 .458；均低于MASS .481 | 不继续围绕该差基座扫参数；不能把一项混杂改动说成根因 | [正式分数索引](SUBMISSIONS.md)、[当轮设计](../reports/ROUND2_ATTRIBUTION_2026-11-07.md) |
| 新多谱head全面接入 | 两seed .465/.470 | 当前全量接入负向；不等于同一head晚接入也无效 | [训练与处置](../reports/OPTIMIZATION_BATCH_2026-11-08.md) |
| head晚接入、保护前7 | .481→.482 | 有整套晚接入增益；后续old mean同位置也.482，尚不能证明新训练目标单独贡献 | [提升账本](../reports/IMPROVEMENT_LEDGER.md)、[11/10计划](../reports/SUBMISSION_PLAN_2026-11-10.md) |
| 仅尾部新同式残差 | .482 | 当前未见超过旧最佳；保留权重与训练记录，避免重复训练同一配方 | [训练记录](../reports/ISOMER_HEAD_TRAINING_2026-11-09.md) |
| 外部实测谱AB及来源归因 | 固定.482追加AB得.488；本轮B-only .488、A-only .482 | 优先B；同分不证明A在每条查询或Private上贡献严格为零 | [本轮结果](../reports/ROUND_RESULT_2026-11-11.md)、[冠军配方](../submission/optimization_20261109/mass_guarded_extlib/recipe.json) |
| Enveda直接升首 | 补缺和竞争各.484，均低于.488 | 暂停这两种接法及其阈值扫描；保留数据，别把数据无用和接法负向混为一谈 | [本轮结果](../reports/ROUND_RESULT_2026-11-11.md) |
| AB已有结构别名提升 | .488，与冠军同分 | 暂不继续同修复单独提交；不能据此断言预测完全相同 | [本轮结果](../reports/ROUND_RESULT_2026-11-11.md) |
| 部署检查目录未模拟实际CODE | 生成r2本地使用code夹具通过，云端实际p2s_code导致最终audit找不到文件；未正式提交 | 模块自检以__file__定位，runner核实际路径；测试使用真实目录布局，不能因多项检查通过就推定布局一致 | [r3修复](../reports/optimization_20261112/generation_r3_recovery.md) |
| 两题组件小试未走完整生产初始化 | 生成r3正式隐藏重跑异常；排查确认FROZEN先修改engine，而runtime仍锁原始SHA，组件小试直接导入原assets漏掉 | 修复仅解除特定缺陷，不等于可部署；必须从真实FROZEN初始化到最终CSV检查，fast/fixture项数不能代替端到端 | [本轮复核](../reports/ROUND_REVIEW_2026-11-12.md) |
| 生成实际生产路径修复复核 | 11/13锁定FROZEN修改后的engine，20个外层代码cell到最终CSV真实两题2327秒通过；原排序/head/AB全保留 | 足以支持一次正式评测，不证明隐藏全集预算或榜分。输入误留标签元数据，源码审查未发现消费，不能称无标签验证；308个候选/14入最终名单不是增量召回 | [独立放行与边界](../reports/optimization_20261113/evidence_generation_release.md) |
| 11/13生成扩展与单因素 | 11/14官方最终：12/300/noiso .473；仅noiso .488、仅budget300 .488 | 停止当前整体扩展，不将下降单归某开关；小面板候选多不等于Public收益 | [五次最终结果](../reports/ROUND_RESULT_2026-11-13.md) |
| 11/13尾部评分/谱网络 | mean＋AB .488、固定N1c .488，无确认新高 | 保留前7的改动可能只影响低权重名次，不能据同分证明预测一致；下一轮直接检验早位规则，不重复同配方 | [官方原值](../reports/optimization_20261114/prior_batch_final.json) |
| 11/14早位固定分数干预 | 当前已出分：trained prefix1 .470、GL early .481、dual pairwise .449，均低于.488；另外两版尚待分 | 停止当前三配方及直接扫同权重；应引入新实测参考/独立表征后训练证据适用性，不能据此说全部GL或排序学习无用 | [当前官方读回](../reports/discussion_review_20261114/latest_our_scores.json)、[讨论及路线调整](../reports/discussion_review_20261114/RECOMMENDATIONS.md) |
| 新公开0.500+标题 | 11/14源码V45实际写Target0.500+，VerifiedBaseline=.487；旧slug404且新slug已找到 | 目标标题不算已达榜分；源代码、实际资产、正式分数分别核对，不再据标题直接认定更强 | [六份源码复核](../reports/discussion_review_20261114/notebooks/NOVELTY_REVIEW.md) |
| 同分更细小数的猜测 | 11/14读回public_score原始字符串也仅0.488或0.473 | 未暴露更多精度，不能说小数位提高，也不能推测Private；记账按官方可验证分值 | [精度与结果](../reports/ROUND_RESULT_2026-11-13.md) |
| Saner best-validation集成 | 11/12实际.478，低于冠军.488 | 暂停当前配方；不同SHA/finite分数不是互补收益证据，不继续同系checkpoint混合扫参 | [官方读回](../reports/optimization_20261112/review_live_results.json) |
| popwenman best及其匹配组合 | 11/12最终各.481，低于.488 | 暂停这份验证阶段checkpoint配方及组合，保留最终full-refit原v2 | [最终读回](../reports/optimization_20261113/prior_batch_reverified.json) |
| 谱网络固定配方 | 11/13旧48诊断 .838914→.836136，未在精确.488评估；后按用户明确要求正式探索58310918 | 预筛负向边界保留，固定策略未扫阈值，隐藏及榜分待官方结果；有新名单变化不等于收益 | [固定策略结果](../reports/optimization_20261113/network_fixed_policy_diagnostic.json)、[探索回执](../reports/optimization_20261113/formal_acceptance_summary.json) |
| GL跨CE支持率 protected-top1臂 | 11/13真实融合回放45/45对照重现，9行尾部变，MRR零增量 | 当前保护范围中合格难例少，不能推断所有跨谱信息无用；不以接口通过安排正式名额 | [回放报告](../reports/optimization_20261113/evidence_review.md) |
| Na分路GL | 正式重跑出现异常，无有效分 | 本地单query可运行不代表整管线已修复；未知CE NaN、部分有效输出兼容需继续查 | [故障与限制](../reports/OPTIMIZATION_BATCH_2026-11-08.md) |
| produre1来源归因 | 旧Flex基座且缺官方身份guard，若干提议有重复身份 | 不能据原表断言B库是.488主增益；必须在精确父版本重做 | [独立复核](../reports/produre_review_20261110/PRODURE1_REVIEW.md) |
| 旧生成Q4代理/oracle | 使用truth升首，不是实际ranker收益 | 旧代理数值不当作可部署改进；勿与后续真实Q4混用 | [旧复核](../reports/produre_review_20261110/PRODURE2_REVIEW.md) |
| 新Q345真实160特征 | 19/48恢复、12首选、MRR@25 .295833；恢复子集19/19进25 | 真实生成排序证据；但有一例残留同结构参考，且生产已有6父体。12父体仍待严格成对实排 | [新复核](../reports/produre_review_20261111/Q345_NEW_REVIEW.md) |
| 新公开ozertuu V18 | 同一底层生成器；新集成/外库过滤/先验规则 | 源码已拉；第三权重403。不能少一个模型仍声称完整复现 | [比较](../reports/public_update_20261111/ensemble_comparison.md)、[资产](../reports/public_update_20261111/public_asset_audit.md) |

## 防止重复踩坑的规则

1. Public分、完整管线验证、组件诊断、接口检查分别标注。fast commit的占位输出不证明真实推理成功。
2. 对照写明父版本、候选集合、实际模型SHA、改动位置。不能把多组件净增全算到某一个参数。
3. 使用官方结构身份检查重复、目标排除和泄漏；raw SMILES、14/27位InChIKey不能混用。
4. 生成器的“造出来后100%进25”是条件结果；总体召回分母仍是全部查询。
5. 新head划分Train/Eval不能消除预训练encoder的曝光；参考排除要按全部同结构身份处理。
6. 自动扫描所有final_model.pt会混入重复或不兼容模型；部署明确固定名单、顺序和SHA。
7. 未知提交结果先对账，不能自动重提；PENDING不算零分，有error的COMPLETE不算有效分。
8. “某天不占名额”不能变成用户永久约束。用户已明确允许生成路线按证据参与选题。
9. Kaggle接受提交请求、可见Save&Run通过、隐藏评测成功、榜分提升分开报告。异常无有效分不是零分，正式接受后异常仍会占额度。默认不为凑数重复配方；用户明确要求本轮用完探索额度时按其授权执行，保留预筛负向及无新完整运行的边界，不预报涨分。

更新时补充反证和适用范围，不删除旧失败记录；模型仍按 [模型索引](MODELS.md) 查找。

produre1/2定位：已完成的诊断基础、排错及探索空间收缩，不是待照搬的优化任务。复用validation/q345_lib等入口及既有结论，不重做两组实验。质量容差无增量、Class2生成冗余、代理不可靠等都有各自实验范围；小样本+1/48不能直接证明方法对隐藏测试有害。母体数是候选杠杆，不是已证明的唯一瓶颈。后续名额按可部署新策略选择。[用户澄清及下一轮取舍](../reports/ROUND_RESULT_2026-11-11.md)。

11/13追加探索的组件排错：mean＋AB小试误优先加载ICE旧RDKit，改为已有官方2026.03.3依赖；第二次遗漏生产library_max上下文，造成与原生产不同的AB命中，补齐上下文重放后恢复一致。两次均未涉及云端正式阶段，原证据保留。局部组件也要带齐生产保护输入，不能把缺上下文的变化当收益。[排错与最终证据](../reports/optimization_20261113/head_mean_ab_review.md)。
