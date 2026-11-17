# FIORA原100开发查询固定候选组件评价

预声明主检验：按原8题输入的molecule_id集合排除后的92题；原8题仅作复现。全100保留为整体汇总，包含原两题无真实fragment监督者。
step0/500使用完全相同候选；完成全部预测绑定后才读取评价标签。

| 分组 | 模型 | MRR@25 | Top1 | Recall@25 |
| --- | --- | ---: | ---: | ---: |
| remaining92_not_in_pilot8 (n=92) | step0 | 0.697335 | 57/92 | 0.870 |
| remaining92_not_in_pilot8 (n=92) | step500 | 0.707332 | 58/92 | 0.859 |
| pilot8_reproduction_only (n=8) | step0 | 0.583333 | 4/8 | 0.750 |
| pilot8_reproduction_only (n=8) | step500 | 0.655435 | 5/8 | 0.875 |
| all_original100 (n=100) | step0 | 0.688215 | 61/100 | 0.860 |
| all_original100 (n=100) | step500 | 0.703180 | 63/100 | 0.860 |

remaining92_not_in_pilot8: 配对MRR增量 +0.009997，paired bootstrap95%区间 [-0.028883,+0.049772]；seed=20261116，10000次。


pilot8_reproduction_only: 配对MRR增量 +0.072101，paired bootstrap95%区间 [-0.044565,+0.255435]；seed=20261116，10000次。


all_original100: 配对MRR增量 +0.014966，paired bootstrap95%区间 [-0.023231,+0.053948]；seed=20261116，10000次。


完整质量窗候选召回 1.000；cap后 0.920。缺失分数0；cap漏真与候选本来缺失单独报告。

这是既用development100组件检查，非新独立holdout。区间只描述固定开发面板的查询重采样变化；不是完整冠军或榜分收益。没有根据本结果调融合、阈值、模型、候选或分组。
