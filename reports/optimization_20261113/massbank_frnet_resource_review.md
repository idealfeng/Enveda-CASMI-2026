# 新公开FRNet资源：只读可行性审查

本次按根代理补充任务审查 `agentili/casmi26-fr-reranker-blend`，先访问公开metadata、文件清单并下载小型源码/配置；后续按明确授权下载3.1MB权重并独立计算SHA。没有导入Torch、没有反序列化模型、没有CPU/GPU推理或主库作业，也没有Kaggle写入。训练来源与具体许可未能确认，当前保留为研发资产，不建议正式提交。

## 取得的资产

官方metadata读取时间2026-11-13 11:52 UTC；当前版本 **v2**（11/11更新），总大小 **3,156,612字节**。

| 文件 | 字节 | 当前状态 |
| --- | ---: | --- |
| fr_model.pt | 3,100,917 | 后续授权已下载，独立SHA匹配公开pin，未加载 |
| model.py | 6,830 | 已存D；SHA与V50冻结pin相同 |
| fragfeat.py | 12,928 | 已存D；SHA与V50冻结pin相同 |
| fr_config.json | 258 | 已存D |
| harmonized_fr_blend.py | 20,196 | 已存D，非完整可直接导入包 |
| domain_class_priors.py | 10,439 | 已存D，独立先验组件，不默认并入新信号 |
| test_domain_class_priors.py | 4,780 | 已存D，未执行 |
| fr_selftest.json | 264 | 已存D；expected_scores=null，不是可复现数值golden test |

全部非权重文件共55,695字节，位于 `assets/kaggle/agentili/casmi26-fr-reranker-blend/v2/`。完整公开读取回执、大小和源文件SHA见 [metadata](massbank_frnet_public_metadata.json)，未持久化signed URL。

公开V50预期权重SHA为 `21f70d461564a1db09ce7e181a138538b8efcef2f05c67050f042c607560ff7e`，下载后独立计算完全一致。下载前 `docs/model_registry.json` 的82个权重条目没有此SHA，也没有agentili/FRNet文件；根代理刷新索引后新文件应登记。这支持实际权重不同，但不支持直接推断排序互补。

## 模型到底是什么信息

源码是候选条件的碎片匹配网络，而不是Saner/v2同系双塔checkpoint，也不是预测完整谱强度的生成模型：

- 先对候选重原子图枚举断1/2根键得到的连通片段，按adduct允许carrier和H偏移−2至+3与观测峰匹配；确定性匹配标注写入原子/键/峰特征。
- 默认FRNet `d=128, layers=5, peak_layers=2`：GINE图网络处理候选图，Transformer处理带片段解释标记的峰序列，最后拼接图读出、峰读出和全局解释强度特征输出一个logit。
- 重要推理参数：最多48个峰、峰容差.005Da；双断键枚举限制MAX_BONDS_2=110；输入强度先按谱归一，按极性合并多谱，接近/高于precursor的峰剔除；至少3峰门槛。
- `no_frag` is a supported ablation switch. Later inert opcode inspection confirms the actual checkpoint uses no_frag=False, d=128, layers=5, epochs=12 and ep=9. The small fr_config.json epochs=[5] field does not establish actual training history or data provenance.

它可能提供真实不同的“候选图如何解释观测碎片”信息，但与现有MetFrag-lite/RR碎片枚举有概念重叠，并不是完全独立物理证据。应先导出分数/解释特征，验证是否纠正完整冠军错误；不能因架构不同直接假设互补。

## 完整可用性与实际缺口

`harmonized_fr_blend.py`不能直接作为完整包导入：它依赖本数据集未提供的 `harmonized_apex_postprocessor`，且默认权重路径为 `../work_fr/model_full.pt`，与清单的 `fr_model.pt`不一致。该问题不代表FRNet本体不可用；公开V50 cell22选择了自带加载/批处理wrapper，直接加载flat目录的model.py、fragfeat.py、fr_model.pt，避免了这个未打包依赖。

FRNet主网络只依赖PyTorch，不需要torch_geometric；片段枚举若没有Numba，公开V50直接停用（计算预算原因），因此离线环境也须确认RDKit/Numba路径。数据集自测仅检查finite，不会证明完整推理或收益。

## 后续最小调用入口（本次未执行）

公开V50 `cells/22.py` 的 `_fr_load()` 先固定三文件SHA、导入flat包并用checkpoint真实args构造模型；`_fr_scores(model, spectra, smiles)`（第71行）先调用 `ff.merge_spectra`、`ff.query_table`，再逐候选 `ff.featurize`，通过 `_fr_batch` 组成模型输入。输入 `spectra` 应沿用该源码 `_fr_spectra` 的字段约定，不能把已被其他模型处理的峰表直接替换进去。它只返回每个候选原始logit/无法处理时NaN，无须执行原tail blend。

若后续确认许可、训练来源并释放内存，首轮可固定2个真实query、每个25个缓存候选，只导出50个原始分数和特征有效性，不读标签选权重。实际CPU耗时与峰值内存尚未测得；公开源码的1500秒是整段保护上限，不是对50候选的测速。当前不启动该流程。

## 许可与训练来源

官方metadata：`license_name = Other (specified in description)`，但API返回的description为空，文件清单也没有LICENSE。**因此具体许可条款目前未确认，不能把公开可下载等同于已核实可用于比赛。** 本次仅记实际读取状态，不推断403/权限问题，也没有给任何数据重新贴许可证。

训练数据来源、身份隔离、验证方式和预训练曝光均无法仅凭这套推理资产确定。若后续真采用，需要从原训练Notebook/作者资料确认，并显式记录；这与是否能运行是两件事。

补充的只读来源调查：[回执](massbank_frnet_license_investigation.json)。SDK完整JSON字段中只有licenseName/description等，并无另一个terms正文；license仍Other、description仍空。普通公开页面请求未成功取得数据卡，web工具也无法打开；按作者筛选的公开CASMI Notebook列表为空，没有找到训练入口。这些结果只能记为“未取得”，不能推断作者未发布或数据集一定不可用。

为避免加载模型挤占根代理当前7.0/7.5GB WSL内存，使用纯标准库zipfile/pickletools静态检查权重的12,166字节metadata opcodes（没有unpickle）。[记录](massbank_frnet_checkpoint_metadata.json) 显示args中 `tag='full'`、`no_frag=False`、`d=128`、`layers=5`、`epochs=12`、`bq=64`、`lr=.0005`，checkpoint `ep=9`。因此小fr_config的epochs=[5]不是实际checkpoint训练步数的可靠证明。metadata没有训练文件列表、split身份、许可正文或明确NIST声明；未看到NIST字符串不等于证明未用NIST。`tag=full`也不能独立证明具体full-refit训练范围。

## 是否立即采用

不立即提交原tail重排配方。公开V50源码自己将FR_ON=False，注释称先前FR_W=1的tail版本使其.487→.486；这是作者源码自述，尚未核验我们的真实分数。数据集blend文件内又有其它自报分数和不同W值，不能取最高自述当稳定效果。

更合理的后续用途是为完整冠军的候选级证据表提供FRNet原始logit/片段解释度，先确认覆盖、推理时间、与现有GL/ICE/物理分数的实际错误互补，再决定是否训练受限融合。当前没有模型执行或成对效果结果，不能称已取得新预测能力，更不占今天提交名额。

资料入口：[官方数据集](https://www.kaggle.com/datasets/agentili/casmi26-fr-reranker-blend)；原公开V50源码快照 `reports/optimization_20261113/public_short/prvsiyan__analog-propagation-casmi-2026-baseline/cells/22.py`。
