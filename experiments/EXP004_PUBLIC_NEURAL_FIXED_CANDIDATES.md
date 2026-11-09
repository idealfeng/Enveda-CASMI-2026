# EXP004：公开双/三模型固定候选对照

登记：2026-11-06。状态：**complete**。比较对象是CUSTOM共识排序层，**不等于完整V56最终输出、完整V30复现或Public Score**。[结果](../reports/EXP004_PUBLIC_NEURAL_2026-11-06.md)：MRR public0.845106、dual0.849074、tri0.850955，tri只有3例改善，收益集中，保留进入完整流程复验。

三臂在评价前固定：public原始Saner；dual=`.5*z(public)+.5*z(v2)`；tri=`.5*z(public)+.25*z(v2)+.25*z(v4)`。逐分子z-score采用ddof=0、标准差下限1e-6。原共识规则固定w_top=.25、w_mid=.75、rescue=0、offset=3。

使用既有`validation_flex_c2_20261105d`的48个查询、240谱和冻结候选；public复用已冻结评分，v2/v4按原始同一评分器串行推理。三checkpoint必须独立且hash固定，全部查询模型输入健康、分数有限、无缺失/重复候选，不允许模型缺失回退。上游候选证据列必须不变。

先要求public对照逐字节重现原`variants/submission_CUSTOM.csv`，再冻结三臂预测、检查官方评分身份候选集合相同，之后才计算真值指标。报告MRR/top1/top5/top25、NP/cross、逐分子与同式排名变化及配对区间；预登记dual-public、tri-public、tri-dual三项比较。不扫权重、不混改先验、物理、结构池或补位。

全部模型存在官方train full-refit曝光，48面板仅是参考谱隔离开发诊断。锁定250不预测、不评分；阳性结果不作为干净CV或必涨榜分证明。先根据模型真实覆盖、增益分散程度及面板分歧决定完整公开基线复现的优先级。

执行脚本：`scripts/run_public_neural_comparison.py`。默认新目录`runs/exp004_public_neural_20261106`；已有实验目录拒绝覆盖。原始0.479 Notebook和验证缓存保持不变。
