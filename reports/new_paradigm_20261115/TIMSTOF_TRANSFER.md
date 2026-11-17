# FIORA-OS → 官方 timsTOF：源码级迁移判断

2026-11-15。**判断：可做一次有明确数据门槛的 500 步迁移小试，不需要等 HCD 查询。原生训练代码足以构造真实监督，但不能直接用 `--resume old --instruments timsTOF`。** 最小版本先做官方 `[M+H]+`、单一已知碰撞能，增加独立 `timsTOF` 类别并迁移两处输入层。是否值得扩大训练，首先由 timsTOF 实测谱的**可解释碎片覆盖率**决定，其次才是显存和速度。

本次只读固定源码并写本报告，**未准备训练样本、未下载依赖、未迁移/改写 checkpoint、未启动训练**。500 步实际速度、峰覆盖率、MRR 和收益目前均未知。

## 固定来源与本次证据

- 源码 commit `e19ef82c9a6cb9dbac92bce23e914008f1aeb44e`；本地 `assets/research/fiora_os_20261115/source_checkout/`。
- 父权重 FIORA OS v1.0.0，MSnLib v7；SHA256 `83221e187991f116a8aed1bf272dd656cf31721a177dcbb0239f414c8df31a0e`，13,447,861 参数。
- 已有两结构 CPU 前向只证明可加载和有输入敏感性：[attempt2](fiora_canary_attempt2.json)。它不证明负离子质量定义正确，也不证明训练或 timsTOF 迁移成功。
- 主训练入口：[cli/train.py](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/cli/train.py)；可复用 `FioraModel`、`build/fragment/match`、PyG Data、`GraphwiseKLLoss` 与 Fabric loop，不需要重写一整套模型。

## 一、怎样显式增加 timsTOF，保留 HCD 语义

`CovariateFeatureEncoder` 将连续变量、离子类别、仪器类别和元素组成拼成一个向量。仪器还有一个独立 OTHER 槽；不是单独的可扩展 embedding 表。[源码](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/GNN/CovariateFeatureEncoder.py)

保持原离子顺序 **`[M+H]+,[M-H]-,[M]+,[M]-`**；即使小试只取正谱，也不缩减这四列。将仪器词表由 `[HCD]` 扩为 `[HCD,timsTOF]`：

| 特征 | 原 static 向量索引 | 新索引 |
| --- | --- | --- |
| CE、分子量 | 0、1 | 0、1 |
| 四个 precursor modes | 2–5 | 2–5 |
| HCD | 6 | **6，原列原权重保留** |
| timsTOF | 无 | **7，新独立列** |
| OTHER | 7 | 8 |
| 十种元素组成 | 8–17 | 9–18 |

因此 `static_feature_dimension` **18→19**；`static_rt_feature_dimension` **17→18**（当前模型无 RT/CCS head，但 metadata 仍需一致）。GNN/atom/bond embedding 和十通道输出都不用改。

只需按特征名称映射两处首层权重，而非重新随机初始化 head：

| state key | 原 shape | 迁移 shape |
| --- | --- | --- |
| `edge_module.dense_layers.0.weight` | 500×13538 | 500×13539 |
| `precursor_module.dense_layers.0.weight` | 500×3318 | 500×3319 |

这些 shape 由固定 config 与源码拼接顺序推导（GNN layer stacking 输出 3300 维）；迁移实现时必须再次断言实际 tensor shape。每个首层的 static 部分位于输入尾部，按上表搬移，非 static 列逐列复制。**新 timsTOF 列零初始化**，HCD、OTHER、元素和离子权重均保留。其他所有 tensor 原样复制，总参数仅增加 **1000**。保存新 params/state 到独立新目录，严格 load，不使用 `strict=False` 掩盖遗漏。

迁移后先做不训练的契约检查：同一 HCD 结构/CE/离子的新旧输出在浮点误差内一致（例如 max abs≤1e-6），旧 tensor 复制一致，HCD 仍是 6 号槽；timsTOF 必须编码到 7，不能编码 HCD 或 OTHER。这比只检查 shape 更能防止偷换特征。

**现成 CLI 的陷阱：** `train.py` 约 703–710 行在 `--resume` 时从旧 checkpoint 的 params/state 重新构建模型，前面按新 `--instruments` 计算的 `model_params` 并不会替换它。因此 `--resume old --instruments HCD,timsTOF` 会出现 19 维数据对 18 维旧模型的冲突。正确做法是先在**新资产目录**生成上述 migrated params/state，再 resume **迁移后的**模型；预处理参数也显式传同一词表和四个离子顺序。[模型输入拼接](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/GNN/EdgePropertyPredictor.py)、[graph head](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/GNN/GraphPropertyPredictor.py)

## 二、真实峰怎样成为训练标签：已有实现，不是代理

官方训练路径是：

1. 正确结构 SMILES → RDKit 分子图、atom/bond 编码。
2. `fragment_MOL(depth=1)` → 对每条**非环键单次断键**枚举两侧片段（不限化学 SINGLE bond 型）；环键在 `create_Fragments` 中直接返回空。保留 edge 与左右侧对应关系。
3. 计算每个片段在默认五个氢/电荷模式下的精确质量；将实测 m/z/intensity 传给 `match_fragments_to_peaks`，不是用“质量接近母体”替代反应或片段。
4. 一个峰对应多条 fragment/edge 时，强度按对应 edge 数分摊；每个 directed edge 有左右各五个通道，另加两个重复的 precursor 项。
5. 将计数向量变成 `compiled_probsALL = 2*counts/sum(counts)`，由模型 graph-wise softmax 对齐；`GraphwiseKLLoss` 再对每图归一化预测与目标，最小化 **KL(观测分布 || 预测分布)**，通过 `segment_ptr` 保持不同图分开。

对应代码：[FragmentationTree](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/MOL/FragmentationTree.py)（`create_Fragments`、`match_peak_list`）、[Metabolite](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/MOL/Metabolite.py)（约 453–636 行）、[Losses](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/GNN/Losses.py)。

**真实瓶颈：未匹配峰被丢弃，剩余部分重新归一化。** 因此即使 90% 实测强度无法用这些片段解释，KL 也可能下降得很好。先对固定 timsTOF 小批统计 `coverage`、`coverage_wo_prec`、`num_non_precursor_matches`、冲突数，以及因 `<2 matches` 被过滤的比例，按分子/CE 汇总；不能只看训练 loss 或匹配峰数量。若绝大多数只拟合 precursor 和少数碎片，500 步只是训练残缺标签，不应扩大算力。

默认容差还有单位陷阱：`DEFAULT_PPM = 100 * 1e-6`，函数参数实际是相对小数；`--ppm 100` 会极度放宽，沿用原始默认应是 **0.0001**。同时源码有最低绝对容差 **0.01 Da**。这个小试不扫容差；记录真实匹配率与冲突，不把高覆盖当成高特异度。[质量匹配实现](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/MS/ms_utility.py)

最小批先用 `[M+H]+`。当前 `Fragment.match_peak` 遍历正模式列表，而 `SimulationFramework` 的负谱分支对 fragment 改注释字符串，取 m/z 时仍用正模式 key；部分氢/电子质量差可被 0.01 Da 最低容差掩盖。这不是本报告已复现的性能故障，也不否定论文负谱结果，但负谱不宜夹进首个迁移 pilot。应另做 matched-label/forward-mass 精确契约，再扩大负离子范围。

## 三、官方 timsTOF 数据的最小准备，不依赖旧 HCD 面板

只用官方 **train** 的真实结构和谱。筛选原始 instrument_type 明确 `timsTOF`、`[M+H]+`、有限且**单值** CE；SMILES 有效且在模型原子/片段限制内。生成原生训练 CSV：

- `SMILES`：正确训练结构；按官方评分身份做结构分组，不能只按谱行随机拆分。
- `summary`：JSON，含 `name`、`collision_energy`（标量 eV）、`instrument: timsTOF`、`precursor_mode: [M+H]+`。
- `peaks`：JSON `{mz:[...],intensity:[...]}`，直接来自这条官方实测谱。
- `group_id`：稳定整数，所有同官方身份的重复结构/不同CE谱共享 ID。
- `datasplit`：固定 `training` / `validation`；原 old48 及之后独立评价身份在训练前排除。预训练 MSnLib 暴露仍单独记录，不能因本次 split 就称完全无污染。

**CE 是另一个实际门槛。** 原生 covariate 需要标量。虽然 Data 会保存 `ce_steps`，本版 `fabric_training.py` 并没有读取它进行混合能谱训练。不能把多能量合并实测谱简单配给均值 CE 并称条件匹配。先用确有单 CE 的子集；此子集的实际规模本次未统计。若没有足够单 CE tims 谱，需要先制定多个 CE 预测如何对应混合谱的训练契约，不能直接启动大训。

## 四、500 步如何落地，RTX4060/8GB 是否够

**8GB 值得试，但尚未实测 backward。** 原模型 FP32 参数约 51.3 MiB；全量参数+grad+Adam两份状态约 **205 MiB**，权重本身不是显存主项。主项是 `subgraph_features=True` 的边×子图节点×3300维 gather/池化和 autograd。源码 `MAX_SUBGRAPH_NODES=128`，默认 batch32 对大天然产物可能 OOM，不能照搬。

最小 profiling 方案：保留原 10层/300维/两个MLP架构与 `compiled_probsALL`/graphwise KL；从小图开始（例如≤64 heavy atoms、≤160 directed edges），**batch4、num_workers0、单卡、FP32**，不同时运行 P0 或其他大模型。这个限制只属于速度/梯度小试，不代表最终数据分布。以 full fine-tune 为首个单配方，低学习率如2e-5、无 scheduler；不以同一面板扫多个学习率/损失选最好。

原生 `train_fabric_loop` 有 epochs，**没有 max_steps 或 precision 入口**，默认 Fabric precision、Adam；不是宣称已有自动 500 步开关。可把“经过有效匹配过滤后的 training”固定为 **400 谱**、batch4、5 epochs，严格得到 **500 optimizer steps**，另有独立 validation；匹配后若不足400或实际 loader长度改变，应在新 runner中显式计步到500，不能把500 forward当500 train steps。训练 API 可复用但精确计步与 profiling 需要一个新的薄 runner，不修改冻结源。[Fabric实现](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/GNN/fabric_training.py)

训练入口还需 `lightning-fabric>=2.6,<2.7` 和 `torchmetrics`；两条 CPU forward 没有覆盖训练模块 import，本次未安装或验证它们。已有 PyG2.6.1 forward 在 torch2.9.1 上可用，backward/所有训练依赖尚未验收。缺失依赖只放 D 盘独立 target，不改现有 venv。

500 步应回报：预处理时间、实际有效结构/谱数、被过滤原因、匹配覆盖/冲突、首步/warm-up、稳定每步秒数、GPU峰值显存、host RSS、有限 loss/grad、step0 vs500 的固定留出 KL及不含precursor的谱相似度。**现没有可靠依据承诺几分钟或几小时**；CPU forward 0.014秒不能外推 GPU训练时间。500步只是可训练性/速度证据，不能直接拿来报排名增益。

## 五、这条路线与 ICEBERG/GLACIER 的独立性，以及放行条件

它是**另一套已训练的分子图/键片段模型，加上 timsTOF 域适配**，不再调整现冠军的融合权重或增加一个相同候选排序头。具体差异在 FIORA 的单次断键片段表示、左右侧氢变化通道及图级归一化目标；模型 SHA/架构与 ICEBERG/GLACIER 不同。它们都属于“正确结构→实测谱”的监督家族，使用同一官方数据也不构成新的独立采集信息，不能宣称训练目标完全正交。

FIORA 微调后依然**不生成库外新结构**；它有机会改善已有同分子式候选的谱区分，不能直接修补 Class-3 召回。训练 loss下降、输入敏感性或两个结构峰不同都不能证明互补。

推荐顺序：

1. 首先用小批官方 tims 正谱实际构造标签，检查**去precursor覆盖和歧义**；若片段表示严重不足，暂停扩大，而不是加GPU或调匹配容差。
2. 完成显式迁移和 HCD parity，再只跑一个500-step计时配方；若显存受限先减 batch，不改架构来凑“新模型”。
3. 固定真正留出的 timsTOF 查询和**现冠军同一候选集**，比较训练前/后 FIORA 分数、ICE/GL相关性、候选真结构 margin/排名、错误交集。先独立 evaluator，预测阶段不读truth；不在这批查询上选择融合权重。
4. 只有训练后在冻结留出上改善且与冠军错误有可复核互补，再做完整生产路径和提交。否则保留失败证据，结论仅针对该 fragment/域适配配方。

**当前下一件可执行工作是“真实 tims 标签覆盖 + 显式19维迁移”，不是等待HCD，也不是直接全量重训。** 本报告结束时该两项仍未执行；不把可行性判断写成训练完成。
