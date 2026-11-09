# EXP004：公开双/三模型固定候选对照完成

范围：CUSTOM共识排序层，位于physical/merge/final prior之前。48个开发查询、240谱、每臂1200候选。**存在官方train full-refit预训练曝光，不是干净CV、完整V30复现或Public Score。**

| 臂 | 权重 | MRR@25 | cross 24 | NP 24 | top1 | top25 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| public | 原Saner | 0.845106 | 0.717989 | 0.972222 | 38/48 | 46/48 |
| dual | .5 public + .5 v2，各query z-score | 0.849074 | 0.718981 | 0.979167 | 38/48 | 46/48 |
| tri | .5 public + .25 v2 + .25 v4 | 0.850955 | 0.722743 | 0.979167 | 38/48 | 46/48 |

dual−public为+0.003968，分子配对95%区间[−0.003472,+0.013641]；tri−public为+0.005849，区间[0,+0.015026]。下界恰为0，不能称确定显著。tri−dual为+0.001881，区间[0,+0.005498]。

tri相对public只有3个真值排名改善、0退化：cross的7→4、18→16，NP的3→2。NP单例贡献约59.4%，最大两例合计约97.5%；两面板均值为正也不能替代广泛复验。三臂逐查询首选评分身份均未改变，收益来自尾部排序。

## 工程核验

- public原样逐字节复现旧CUSTOM输出，所有候选评分身份集合固定。
- 三checkpoint独立、SHA及代码/config已固定；预处理features、fp_bits、max/min_peaks相同，逐行实际n_spectra/n_adducts也相同。
- v2/v4分别55.78/53.13秒完成48查询/1200候选，全部neural_ok、有限分数、无回退。总实验127.71秒。
- 逐query ddof0、std下限1e-6，预登记3组比较；没有扫权重、改结构池、先验或物理层。
- 原输入文件哈希前后相同，锁定250未预测/评价，未训练或提交Kaggle。
- 5项索引/覆盖/边界单测通过；独立复核41/41，重新计算官方身份指标、混合分值、bootstrap和哈希一致。

## 决定

保留tri进入完整公开配方的部署复验，dual作为较简单对照。这里不能给0.479榜分直接加0.005849，也不能认定新权重已经带来稳定泛化增益。完整V30还包含更强NP先验、leader规则、LOTUS membership与回填；完整得分必须单独复现。

原始记录：`runs/exp004_public_neural_20261106/report.json`及各臂CSV、逐模型parquet、receipt与日志。独立复核：`reports/exp004_independent_review_20261106.json`和同名Markdown。执行代码：`scripts/run_public_neural_comparison.py`。
