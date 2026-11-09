# CASMI26 提升记录

每次真实 Public 最佳分提升后更新此表，并在 `improvement_ledger.json` 保存可核验记录。记录整个有效改动；只有单因素对照支持时，才归因到其中一个组件。Public 提升不等同于独立验证集或 Private 提升，同一显示分数不代表预测相同。

| 日期（北京时间） | 旧最佳 → 新最佳 | 真实提交 | 可以确认的提升来源 | 尚未拆清的因素 | 后续动作 |
| --- | --- | --- | --- | --- | --- |
| 2026-11-05 | 初始 → 0.479 | 58021256，Flex V56 V2 | 原公开 Flex V56、公开权重及资产的复现；作为起点，没有自研增量归因。 | 不适用。 | 保留固定版本作为历史锚点。 |
| 2026-11-07 | 0.479 → 0.480 | 58063780，Flex dual only V1 | 在同一 Flex 基座内，将原神经组件换成固定 public/v2 双模型组合。 | 不能归因于某一个 checkpoint，也没有证明单独模型泛化更好。 | 后续完整 tri 得 0.475，停止该三模型组合。 |
| 2026-11-07 | 0.480 → 0.481 | 58063883，public MASS repro V1 | 完整公开 MASS 配方复现，包含原双模型及不同的先验、质量首选链、LOTUS/outside 处理。 | 多个变动一起发生；不能将整个 +0.001 称为质量项或自研提升。 | 保留完整 MASS 为研发基座；V35 多项替换 0.469，撤回。 |
| 2026-11-09 核验 | 0.481 → **0.482** | **58129661**，guarded head tail 1108 V1 | **整个旧 MASS 流程及最终前 7 名保持；在最终 CSV 后，用冻结 v2 编码器和两个新训练的多谱 head 分数，仅重排第 8–25 名同分子式候选的原槽位。** 候选集合、公式槽位与查询顺序保持。 | 新 head 的作用和晚接入原 v2 排序的作用未分离；仅一次 Public 正向结果，尚不能称稳定泛化增益。原内部全量接入 seed0/1 为 0.465/0.470，但接入位置不同，不能单独证明只适合尾部。 | 今日先做晚接入 v2 mean 消融、保护前 3/前 1 的范围对照；新训练目标改为同式比较和有界残差。 |

最新记录由官方 API 于 **2026-11-09 15:08（北京时间）**核实：58129661 COMPLETE、Public 0.482、无错误。证据：[本轮初始线上快照](optimization_20261109/initial_live_status.json)、[冻结配方](../submission/optimization_20261108/mass_guarded_head_tail_1108/recipe.json)、[正式提交回执](optimization_20261108/mass_guarded_head_tail_1108/submission.json)。

后续每次更新包含：父版本与提交编号、准确源码和权重指纹、唯一或成组改动、指标变化、负向对照、归因边界、保留或停止的决策。显示到三位小数的分差按显示差记录，不假设隐藏精确差值。一天内不以反复查看榜分选训练步数或权重。


<!-- gain-ref: 58156414 -->

2026-11-09 20:23 官方确认 **0.482 → 0.484**，提交 **58156414**。

提升来源：Alex V12完整公开外库配方复现，使用其实测谱匹配和原public/public神经路径。

归因限制：与我们0.482同时存在模型路径、先验与外库差异；不能把整个差值称为单一外库或自研收益。

固定源码 SHA：`1838e7c7c07177b7e6976c9b4c1e9c566769b2c88c2a699ce002bffa174dbbee`。证据：[stormseye/casmi26-public-alex-extlib-1109](https://www.kaggle.com/code/stormseye/casmi26-public-alex-extlib-1109)、[reports/optimization_20261109/public_alex_extlib/score.json](optimization_20261109/public_alex_extlib/score.json)。


<!-- gain-ref: 58156482 -->

2026-11-09 20:42 官方确认 **0.484 → 0.488**，提交 **58156482**。

提升来源：保留完整0.482输出，在其后增加Alex V12两外部实测库匹配首选提升及官方身份合法性保护。

归因限制：单独增加一整套外库匹配组件；不能拆分库A、库B或阈值贡献，也不是新增训练收益。

固定源码 SHA：`2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。证据：[stormseye/casmi26-mass-guarded-extlib-1109](https://www.kaggle.com/code/stormseye/casmi26-mass-guarded-extlib-1109)、[reports/optimization_20261109/mass_guarded_extlib/score.json](optimization_20261109/mass_guarded_extlib/score.json)。
