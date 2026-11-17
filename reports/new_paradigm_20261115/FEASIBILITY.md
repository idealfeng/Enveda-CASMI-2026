# 新能力路线可行性核查（2026-11-15）

结论：先做 **FIORA-OS v1.0.0 的独立前向小试**；将 **DiffMS 的直接结构生成**作为第二条待准入路线。两者都尚无本项目验证增益或 Kaggle 新分。现冠军已经使用 ICEBERG 和 GLACIER 正向预测，因此 FIORA 是独立权重、训练域与架构的补充，不能包装为首次加入正向预测，也不能解决固定候选池中不存在真结构的问题。

竞赛的[官方外部资源规则](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/rules)要求公开可合理取得且遵守主持人的具体禁止；[运行要求](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/overview)为禁网、最长 9 小时。主持人的训练来源澄清见[讨论 749217](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/749217)。因此将代码许可、具体权重训练语料、离线包和时间预算分别核查，不能仅由 MIT 代码推导所有同名权重可用。

## 1. FIORA-OS：现在能做的低成本独立模型

| 项目 | 核实结果 |
| --- | --- |
| 官方代码 | [BAMeScience/fiora](https://github.com/BAMeScience/fiora)，本次固定 `e19ef82c9a6cb9dbac92bce23e914008f1aeb44e`（source tag v1.1.0） |
| 选用权重 | **仅 FIORA_OS_v1.0.0_state.pt**；[官方权重目录](https://github.com/BAMeScience/fiora/tree/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/resources/models)，网页约 51.3 MB；本地精确字节及 SHA 见 acquisition receipt |
| 实际下载入口 | [固定 commit 的 state_dict](https://raw.githubusercontent.com/BAMeScience/fiora/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/resources/models/fiora_OS_v1.0.0_state.pt)、[对应 params](https://raw.githubusercontent.com/BAMeScience/fiora/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/fiora/resources/models/fiora_OS_v1.0.0_params.json) |
| 许可与来源 | repo MIT；[论文](https://www.nature.com/articles/s41467-025-57422-4)明确区分标准 FIORA 与开放的 FIORA-OS；OS 采用 MSnLib，当前公开 params 明确 `training_library: MSnLib v7`。源码许可不能替代训练来源核查，本次保留 LICENSE 与精确模型 params |
| 必须排除的版本 | 标准论文模型训练使用 NIST'17 / MS-DIAL，**不下载、不接入**；不能因 FIORA 项目开源而混用标准模型 |
| 输入 | SMILES、碰撞能、precursor type、instrument；官方 CSV 列 `Name,SMILES,Precursor_type,CE,Instrument_type` |
| 模型条件 | params 中只有 **HCD** 仪器；离子支持 `[M+H]+,[M-H]-,[M]+,[M]-`，无 Na 通道。不能把 timsTOF 直接改名为 HCD 然后声称域匹配 |
| 模型差异 | RGCNConv、10 层、hidden 300、分子图键断裂输出；MSnLib 训练，与现有 ICEBERG/GLACIER 不同。独立 SHA 只能证明不是同一文件，互补程度仍需固定面板实测 |
| 小试 | 两个不同公开 SMILES，使用原生 HCD 条件，显式加载 OS state+params，检查严格 load、有限/非恒定谱、有效碎片和实际时间，不使用测试标签或 hidden |

这里的“新信息”是另一种结构→碎片归纳偏置和训练信息。只有同一批冻结候选上，与 ICEBERG/GLACIER 的错误相关性以及原冠军增量通过后，才考虑正式提交。两条谱都有限或不同，只算组件前向成功，不能称排序改善。

官方 README 说示例一般为秒级、安装通常少于十分钟，但**并非本机测速**。[官方 README](https://github.com/BAMeScience/fiora/blob/e19ef82c9a6cb9dbac92bce23e914008f1aeb44e/README.md)；本机性能以 canary 回执为准。预训练推理优先，不以 500 步重训当作第一步。若需要适配 timsTOF，再先计时 500 步，未测之前不承诺训练时长。

## 2. DiffMS：真正脱离固定候选池，但暂不大下载

| 项目 | 核实结果 |
| --- | --- |
| 官方代码/论文 | [coleygroup/DiffMS](https://github.com/coleygroup/DiffMS)、[论文](https://arxiv.org/abs/2502.09571)；代码 MIT |
| 当前正式模型 | [官方 Zenodo record 23542112](https://zenodo.org/records/23542112)，v3，2026-10-21，record 声明 MIT；`diffms_checkpoints.tar.gz` **795,677,476 B**，MD5 `0e3648e5932b7a615185cb5cee42666f`；元数据保存在 `diffms_record.json`，本次不下载权重 |
| 配套数据 | 同 record `msg_preprocessed.tar.gz` **778,700,233 B**；并非做两条推理必需先下全部训练数据 |
| 实际创新 | 质谱/分子式条件 → 离散图扩散 → 新结构，不是现有“母体+局部反应模板”的同一生成器，也不限定候选数据库 |
| 输入约束 | **需要重原子组成/分子式条件**；CASMI 只能使用不依赖真值的分子式假设，不能传入标签分子式。负离子/Na 以及超训练大小的泛化能力没有完成核查 |
| 当前阻碍 | 依赖 MIST encoder；当前公开 README 所指 encoder release 与本项目已发现输入近恒定的 MIST 系列关联。不能据此断言 DiffMS 全部坏，也不能未核查就接入；需要它自己完整 encoder 的严格状态匹配与原生变动性 canary |
| 工程成本 | README 环境 torch 2.3.1/CUDA11.8/Python3.9，与现有 torch 2.9 环境不同；必须 D 盘隔离。现脚本仅支持 msg/canopus 数据布局，CASMI 需薄适配，不可冒用原生数据名掩盖输入差异 |
| 最小门槛 | 先两条无标签查询、每条少量生成（例如 ≤16），统计有效/唯一/分子式一致率和耗时；检查 `strict=False` 过滤是否遗漏关键权重。官方默认 100 samples 不直接用于首次 canary |

DiffMS 的本机推理/500 步训练时间目前**未知**；论文指标不能替代当前权重和 CASMI 条件的可运行性。只有确认来源、输入条件与 encoder 有效，才值得下约 0.8 GB 预训练包。若重训，500 步只做速度与显存测试，不挑权重/指标。

## 未选路线

- **SpecTUS**：官方 [hejjack/SpecTUS](https://github.com/hejjack/SpecTUS)面向 GC-EI；最终 NIST20 微调权重不公开，合成预训练来自 NEIMS/RASSP。ESI-MS/MS 输入域不合，NIST 衍生来源也不满足本项目准入要求。
- **RASSP / 标准 FIORA / NIST 来源 CFM 版本**：不因可下载或开源而绕过来源限制。
- **MSNovelist**：还需 formula 和 CSI:FingerID 等外部 fingerprint 路径，离线依赖、服务可用性与特定权重训练来源尚未满足本轮条件，不作为最可落地前两项。

## 本次产物与状态

- 主来源缓存与固定摘要：本目录 `primary_source_receipt.json`、论文/README/config 缓存。
- FIORA 源码和唯一 OS v1 state：`assets/research/fiora_os_20261115/`；下载回执 `acquisition_receipt.json`，逐文件 SHA256 与 git blob 校验。
- 依赖发现：WSL `.venv-linux` 已有 torch/RDKit，尚无 torch-geometric / torch-scatter / torch-sparse；仅允许在 D 盘新 target 增加缺失依赖，不改现有环境版本。
- 前向成功回执：`fiora_canary_attempt2.json`。CPU、strict 67/67 state keys、13,447,861 参数；两种相同分子式 C9H8O4 位置异构体，各输出 11 峰，raw 输出同形状且最大概率差 0.125625，谱不同。导入 100.72 秒、load 1.76 秒、图准备 1.14 秒、两次前向+峰整理 0.594/0.0136 秒，总 105.4 秒。这不是全测试集吞吐或排序收益。
- **下载成功、组件前向、固定面板增量、完整管线、真实榜分是不同门槛。**
- 首次运行在 import 阶段发现 `treelib` 缺失的 `six` 依赖，尚未加载模型：`fiora_canary_attempt1_missing_six.json` 保留失败证据；只补 D target 的 `six==1.17.0`，第二次使用 `fiora_canary_attempt2.json` 独立回执，未覆盖旧证据。
- old48 条件审计：仅读五列 ID/instrument/adduct/CE，240 谱/48 查询，207 谱 CE 已知；`instrument_type` **没有任何 raw HCD 行**，129 timsTOF、66 Orbitrap/orbitrap，其余不同仪器或缺失。不能把 Orbitrap 自动等同 HCD，更不能把 timsTOF 改名 HCD。因此本次没有挑出符合原生条件的实际查询（0 个），未启动候选批量评分或微调。见 `old48_native_condition_audit.json`。
