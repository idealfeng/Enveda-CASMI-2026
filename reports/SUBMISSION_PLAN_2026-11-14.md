# 11/14五次：让已有证据影响早位排序

状态：五个探索版本已冻结并完成组件/回放核验，14:50北京时间启动云端调度。用户明确要求今天五次；正式接受数量及评分看[调度回执](optimization_20261114/batch_dispatcher_status.json)、[官方读回](optimization_20261114/latest_status.json)。不会把PENDING或组件通过记成新分。

11/14官方初始额度0次已用、5次可用。昨天逐编号最终为：大生成扩展.473，noiso-only、budget-only、谱网络、mean＋AB各.488；最佳仍58156482/.488。API原始分数字符串同样只到三位，不能确认更细小数的收益。[昨日正式结果](ROUND_RESULT_2026-11-13.md)、[逐编号证据](optimization_20261114/prior_batch_final.json)、[今日初始额度](optimization_20261114/initial_official_readback.json)。

共同父版本：精确冠军Notebook SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。保留原双神经、MASS、候选召回、数据版本、官方身份校验和AB。没有新增训练、没有扩大生成预算，也不重做produre1/2。模型权重位置及SHA沿用冻结recipe与MODELS索引。

| 分支 | 实际改动及假设 | 已知边界 |
| --- | --- | --- |
| head_prefix1_ab | 原晚接入trained two-head由保护前7改为保护首选，仍只在同式原槽位重排第2–25名，随后原AB | 原.488从未允许此head动第2–7名；旧全面head接在不同阶段曾降分，不等同本版晚接入 |
| mean_prefix1_ab | 原v2 mean晚接入同样放开第2–7名，随后原AB | 相对昨日mean＋AB只改变保护范围；相对冠军同时改变评分器和范围，收益不能单归某一项 |
| gl_evidence_early | 实际生产GL聚合分数与原排名先验结合，充分覆盖的同式原槽位早排序，保护首选及强参考证据 | 不冒称逐CE trace；原始逐谱未导出时只能使用实际聚合分数，缺失不补成真分 |
| dual_evidence_agreement（revision2） | GL与ICE充分覆盖且候选分数都明确高于当前首选时，按两模型平均标准化优势选择原rank≤10的同式候选门控升首，保护强参考命中 | 两者都胜过原首选不等于正确；只改候选次序。初版共同唯一winner零变化，保留但未提交；revision2未读标签、未扫系数 |
| library_consensus_early（revision3） | 原两实测外库匹配按多个去重查询谱的候选支持分布做同式排序，允许挑战首选、保留实际强AB命中行 | 不新增库，不重试前体质量修复，不改变官方身份；先前保护首选的组件无变化，保留其证据，改机制后不调系数或计算收益 |

本轮在固定策略下探索，不对同一已曝光面板反复调系数挑正值。组件小试复用已有生产中间数据/实际谱列，核查真实评分消费、原候选集合和身份、保护范围、输出CSV变化；不重新评估produre指标。原小样本可有标签元数据遗留，按此前披露只作部署组件，不称清洁CV或真实收益。新谱输入显式只取官方字段。

各版源码、recipe、metadata和branch_spec固定后由主控再次核查，仅上云私有离线V1。可见Save&Run用fast_static检查版本/审计，隐藏完整推理及分数仍由正式code submission完成；不能说五版都已本地整链运行。大型库与GPU作业串行，全部新产物和缓存在D。

调度每版最多一次push、一次正式写入claim；只在尚无claim、尚无部分审计产物时恢复只读连接失败，未知写入不重复。最多两个可见Notebook并行，总计不超过今日五次。正式接受、隐藏成功、榜分提升分别记录。只读watcher统一串行记新高，旧watcher若仍在运行先按确切PID/命令停止，保留状态证据后再接管。

下一步由真实五版Public结果判断早位证据的价值。组件负向、同分、异常与改动来源均保留；不把已完成生产验证或候选变化数量当成涨分。

## 实际核验与复现入口

- head/mean两版：各真实执行改动cells30–33，约98秒/版；两题都改变第2–7名，首选不变，原AB零命中。以本次评分重构prefix7，精确复现历史同评分输出，没有偷偷换评分器。[核验与SHA](optimization_20261114/prefix1_ab_components.json)、[放行](optimization_20261114/prefix1_ab_release.json)、[脚本与边界](optimization_20261114/prefix1_ab_review.md)。
- GL/dual两版：真实追加cell的fast及hidden组件通过，两个生产样本因强原库证据保护而最终不变；另仅用既有48条stage名单和真实聚合分数做无标签纯排序回放，GL改变44行、dual revision2改变12条首选，不计算MRR。初版共同唯一winner零变化，冻结保留未部署；最终pairwise规则不扫系数。[GL组件](optimization_20261114/evidence_early_components/verification.json)、[dual r2组件](optimization_20261114/evidence_pairwise_components/verification.json)、[放行说明](optimization_20261114/evidence_early_release.md)。
- 外库版：真实两题/20谱匹配324884条参考谱，691个谱对、60个候选合格对。revision2去重谱且保护首选，零最终变化；fixture首选弱支持导致断言已修正检查对象，原失败保留，未改系数。revision3仅放开首选保护及对应观察器，用同一批真实分数回放，改变1条首选，fast追加cell真实通过。没有新一轮matching或完整模型，强AB保护在门控夹具验证，两题实际AB零命中。[r2真实匹配](../runs/library_consensus_early_20261114_r2/verification_completed.json)、[r3回放](../runs/library_consensus_early_20261114_r3_replay/verification.json)、[边界和排错](optimization_20261114/library_consensus_review.md)。
- 主控独立核对：五个stage均真实`local_preflight`通过，原cell变更范围正确、数据版本相同、title对应slug、分支末audit与各recipe精确绑定；库取revision3，dual取revision2。全量不可变[manifest](../submission/optimization_20261114/manifest.json) SHA `8a4897ca2cb8f21c0eb12807c4f256991b3e1fec344511c7d79528ed330eb719`。[独审](optimization_20261114/independent_static_review.json)、[放行绑定](optimization_20261114/release_gate.json)。
- 查分记账：16项隔离fixture检查通过，没有写真实账本；只记官方确认新高且附实际变化及归因边界。[查分器检查](optimization_20261114/gain_watcher_review.json)。只读传输错误在无正式claim、无部分审计产物时才恢复，三个相关边界检查通过，不重试未知写入。

所有构建脚本、实际运行命令入口与产物路径见各路线报告；新权重内容数不变。两题生产中间数据不等于精确冠军全测试候选，旧48只是无标签组件行为回放，不是新验证台成绩。正式提交、模型、训练源、错误日志和审计原路径保留，完轮后刷新本地索引和`--check`。

## 云端执行快照

15:06北京时间：head_prefix1_ab正式接受58334939，gl_evidence_early接受58335002，dual_evidence_agreement接受58335047，三版当前PENDING。mean_prefix1_ab及library_consensus_early的V1已创建且源码绑定通过，仍在云端QUEUED，未产生正式提交claim；不把它们写成已用次数。[调度](optimization_20261114/batch_dispatcher_status.json)、[接受汇总](optimization_20261114/formal_acceptance_summary.json)、[评分](optimization_20261114/latest_status.json)。

07:03 UTC只读GPU额度：总30小时、已用约2分23秒、无预留，排队不是本周额度用尽。[额度证据](optimization_20261114/accelerator_quota_check.json)。mean可见V1尚无日志/失败信息，未取消或重建。两版完成可见运行后，现有调度核验输出并首次正式提交，最多6小时；未知写入不重试。正式接受后隐藏运行由Kaggle执行；剩余两次正式写入仍依赖本地后台存活。

本地另启通用`watch_batch_accounting.py`，只读取固定回执并在新增编号后自动刷新模型/提交索引和`--check`，不进行云端写入，也不写提升账本。查分与新高来源归因由唯一ledger watcher执行。背景任务、stdout/stderr和pid均在本轮报告目录，后续窗口先看动态汇总，无需重新构建五版。
