# FIORA tims500：接入现 .488 的离线工程可行性

2026-11-16。**本文件是只读工程建议，未实施接入、未部署、未上传。** 未读取正在运行的全100题预测或 truth 文件；不预判其结果。只有主检验原8题以外92题确认排序信号后，才值得进入这里描述的冠军候选对照；若为负向，本文件仅供备查。主92阳性也不能替代对完整 .488 的增量验证。

## 1. 现有生产接口能提供真实查询，但旧 final25 不是冠军 final25

当前正式冠军为 `58156482 / Public .488`，固定入口 [notebook.ipynb](../../submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb)，SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。[recipe](../../submission/optimization_20261109/mass_guarded_extlib/recipe.json) 保留原管线、双神经组合、MASS/先验、旧训练 head 和最后 AB 实测库覆盖。

本次直接解码了该 notebook cell11 的固定源码，没有执行其中代码：嵌入的 inner notebook SHA 为 `d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88`，嵌入 `export_evidence.py` SHA 为 `d4ec36a9f6216d2607fff4f481bc465dbc8fbc616ec4b24f12932e4c5e546e19`。inner cell39 原样读取官方 `test.parquet` 全列，增加观测中性质量 `nm`；export 最后把 `scope['te']` 原样保存为 `effective_query_spectra.parquet`。因此真实前体、峰、机型、离子和原 CE 没有被早期 ranker 的“多CE取均值”临时变量覆盖。

FIORA 的查询投影可严格限制为：

| 用途 | 允许读取的生产列 | 固定处理边界 |
| --- | --- | --- |
| 查询绑定 | `molecule_id, spectrum_id` | 从最终 CSV 的 ID 顺序绑定，先封存选择；不按预测效果选谱 |
| 真实条件 | `instrument_type, adduct, collision_energy_ev` | 仅真实 `timsTOF / [M+H]+`；CE 为有限 scalar 或长度1数组；多CE数组不能取均值假装单CE |
| 真实观测 | `precursor_mz, ms2_mzs, ms2_normalized_intensities` | 观测前体用于两边统一去前体；不由候选理论质量或 truth 替换 |

本次只读已有 `runs/generation_production_20261113_r2/kaggle/working/effective_query_spectra.parquet` 的 schema 和上述前两组元数据：该旧两分子产物有20条谱，其中4条满足单个有限CE、timsTOF、H+条件。它是已有 expanded-generation 中间件，**不是精确冠军覆盖率，也不是本次100题证据**。只查看 schema 已能发现旧产物还保留 `normalized_smiles, inchikey, molecular_formula, official_identity` 等标签列；未来 adapter 必须按白名单 `columns=` 投影到新的无标签查询文件，不能整体传给 scorer。该旧产物没有被修改。

`frozen_candidate_evidence.parquet` 和 `submission_baseline0465.csv` 出自 inner 最终规则之后，仍早于 outer 双神经、MASS、head 和 AB。它们不能代替完整 .488 的最终25。最小新对照必须先走完原冠军所有阶段，封存 AB 后真正的 `submission.csv`，再以其中实际 raw SMILES、原位次、官方身份及候选自身分子式构造 FIORA evidence。AB 可能补入此前没有的结构，因此要能给这些最终候选构图，不能只沿用旧 pool PID。

来源：[生产阶段图](../champion_error_decomposition_20261115/source_stage_map.md)，以及本次直接解码固定 notebook 的 export/inner cell39。

## 2. 先检验早位纠错能力；保护机制分别对照

旧训练 head 的 prefix7 是那条历史配方的实现约束，不是用户给 FIORA 的永久限制。尾部旧策略多次停在 .488；若把新算法预先锁在 rank8–25，会丢掉“能否修正 top1 / Top5”这个关键检验。

未来离线对照应先固定完整冠军相同 final25 的候选多重集、查询观测和模型。FIORA 按原生产候选自己的分子式分组，**同式组在全部原 slots 中重排，包含 rank1–7**；不读真分子式，不插真候选，不改变各位次的分子式，不新增召回，不扫描融合系数。相同分数按原位次稳定打破平局。先分别报告 top1/Top5 正确项修复、原正确项损害、MRR@25 和真实改动位置，再讨论接入。

至少区分以下机制，不能把它们混称为一个 FIORA 收益：

1. **原冠军完整输出**：固定基准；原各阶段及 AB 的实际审计留存。
2. **FIORA 同式全 slots 重排能力诊断**：测模型是否在同一最终25中识别早位错误，rank1 可以移动。该诊断本身不是准入配方。
3. **已有高置信库保护对照**：在相同 FIORA 分数上，单独评价原生产 `library_max >= .90` 整题保护的效果。这个值来自本次同输入、同隔离条件的原生产证据，不能设为0、复用别的旧面板或用AB余弦替换。保护造成的机会损失和减少的损害需同时报告。

AB 保护适用性另列：原 AB 用 `TAU=.80, K_PEAKS=4, LIB_TAU=.90`，前体窗为10ppm+.002Da，碎片窗 .015Da；它读取原 pipeline `library_max` 来跳过已有高置信库查询。**AB 自己的命中/升首不等于 pipeline library_max>=.90。** 应按原 `external_overlay_runtime.json` 的 `actual_matches/details`，分层报告已接受 AB 升首题、命中但未改首题、未命中题。是否整题保护 accepted-AB promotion，必须作为单独预声明机制对照；本文件不默认加入该保护，也不默认撤掉已有保护。不能根据结果再挑一个阈值。

公式/身份计算沿用官方 RDKit 2026.03.3；旧 reorder 中的候选多重集、官方身份多重集、公式 slot、ID顺序、CSV roundtrip 检查均可复用思想，但不能原样继承其 prefix7。未知机型、缺CE、多CE、无合格谱等查询保持原冠军，并明确记为不支持。构图/forward 缺失不能删候选或补抽；未来预声明的查询/同式组回退要保证部分评分不会悄悄变成重排优势。全局源码/资产绑定失效仍应显式失败。

来源：[原 late reorder](../../scripts/guarded_head_tail_20261109.py)、[原 AB helper](../../scripts/external_library_overlay_20261109.py)、冠军 cell32 内嵌 `alex_v12_external_function.py`（SHA 在 recipe 中固定）、[隔离/库上下文边界](../champion_error_decomposition_20261115/panel_contract_review.md)。

## 3. 最小新增离线资产：真实 tims500，不是改名的 HCD

| 资产 | 当前本地固定位置 / 内容 | 离线接入要求 |
| --- | --- | --- |
| 唯一部署候选权重 | `runs/fiora_tims_model_20261115/pilot500/last_checkpoint.pt`，161,470,333 B，SHA `9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252` | 取 `model_state_dict`；检查 step500、strict67 keys、13,448,861参数；不拿迁移未训 step0 或原18维OS HCD state替代 |
| 配套参数 | `fiora_OS_tims_migrated_params.json`，1,776 B，SHA `1f189efe9fb64f43406bce409b825870655f8b83765c5ee77d3e208e2cbc2418` | static19维，instrument词表 `HCD,timsTOF`；RT static18维按原生构图约定保留，不启用RT任务 |
| 固定源码 | `assets/research/fiora_os_20261115/source_checkout`，commit `e19ef82c9a6cb9dbac92bce23e914008f1aeb44e`，当前55个源码/配置/说明文本合计277,050 B | 携带MIT许可、所用encoder/graph/model/谱cos/质量映射源码及逐文件SHA；生产 adapter 应独立冻结质量映射函数，不隐式依赖本地训练脚本路径 |
| 独立依赖 | `assets/research/fiora_os_20261115/dependencies-linux`，当前927文件、18,666,843 B | 按目标解释器和既有torch版本核实；见下一节。不要覆盖原冠军环境 |
| 新 adapter / 收据 | 尚未实现 | 仅读取封存无标签query/candidate、模型/源码；记录分数、coverage、错误和最终CSV消费关系；truth由另一评价进程读取 |

完整 checkpoint 带 optimizer；将来可另导出仅 tensor 的 step500 state，约53.8MB量级，保留父 checkpoint SHA 和逐 tensor 一致性收据，形成新的导出SHA。本次没有导出。部署推理只需 step500；step0 可继续作为研究对照，不必常驻生产GPU。

分数也要保持已测定义：原生depth1构图和前向质量映射，仅保留forward directed-edge片段，预测强度严格大于 .001，去掉两个原生前体通道；查询谱和预测谱共同按实际观测前体 `max(.01Da,100ppm)` 去前体。使用native sqrt谱cos、.01Da匹配和相邻bin链式合并，不能换成一对一匹配或把 fragment-channel cosine 当成该谱分数。[已测 scorer](../../scripts/score_fiora_candidate_pilot_20261115.py) 的这些固定规则应进入独立生产payload和收据。

模型来自真实 timsTOF 的400结构全参数500次更新，开发仍是原100；MSnLib v7预训练结构曝光未知。现有训练范围是单CE20–60eV、[M+H]+、小结构（原500结构<=32 heavy atoms / <=74 directed edges），不能由两类 instrument词表推断其他离子/机型/多CE及大天然产物已验证。未来 query准入和候选规模边界应先固定，不由 truth 或排名损益挑选。对HCD/Orbitrap/QTOF等条件不自动重命名为timsTOF。

来源：[500步实际结果与边界](../new_paradigm_20261115/TIMSTOF_500_RESULTS.md)、[8题实际模型加载收据](../../runs/fiora_candidate_pilot_20261115/inference/model_load_verification.json)、[迁移参数](../../runs/fiora_tims_model_20261115/fiora_OS_tims_migrated_params.json)。

## 4. PyG 自身可离线携带，但整个本地 target 不能直接宣布可移植

本地 PyG **2.6.1** 的 `WHEEL` 明确为 `Root-Is-Purelib: true / py3-none-any`。模型实际使用 `RGCNConv(aggr='mean', num_relations=4)` 和普通 tensor `edge_index`；所固定 PyG源码在没有 `pyg_lib`/`torch_scatter`/`torch_sparse` 时有原生torch分支，mean/sum用 `scatter_add_`。已有本地真实 forward 和785候选遍历没有安装这些PyTorch编译扩展，证明“必须另编scatter/sparse”不是当前模型的先决条件。

但本地 target 的14个发行包不全是纯Python：`regex, xxhash, aiohttp, frozenlist, multidict, propcache, yarl` 带 **cp312 Linux x86_64** wheel/tag或 `.so`，共10个 `.so`。它们与PyG的纯Python标签不能混为一谈。当前验证环境为torch2.9.1+cu126；本次没有核验实际Kaggle镜像的Python/torch/CUDA版本，也没有在Kaggle离线启动过FIORA。因此结论是：**离线打包在源码层面可行；Kaggle实际兼容尚待验证。**

最小后续工程是把PyG2.6.1、dill、treelib、six等必需模块置于独立只读payload，通过新子进程的路径接入，复用原冠军已经固定的torch/RDKit及常规科学计算库。对递归import实际需要、又不在目标环境中的含扩展包，使用与目标Python/平台匹配的离线wheel；不能把这份cp312 target直接当通用包上传。先跑目标容器的无网络 import、strict load、真实候选构图到谱分数，再测试全生产初始化到最终CSV。不能只凭pip安装成功、`finite forward`或fast_static声称部署通过，也不能在notebook中在线git/pip临时补依赖。

来源：[现有依赖清单](../new_paradigm_20261115/fiora_dependency_receipt.json)、本地 `torch_geometric-2.6.1.dist-info/{WHEEL,METADATA}`、`torch_geometric/nn/conv/rgcn_conv.py:242`、`torch_geometric/utils/_scatter.py:72`、[实际 canary](../new_paradigm_20261115/fiora_canary_attempt2.json)。

## 5. 当前能支持的预算估计，以及尚未获得的准入证据

只使用已经完成的785候选测试性能，不读取本轮100题进度或成绩。该测试为RTX4060 Laptop、batch1、两个checkpoint，各候选用同一图、同一真实CE/观测峰：

| 已测项目 | 785候选累计 |
| --- | ---: |
| 全进程计时口径（含加载、两模型和逐行IO） | 158.45秒 |
| 真实构图 | 10.15秒，中位 .01222秒/候选 |
| step500预测+谱分数 | 26.99秒，中位 .03008秒/候选 |
| 两模型子进程host RSS峰 | 1326.30MiB |
| 两模型GPU分配峰 | 125.99MiB |
| 显式图/推理错误 | 0/785 |

来源：[8题完整 inference verification](../../runs/fiora_candidate_pilot_20261115/inference/verification.json)。500步训练的单步吞吐、显存不能替代候选推理预算。

仅作同设备/类似小图的算术估计：构图加step500约 `(10.14665+26.98585)/785 = .04730秒/候选-查询条件对`，所以 `T ≈ 初始化与IO + .04730 × N_pairs`；这不是实测单模型端到端时间或上界。一个有效谱配全部25候选最多25对/查询；只给实际存在竞争的同式组评分可减少对数，rank1仍可参与。重复结构能缓存与CE无关的图，预测需按真实条件分别绑定；多个谱会增加对数，不能把多谱免费视为一次单CE预测。

以10,000对代入仅得到约473秒的局部计算量，不能承诺整个hidden运行时。大结构构图/子图片段、不同Kaggle GPU、冷启动、父进程已驻留的模型/特征和逐行IO均未被此公式保证。未来应隔离scorer子进程、避免与原冠军模型同时竞争GPU/host峰值，保留实际walltime/RSS/CUDA峰；不要用125.99MiB推断整个冠军新增步骤只需该内存。生产预算需先固定候选/谱准入和失败回退，并用完整初始化到AB后final25再到新CSV的真实路径测量。

进入正式候选前仍缺：完整 .488 同final25下的top1/Top5/MRR配对增量；原库保护和AB机制的独立归因；非支持条件覆盖率及大图错误/时延；Kaggle目标环境无网络依赖与权重严格加载；完整原生产初始化到最终CSV及消费分数审计。当前未发生新提交，也没有新Public/Private分数。
