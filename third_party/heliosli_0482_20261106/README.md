# heliosli新公开源码审查（2026-11-06）

此目录仅保存两份公开Notebook的小源码、公共pull元数据和审查记录。没有运行源码、下载模型/谱库payload或提交Kaggle。

| 公开源码 | 当前pull版本 | 重要输入边界 |
| --- | --- | --- |
| [casmi26-0.482](https://www.kaggle.com/code/heliosli/casmi26-0-482) | V2 | 两个空dataset引用；标题0.482不是本审查独立读到的数值Score |
| [Happy to make the dataset public if it helps](https://www.kaggle.com/code/heliosli/happy-to-make-the-dataset-public-if-it-helps) | V5 | 一个空dataset引用；有独立rr3模型overlay |

来源拉取时间与源码SHA见各子目录`receipt.json`。服务元数据`lastRunTime`约2026-11-03，不能当作发布日期；官方排序列表的时间字段可能另有语义。完整静态事实在`STATIC_REVIEW.json`。

## 实质新增

主Notebook沿用0.468族公共骨干，尾部添加两个overlay：

内嵌基线与我们Flex V56均为59个cell，代码AST只在cell28环境观察断言不同：helios强制Python3.12/T4，V56允许3.12或3.13及非空GPU名称；其余代码语义一致。对应`BASE_COMPARISON.json`。不同原始frozen SHA主要不能被解释为换了预测骨干。外层基准融合配置及后处理也不同，不能把整个分数差直接归因于某一个overlay。

1. **rr3同式异构体模型。** 源注释描述候选1–2键切割碎片匹配、图网络与Transformer。需要外部`rr3_config.json`、`rr_deploy.py`、`rr_v3.py`、encoder、checkpoint及selftest，代码本身未内嵌这些模型文件。FREEZE模式保护训练结构位置，并跳过强谱库命中；三个自测与离线分数相关性须达到0.999。缺配置或失败时会跳过overlay，保留旧提交，因而“能运行”不等于复现该新增方法。
2. **更新外部谱库的高置信匹配。** 源码点名`heliosli/casmi26-extlib-v1`，说明收集MSnLib2026-07、GNPS2026-10及MassBank2026.03的train以外结构。按同离子模式、precursor窗、平方根强度余弦及峰数门槛匹配，将强命中移到或插入rank1；已有强library命中受保护。需要外部配置、哈希固定的reference parquet及自测。具体阈值在缺失配置内，不能凭代码猜出。

## 公开性核对

匿名官方dataset list（作者heliosli、pageSize100）完整返回9个公开dataset，均不是CASMI。显式查询`heliosli/casmi26-extlib-v1`元数据返回403。空引用与这些结果共同说明：**尚未建立完整公共payload可用证据**；不能仅凭空引用推断精确私有数据集名称或删除原因。

源码声称主办在discussion750684允许更新训练来源的谱库；本审查未取得该主办原文，不将源码注释当作授权证明。外部数据条款仍须逐来源核查。

新增谱库插入逻辑只按原始SMILES去重，没有统一官方评分身份去重这一层的充分检查；若借鉴，应补上评分身份合同并单独验证。模型内部`train_flags`及训练/验证隔离依赖外部代码，当前无法审计。

**决定建议：** 作为有价值的新信息来源归档，优先调查公开权重/引用修复及可审计外部谱库子集；现阶段不把bare source换上就称0.482复现，也不把标题0.482当作独立读到的Public Score。原0.479继续作为我们可复现的锚点，除非root对其他完整新方案另有确切证据。
