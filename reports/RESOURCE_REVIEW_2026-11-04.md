# 四份公开资源审查

日期：2026-11-04。目的：判断对当前冲银路线的增量价值。仅下载轻量源码/元数据，未执行新上游代码、训练模型、下载权重或数据。

## 结论与下载决策

| 资源 | 对我们的主要价值 | 决策与已完成动作 |
| --- | --- | --- |
| [José Statistical Tour](https://www.kaggle.com/code/josefreitasalvesneto/casmi-2026-a-complete-statistical-tour) | 来源库的域差异、数据质量、峰数组流式分析 | 已保存 V3 Notebook 与 metadata；作为 EDA 参考，关键 LB 结论须纠正，不新增模型管线 |
| [Lessons from ~30 submissions](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743254) | 双验证、同分子式硬负例、多种子方差、候选扩充的收益与代价 | 是经验帖，没有对应可拉取的代码；保存自己的审查摘要与来源，落实到实验设计 |
| [shiferaxa/casmi26](https://github.com/shiferaxa/casmi26) | 模块化验证/特征导出/自训 FPNet 代码及实验日志 | 最值得借鉴的工程；已获取固定提交源码快照，暂不复现其旧榜分管线或下载资产 |
| [Roman Peaks to Structures](https://www.kaggle.com/code/romanrozen/0-468-casmi-from-peaks-to-structures) | 在同一 Flex 基础上增加神经模型集成和 TAX 分类学先验的实验线索 | 已保存当前 V8 Notebook；先审计第二模型来源与回退行为，再决定新增模型消融，不直接下载整套输入 |

这四个链接实际是一份 GitHub 工程、两份 Notebook 和一篇讨论，不需要建立四套独立复现任务。

## 当前最重要的纠正

José V3 仍将占位 test.parquet 的来源与 Public LB 混为一谈。[主办方在原讨论中的澄清](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/741404)明确，Public LB 来自隐藏测试的 public split。我们继续把下载的 test 仅用于接口/运行检查，同时用独立验证辅助判断榜分变化；不采纳“因为 dummy 来自训练集，所以 Public LB 无用”的推论。

EDA 的部分样本计数也与当前本地文件不同。强度阈值、跨库精度过滤及检索基准先重算与消融，不能照搬作者的数字和最优性结论。详见 [EDA 源码审查](../third_party/jose_statistical_tour/README.md)。

## shiferaxa：取工程框架，先校准验证口径

固定提交 `41f0c5dde78e551fb5aedbb3421156a38b3f427d`，源码 ZIP 392,024 字节，展开约1.11MB/77文件，无模型、数据或 LFS。目录：`third_party/shiferaxa_casmi26`。这是源码快照，没有完整 Git 历史。

它的四通道骨干来自较早 prvsiyan/haideptry 谱系，与现有三套高度共享。最有用的文件是 `fork/harness.py`、`run_fork_val.py`、`dump_rank_features.py`、`train_ranker.py` 和 `kaggle/train_fp_v2/notebook.py`。采用前需统一官方评分身份与 RDKit 版本、核对评分排名语义、重建跨文件全局查询 group、移除占位质量范围限制并审计预训练污染。当前不把上游自报分数当成我们的新基线。

其训练配方使用6930-bit指纹头，当前强管线使用的10226-bit配置并不相同，不能直接互换 checkpoint；复用训练工程时需同步指纹定义、候选特征及模型接口。具体源码位置、下载 SHA 和可复用组件见 [仓库审查](shiferaxa_source_audit/REVIEW.md)。

## Roman：关注新分支，不重复已有骨干

当前 V8 的标题仍含0.468，源码内部出现0.480实验说明；这些文字不能单独证明当前版本的官方 Public Score。其冻结基础 Notebook、八个 helper 和四个 Saner 模型文件 pin 与本地 Flex V56 相同。潜在新增信息是第二神经模型集成及 TAX 先验，先核查来源/完整性，再固定候选做单因素消融。

第二模型相关输入含 `deleted/142141665`，关联 trainer 匿名访问返回403；源码允许缺失时回退复用公共模型，不能仅凭成功生成 CSV 判断双模型集成已运行。目前未下载相关权重，且没有固定的第二权重哈希，不声称其完整集成可复现。TAX使用的两张表本地已有，后续可单独做先验消融。当前 V8 绑定 scriptVersionId `365039563`，源码 SHA-256 为 `98008df2e1fbabf66acbdab8a5beff9550ccc4f1ed1447352672a9710628362b`；详见 [Roman 源码审查](../third_party/romanrozen_peaks_to_structures/README.md)。

## 对计划的调整

1. 保持现有三套冻结产物，优先建立官方身份分组的验证台。借鉴 shiferaxa 的特征缓存、查询 mask、失败分解结构，计算特征与重排分开。
2. 为 `VAL001_NEURAL_INCREMENT` 加入固定候选的同分子式硬负例子集；两套来源不同的验证并行，种子波动用我们自己的实验估计。np250 作为开发诊断面板，不称为未被使用过的独立盲测。
3. Saner 单模型的增量经过验证后，再评估 Roman 的第二模型集成和 TAX 先验；分开实验，不将两项一次加入后归因。
4. 自训 FPNet 的数据准备/训练配方可借鉴 shiferaxa，但先统一官方身份隔离和训练资产来源，再投入算力。

[经验帖审查与证据边界](resource_review_20261104/discussion_743254/REVIEW.md)。该帖的百分比与 seed 波动都是作者自身实验的观察，不用作我们固定的噪声阈值或隐藏类别比例。
