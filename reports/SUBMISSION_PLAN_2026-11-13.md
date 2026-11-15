# 2026-11-13：按实际信息增量筛选提交

官方读回：今日0次已用、5次可用；冠军仍58156482/.488。昨日最终为新匹配.488、popwenman best集成.481、Saner best集成.478、组合.481、生成隐藏异常。今日停止同系checkpoint混合及未经胜出证据的组合，不重做produre1/2。

## 本轮实际筛选

| 候选 | 实际新内容 | 进入正式提交的条件 |
| --- | --- | --- |
| 生产生成修复 | 锁实际FROZEN determinism-patched engine；12母体/300产物/双步/no-isomer算法沿用昨日未取得有效分的方案 | 必须真实外层Notebook从生产初始化到最后CSV通过；两题组件检查不再代替该路径 |
| 可信MassBank precursor修复 | 修复1281条元信息可信记录的索引 | 已在可见400目标/1213谱真实匹配比较，无新增合法身份命中，暂不提交；不把合成参考自匹配变化当隐藏收益 |
| GL跨CE支持率 | 固定0.10、保留top1/同式原槽位的实际融合回放 | 45条精确复现control；10条合格、9条尾部变化，但MRR不变，暂不提交、不扫系数 |
| target-target谱网络一致性 | 复用新公开N1c谱相似网络、相邻目标top候选结构FP一致性，强AB/原库命中保护 | 旧48数据固定配方MRR .838914→.836136，暂不提交，不事后调阈值凑正增益 |
| FRNet候选条件碎片证据 | 新公开GINE结构编码＋峰Transformer，非v2同系checkpoint | 先核训练来源、许可和真实评分可用性；许可/来源或整路径不清，不部署 |

公开小量源码快照在 `optimization_20261113/public_short/`。此处的来源排名不包含官方真实score值，标题或自报不是我们的已验证榜分。N1c来源为analyticaobscura/casmi-2026；FRNet来源为agentili/casmi26-fr-reranker-blend，公开prvsiyan V50已关闭原FR尾部blend（作者记述曾降分），因此不能直接照搬旧blend当更强baseline。

## 运行与资源

- 生成完整本地生产子集用两query及20谱，真实test/sample均为两行身份范围，保留原/kaggle绝对路径和realpath断言，D盘目录bind mount到WSL。
- 遍历原外层所有代码cell，`KAGGLE_IS_COMPETITION_RERUN=1`，不跳过真实模型或注入旧评分。此次测试输入误保留了诊断面板的结构标签元数据；必须独立核对生产代码是否消费，不能称无标签验证或计算收益。唯一资源适配为cpu_count=4，以适合本地7.5GB RAM；该运行不证明400目标隐藏全集预算。
- 大库/GPU作业串行；本次E2峰内存接近WSL上限。其它组件仅用轻量缓存/元信息比较。
- 通过后建立新的固定stage/recipe/manifest和一次性code submission。源码、数据、生成候选到ranker/后续head/AB、最终CSV全部绑定。正式接受不等于隐藏评测成功。

本文件是执行中的候选筛选记录，不宣称五版已准备或已提交。额度用于可解释、能实际改变预测并可运行的候选，不用完五次本身不是成果。

13:01 UTC官方只读复核仍为今日0次、剩余5次。生成真实生产子集已完成：2327秒，四份审计均为hidden_full/passed，最终两行CSV SHA为`e58cde08da50a70a28b35484ef34e62917b56bd3ad648c3a54a594b6aa519416`。实际生成308个候选，第7–12母体调用12次，1条查询触及300上限；这些数字不代表正确召回。待独立源码/输出审查放行后，按[固定单版manifest](../submission/optimization_20261113/manifest.json)执行上云与正式提交；尚不能称隐藏评测成功。

13:07 UTC已完成独审、云端可见静态运行及输出审计，正式接受 **58309573**，当前PENDING。今天实际使用1次，先保留4次；调度已正常结束，只读查分与新高分记账继续。[完整实验记录](optimization_20261113/generation_experiment.md)、[官方状态](optimization_20261113/latest_status.json)。

后续用户明确要求“随便提交四次吧别浪费次数，试试就试试”，覆盖上条暂留建议。已准备noiso-only、budget-only、固定N1c谱网络、v2 mean＋AB四版，13:38 UTC启动追加调度；局部组件通过，未重跑四版完整模型。首版与追加manifest均保持固定，由同一个汇总进程查五版分数与记账。[追加方案与证据](optimization_20261113/exploration_batch.md)、[当前五版汇总](optimization_20261113/all_today_status.json)。

最终执行：追加四版已全部正式接受，今天总计5次、剩余0次。新增编号58310788、58310627、58310918、58310818；首版58309573。云端实际slug差异与只读网络失败已核实恢复，无重复push或未知正式写入重试；尚无新榜分。[正式接受核实](optimization_20261113/formal_acceptance_summary.json)。
