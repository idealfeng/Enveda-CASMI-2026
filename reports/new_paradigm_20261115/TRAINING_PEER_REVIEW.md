# FIORA timsTOF 原生训练小试独立审查

2026-11-15。审查范围是冻结数据/监督定义、19维迁移、薄训练器、从channel到真实m/z的评价契约。没有修改准备器或训练器、没有训练、没有读取step0/500等development模型成绩。

**结论：当前冻结源码和498个实际ready图的监督检查全部通过，可进入一次固定500 optimizer-step训练/测速。** 这仅是实施契约放行；实际训练梯度、显存和留出变化由本轮run据实报告，不预报排名收益。

## 固定版本

| 对象 | SHA256 |
| --- | --- |
| 实际graph准备器 `scripts/prepare_fiora_tims_pilot_20261115.py` | `e5dddf8ab9339ed22472e5560406d266addb5417af50694f96932accb1900418` |
| 训练器 `scripts/train_fiora_tims_500_20261115.py` | `0fea8fed747fef37c72a85b3b2d5965d388ee2366814d017eb40e6cad7d4dcc2` |
| metadata-only `selection.json` | `2b4ecd92fbf0f175b8533c1678bf693831e9ef1f75bb48084cf32f0169c2213d` |
| 完整graph `index.json` | `622f87ad8098ac98318d326eddb5288cc2bd3ea6a1c69f37de5abc477ff6a8a5` |
| 19维迁移state | `38d3208f4c78a4db935b8d4b58cae643def77b050488d5d7191cf845af114048` |
| 19维迁移params | `1f189efe9fb64f43406bce409b825870655f8b83765c5ee77d3e208e2cbc2418` |

source与依赖固定在FIORA commit `e19ef82c9a6cb9dbac92bce23e914008f1aeb44e`及D盘独立target。这里的hash是当前正式graph/训练源；metadata初始源、Arrow抽谱源和资源修复前失败尝试应保留各自实际版本，不能用尾部读取当前文件的SHA冒充全阶段实际执行源码。数据代理已单独追踪这项抽谱source receipt边界，当前graph源固定不受影响。

## 数据分组与输入边界

metadata-only选样先于fragment匹配和loss。500个不同官方身份按固定hash分成400train/100development，一身份一谱，CE实际20–60eV，均明确timsTOF/[M+H]+/单有限CE。旧验证的冻结raw家族、官方身份及锁定身份清单用于排除；没有抽取锁定查询或真值。MSnLib v7预训练曝光未知，不能称独立无污染泛化验证。

所有500结构仍保留原分母，不按标签覆盖补抽。当前index报告498个cache_ready（400train、98development）及2个无真实fragment监督的development拒绝；训练器要求保留原400/100 selection，并把未可评估development谱保留为missing-as-zero谱cos分母100、KL全分母缺失时显式null。

model Data包含native结构、CE、分子量、四离子槽、HCD/timsTOF/OTHER、元素组成；标签单独在Data的compiled_probsALL字段，nativeforward只按显式feature键读取。group_id仅为native分组元数据，model不读取它。官方identity、split、source_row、实测峰及compiled_mz不作为model输入；评价所需实测谱与m/z映射在独立npz sidecar，训练目标来自实际峰匹配，而不是由标签把正确结构升首。

准备器由Arrow抽谱和Torch构图分两个进程，避免重叠RAM。最初1GiB保护在任何标签产出前失败；实际graph运行声明root批准1.5GiB上限，不改变选样与label契约。

## 真实监督与损失

- `Metabolite.fragment_MOL(depth=1)`与`match_fragments_to_peaks`为固定native路径，默认五正离子fragment modes依次为`[M+H]+,[M]+,[M-H]+,[M-2H]+,[M-3H]+`。
- 每条directed edge有左5/右5channel，反向edge在native label矩阵中交换左右，末尾两项为重复precursor计数。目标是`compiled_probsALL=2*counts/sum(counts)`；训练保留native重复precursor两项。
- 薄训练器GraphwiseKL实现与原`Losses.py:GraphwiseKLLoss`逐行同义：eps1e-8，目标和预测每图归一，KL(target||prediction)，对图平均。运行前提取原类核验数值与梯度；没有引入不同方向、全batch归一或channel MSE。
- 固定seed20261115、batch4、FP32、Adam2e-5，while精确计500次`optimizer.step()`，非500次forward。无学习率/阈值扫描、无development选checkpoint；step500state先保存，再读final development指标。
- `validate_output`绑定每图segment_ptr与label分段，`CacheDataset`要求非负有限目标及`target[:-2].sum()>0`。>=1真实fragment匹配是预先固定门槛，不筛低覆盖率；未知结构/断片失败保留状态和原分母。

存在一个需保留的细节：准备器接受零强度峰，native `num_non_precursor_matches`计数量可包含零强度。理论上“匹配数>=1”仍可有纯precursor目标；训练器已对非prec目标和增加failfast。本次独立逐个读取498个ready图，确认全部`compiled_probsALL[:-2].sum()>0`、零例纯precursor目标；没有仅凭匹配数宣称真实fragment监督。

## compiled mass map与native物理谱的一致性

独立纯结构哨兵试验使用五个connected结构（链、芳环、天然产物、对称重复片段、带电），给每个compiled channel唯一正强度。将sidecar与原`SimulationFramework.simulate_spectrum`结果按精确m/z累计后，**每个m/z强度差均为0**。这实际覆盖左5/右5模式顺序、只输出正向edge、ring片段跳过、对称fragment重复以及末两个precursor只输出最后一项。[独立数值契约](fiora_channel_contract_review.json)。没有加载模型或真实标签。

native只给正向edge物理输出，反向channel仍参与native训练loss；这两者不同是固定原实现，不可把全部directed channels重复加进物理谱。预测最小强度>.001是在合并重复片段前执行，与native一致。native按m/z+annotation合并，后续cos按m/z bin再次累计，所以sidecar不保存annotation仍能得到相同质量bin强度。

另一个disconnected结构`CCO.CC`在native fragmentation就抛`Unidentified edge in fragment`，尚未进入映射。首轮review源码与失败log保留为`review_fiora_channel_contract.py`和`fiora_channel_contract_review.log`；后续r2固定connected验证集。此为native输入限制，实际准备器按graph_error记录且不补抽，不是本次mass map失配。

## 审查中修正的评价问题

最初trainer去precursor用固定±.01Da，而label coverage sidecar用`max(.01,100ppm*理论precursor)`。高m/z时会把native label认作precursor的实测峰留在所谓wo_prec物理cos。已反馈并在首次训练前修正：直接复用sidecar `query_nonprecursor_mask`，预测端显式丢末两个precursor channel，两边统一同一去prec窗口。谱峰匹配容差仍固定.01Da，与去prec窗口分开声明；没有为涨分扫容差。

目前物理cos调用原`fiora.MS.spectral_scores.spectral_cosine`、sqrt强度变换。它会把相邻差<.01的质量连成链再累计，极端情况下链两端可相隔>.01；这由原源码TODO明确披露。因此该指标是**native兼容的质量bin谱cos**，不是严格一对一容差匹配。重复m/z强度会正确累计，但不能据此声称无峰匹配歧义。native的precursor-bin0删除bug通过先剔峰避免，不调用remove_mz参数。

## 绑定与放行限制

训练器已加强：完整index状态、selection精确SHA/400–100官方身份集合、label_contract_SHA/非零fragment门槛/无低覆盖阈值、每条index原(source_row,spectrum_id,identity,split)绑定、各graph/npz SHA、迁移params/state SHA/67key/参数数、prepare及GNN/MOL/SimulationFramework源码全部在训练前固定并于训练后复验。准备器/训练器未被本审查修改。

最后放行只针对固定小试的可执行性和监督含义。coverage高或loss下降都不证明候选排名变好，且FIORA不新增库外结构。后续要用固定候选集做真正独立的同式候选区分/错误互补评价，不能直接把这次训练指标当Kaggle增益。本审查没有打开任何development模型成绩文件。

全缓存监督独审已完成：[fiora_graph_target_contract_review.json](fiora_graph_target_contract_review.json)，状态`passed_independent_native_supervision_contract`，498/498图（400train、98development），`zero_nonprecursor_targets=0`、`issues=[]`。实际检查全部pt/npz SHA、mass-target尺寸、native正向/ring/末prec mask、query去prec窗口、19维仪器编码与元数据字段边界；另提取当前trainer函数和原native类，独立计算KL值与梯度严格相等。该过程没有模型加载、训练或development模型成绩读取。
