# FIORA-OS 可执行小试与新能力路线核查

2026-11-15：**FIORA-OS 独立前向通过，尚无 CASMI 排序/榜分收益。** DiffMS 只做来源与可行性核查，没有下载约 0.8 GB 权重。

## 实际完成

- [路线核查](FEASIBILITY.md)：两条优先路线、主来源链接、与现冠军已有 ICEBERG/GLACIER 的区别、原生输入条件和准入限制。
- FIORA 固定源 `e19ef82c9a6cb9dbac92bce23e914008f1aeb44e`（tag v1.1.0）；模型为 **FIORA OS v1.0.0**。来源 config 声明 **MSnLib v7-only**；repo MIT；标准 NIST FIORA 未下载。
- 模型 state_dict **53,814,639 B**，SHA256 `83221e187991f116a8aed1bf272dd656cf31721a177dcbb0239f414c8df31a0e`。61 个源/许可/config/example/单一 state 共 54,105,402 B，全部核对对应 git blob SHA1，另存逐文件 SHA256：[获取回执](../../assets/research/fiora_os_20261115/acquisition_receipt.json)。未下载完整 pickle model 或其他模型版本。
- 依赖仅放 `assets/research/fiora_os_20261115/dependencies-linux/`，现有 venv 与全局环境未改版本。PyG 2.6.1、treelib 1.8.0 等 14 个发行包：[依赖清单](fiora_dependency_receipt.json)。无 scatter/sparse 编译扩展；实际 forward 在现有 torch 2.9.1+cu126 中运行。

## 完整失败链与成功证据

1. git promisor 读取遇到 Windows TLS handshake 失败；只改为固定 commit 的公开 HTTPS raw 获取，未禁用证书检查，每个文件仍核对 git blob 与 SHA256。第一次 `ls-tree -l` 可能触发 blob fetch，随即中断，后续改为无 `-l` 的 tree 列表，只获取白名单文件；没有扩大到其他权重。
2. 首次 Python import 缺 `six`，在模型加载前失败，112.65 秒：[原始失败](fiora_canary.json)、[冻结副本](fiora_canary_attempt1_missing_six.json)。
3. 只向独立 D target 补 `six==1.17.0`，新 revision 使用独立输出/回执：[成功回执](fiora_canary_attempt2.json)。不覆盖旧失败。

第二次是实际 CPU 推理：strict **67/67** keys、无 missing/unexpected、13,447,861 参数；两种同分子式 C9H8O4 位置异构体，原生 HCD / [M-H]- / 35 eV，均输出 11 峰，raw 同形状但最大概率差 **0.125625**，不是输入无关常量。未读任何查询谱、标签、truth 或 hidden。

| 阶段 | 本机时间 |
| --- | --- |
| import | 100.72 秒 |
| strict load | 1.76 秒 |
| 两图准备 | 1.14 秒 |
| 第一次 forward+峰整理 | 0.594 秒 |
| 第二次 forward+峰整理 | 0.0136 秒 |
| 全进程 | 105.4 秒 |

首次 warm-up 与两条短分子的时间不能外推全量候选/大分子吞吐，更不代表完整生产管线通过。该 CPU 进程已退出，未占 GPU。

产物：`runs/fiora_os_canary_20261115/attempt2/input.csv`、两份 `_raw.npy`、`predictions.mgf`。复现脚本：[run_fiora_os_canary_20261115.py](../../scripts/run_fiora_os_canary_20261115.py)；先 source 项目 `scripts/linux_env.sh`，使用 `.venv-linux/bin/python`。所有新 cache/temp 由现有 D 盘环境脚本限定。

## 实际查询条件审计与下一步

仅从冻结 old48 `queries.parquet` 读取 `molecule_id,spectrum_id,instrument_type,adduct,collision_energy_ev` 五列，未读 truth/结构/峰。240 谱、48 查询，207 谱有有限 CE；**raw HCD 行为 0**。129 timsTOF、66 Orbitrap/orbitrap，其他为 TOF/ITFT 等或缺失；Orbitrap 机型不能自动等同确定的 HCD 激活条件。因此按 ID 确定性的“原生 HCD + 支持离子 + 已知 CE”最多两查询选择结果为 **0**：[完整回执](old48_native_condition_audit.json)。没有运行新批量评分、调参或微调。

下一步的最小互补评估需先满足真实输入条件：

1. 从已有可信元数据恢复激活方式，或另取已经固定的原生 HCD 留出查询；不从 truth 推条件，不把 timsTOF/QTOF/Orbitrap 统一改名 HCD。若仍无 2 个合格查询，明确停在组件通过，不能把另一个域的测试包装为 CASMI 增益。
2. 按 molecule_id 确定性选最多 2 个，冻结现冠军候选多重集、候选身份、离子、CE；不新增生成或候选过滤，不挑看起来容易的结构。分开记录模型预训练暴露（MSnLib v7 结构可能已见）。
3. 预先固定原生谱分数定义，先记录 FIORA 与 ICEBERG/GLACIER 分数相关性及候选名次差异；只在预测完成后由独立 evaluator 读标签，报告真候选 margin/排名及原冠军是否失误。不能试多个分数后挑最好者，也不在两题上挑融合权重。
4. 两题只决定是否扩大冻结验证面板；不是生产准入或提交收益。正式部署仍需域内/跨域验证、来源暴露边界、全测试预算与真实从初始化到 CSV 的完整路径。

本轮不修改根 docs、ledger、模型索引或正式提交。新增资产模型登记与索引刷新由根代理统一处理。
