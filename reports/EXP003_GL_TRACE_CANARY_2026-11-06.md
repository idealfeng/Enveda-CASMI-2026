# EXP003：GL逐谱观测等价检查

2026-11-06。独立只读核验：**passed，30/30项通过**。这里只检查trace观测是否改变原计算，没有读取真值、评估排序或预测锁定250。

- 2个query、16个候选、17张原始H+谱、15个不同query/CE组；适用候选—谱对为136，不是跨query的笛卡尔积。
- control与trace输出字节、JSON数值以及query/候选顺序完全一致。
- 逐谱记录136条，覆盖记录17条；无重复或缺失pair，官方2026身份映射全部一致。
- 16个候选均值均可由逐谱值重构；独立重构精确相等16/16，最大差0。
- 两臂均CUDA、RDKit2025.03.6，模型status=ok、2/2分子与16/16候选评分完成，预测/特征错误0；每臂120个预测job。
- 原45分子输入、冻结canary输入、官方身份sidecar、GL原源码、wrapper、执行脚本和旧site marker哈希均符合准备回执。两臂日志均确认site marker匹配，bootstrap直接复用，未重新安装。

输出SHA：`df5fb1aa4e039c71c05746a6ff3d1504b76f525af04c2b7c8121cbd31f8ad93f`。原始独立检查为`runs/exp003_gl_trace_canary_20261106/canary_verification.json`；准备回执与两臂产物在同一目录。

该结果只允许进入逐谱一致性特征设计，不能据此声称MRR或Public Score提高。谱图记录和CE组也不自动等于独立证据；后续须处理重复谱。两次总耗时含模型装载，不能当作纯trace开销对照。
