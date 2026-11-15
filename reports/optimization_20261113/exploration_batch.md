# 11/13追加四次探索提交

状态：追加四版均已正式接受，加首版今日五次已用完；官方额度读回已用5次、剩余0次。[接受和额度证据](formal_acceptance_summary.json)、[五版最新评分](all_today_status.json)。尚无新榜分，正式接受不等于隐藏完整推理成功。

后续官方结果更新（11/14）：五版已全部COMPLETE无error，首版生成扩展.473，追加四版均.488，无新高。上条“尚无榜分”和旧汇总的PENDING为当时状态，最新以[逐编号官方原值](../optimization_20261114/prior_batch_final.json)、[最终结果报告](../ROUND_RESULT_2026-11-13.md)为准。

| 追加版本 | 正式编号 | 实际云端路径 |
| --- | --- | --- |
| 只关闭额外同分异构化 | 58310788 | stormseye/casmi26-gen-noiso-only-1113 |
| 只扩大总生成预算 | 58310627 | stormseye/casmi26-gen-budget-only-1113 |
| 固定谱网络排序 | 58310918 | stormseye/casmi26-spectral-network-explore-1113 |
| 原v2 mean尾排序＋AB | 58310818 | stormseye/casmi26-mean-tail-with-ab-1113 |

用户在第一版58309573提交后明确要求：“随便提交四次吧别浪费次数，试试就试试”。因此，本轮继续用完余下四次；局部预筛无收益不再作为取消提交的条件，源码/输出正确性检查仍保留。13:14 UTC官方读回为今日已用1次、剩余4次，见[额度回执](exploration_prelaunch_limits.json)。这项本轮决策覆盖先前“只提交一版、暂留四次”的建议，不改变既有失败记录，也不重做produre1/2。

共同对照为冠军58156482，Public MRR@25 .488；Notebook SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。四版固定同样的数据来源及版本、公共神经/v2和原MASS；模型SHA、payload及具体脚本见各版recipe与源代码。没有新增训练、没有新增下载谱库；新缓存及测试产物均在D。

| branch | 相对精确冠军的改动 | 已有证据与限制 |
| --- | --- | --- |
| generation_noiso_control | 只关闭额外同分异构化；仍6母体/150总上限/双步，原head/AB保留 | 真实派生函数组件通过，零质量差枚举开关生效；新配置未重跑完整生产链 |
| generation_budget_only | 只把生成总上限150→300；6母体/双步/原同分异构化保留，原head/AB保留 | 真实派生函数与原枚举语义一致；预算可能增加噪声，也可能不触顶，未取得隐藏指标 |
| spectral_network_explore | 在完整冠军AB之后加入固定公开N1c谱网络和邻居候选结构一致性，强库命中整行保护 | 旧48诊断固定配方曾小幅负向，用户仍允许探索；本次不调系数，实测组件覆盖空图和非空图，不代表新CV收益 |
| head_mean_ab | 用原v2 mean替换晚接入trained two-head；保护前7及同式原槽位，保留原AB | 历史mean单版不带AB为.482；本精确组合未正式提交，可帮助区分head作用与外库作用 |

生成版共用已经走过真实生产路径的确定性engine指纹修复；其他两版保持原冠军主流水线。新分支逐对象核查原cell变化、实际模块和recipe指纹。可见云端Save&Run走fast_static，不能称真实全模型推理；正式code submission才会触发隐藏完整推理。局部组件验证和原12/300/noiso的两题整链证据分别记载，不混为四版整链已通过。

证据：

- [两条生成对照的方案与SHA](generation_controls_plan.md)、[真实派生组件检查](generation_controls_checks.json)、[独立源码审查](evidence_generation_controls_review.json)。
- [固定谱网络放行报告](evidence_network_release.md)、[实际追加cell冒烟](evidence_network_explore_smoke/verification.json)。只取revision2，父目录初版保留排错。
- head_mean_ab首轮组件测试误优先加载ICE自带旧RDKit，正式阶段尚未运行；保留失败日志，新进程改用已有官方2026.03.3依赖，不能直接放宽断言。
- head_mean_ab第二轮实际mean评分通过，但未带生产library_max证据，使AB保护上下文不全；原证据保留。第三轮只补齐上下文并重放AB和末审计，35.5秒通过、AB零命中恢复与原生产一致。[最终放行](head_mean_ab_release.json)、[完整排错](head_mean_ab_review.md)、[组件证据](../../runs/head_mean_ab_20261113_r3/verification.json)。这是组件检查，不是新全链或准确率验证。

新增四版使用单独不可变manifest与状态目录，已接受的第一版源码和manifest不改动。调度固定四个分支、逐版本只写一次、最多两个可见Notebook并行，每次正式写入前读官方额度。第一版一次加本清单最多四次，总计最多五次；未知写入结果不自动重试。

五版查分由同一个只读汇总进程串行写提升账本，先停止原单版记账进程并保留其状态快照，避免多进程覆盖。只有官方COMPLETE、无error、有限且严格超过当前最佳的Public分才能写成提升；PENDING、同分、降分和异常仍保存在全部提交/实验记录中。若新高来自追加版，按该版唯一机制或明确的整体变化记账。

决策：按用户要求提交四版探索，不预报涨分。待真实结果后再选择继续路线，归因以固定父版本及实际改动为准，不用本轮榜分反向调同一诊断面板。

## 云端对账及恢复

首轮调度中，noiso版在下载审计前遭遇只读ConnectionError，没有正式提交claim；预算版已正式接受58310627。另两版push已在服务端创建成功，但Kaggle自动用标题生成了不同slug，返回V1/无error/无无效数据源，主控因此暂停自动继续。已读取完整本人Notebook清单，并核对实际V1完整源码、数据来源、GPU、私有和离线设置，记录actual_target；未重新push。

- 网络实际路径：`stormseye/casmi26-spectral-network-explore-1113`。
- mean＋AB实际路径：`stormseye/casmi26-mean-tail-with-ab-1113`。
- [本人清单只读证据](exploration/reconciliation_owned_inventory.json)、各分支binding/cloud回执保留 requested_target 与 actual_target 绑定。

13:45 UTC官方读回今日已用2次、剩余3次，符合首版+预算版；恢复前核实其余三版均无submission.json、无已有下载审计目录，只继续已存在的云端V1审计及首次正式提交。[初轮状态快照](exploration/batch_dispatcher_status_initial_preserved.json)、[恢复说明](exploration/recovery_notes.json)。noiso版随后正式接受58310788；其余实时接受数量看汇总。API读取失败不计成正式评测失败，更不能盲目重新上传或重复提交。

13:49 UTC mean＋AB也正式接受58310818。谱网络在输出列表读取阶段再遇连接/ReadTimeout，未产生outputs或正式claim；13:52 UTC通过已有V1输出审计，首次正式提交接受58310918。[最后恢复回执](exploration/spectral_network_explore/manual_read_recovery.json)明确只重试尚无claim的读取，正式提交只调用一次，未重新push。原调度停止记录保留为历史，由接受汇总及各submission.json覆盖当前结论。

模型与全部正式提交索引已刷新（106条模型路径、29份不同内容、36次历史正式提交），`refresh_project_index.py --check`通过。提升账本当前仍.488，只在官方确认新高时更新；五版查分由同一后台进程继续，避免并行手动写账本。
