# Ozertuu V18：资产与复现入口审计

检查日期：2026-11-11。只读检查公开源码、公开文件元数据及 D 盘现有资产；未运行公开 Notebook、未下载大模型、未进行 Kaggle 写入。

当前公开链接：[CASMI26 Dual-Neural & Physical Isomer](https://www.kaggle.com/code/ozertuu/casmi26-dual-neural-physical-isomer)。本轮拉取为 **V18**，源码 813,013 字节，SHA256 `54ad16b546964a1044f07aa5229cd7ee81145882d73a83fda061923e9254adcd`。本地源码为 `ozertuu_refresh_20261111T030240Z/0/source.ipynb`。早先旧 slug 下的 V13 不再作为最新比较依据。

## 是否需要再下载

**值得保留源码并准备复现，但当前不需要重新下载整套大资产。** 我们已具备其公开可解析的具名基础资产，以及公开 V80 权重。公开 metadata 中仍有两个空的 dataset 来源；目前不能据此宣称作者完整挂载和第三模型已被还原。

| 公开来源 | D 盘已有版本 | 结论 |
| --- | --- | --- |
| sanpier/casmi-spectrum-model-v1 | v1 | 原公共 scorer，可复用 |
| popwenman/casmi26-scorer-train-v80 | output v1 | 主要新 checkpoint 已在 D，不需重新训练或下载 |
| dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets | v9 | 我们 0.488 正式输入之一 |
| dmitriigluzdov/casmi26-fold-safe-fpnet | v5 | 已有 |
| dmitriigluzdov/casmi26-natural-product-knowledge-table | v10 | 已有 |
| dmitriigluzdov/casmi26-natural-product-panel-benchmark | v10 | 已有 |
| dmitriigluzdov/casmi26-pubchem-popularity-prior | v13，另有旧 v4 | 生产 v13 可用，复现时必须显式定版 |
| qwertykeypadapple/casmi26-lotus-candidates | v2 | 已有 |
| takumuhata/casmi26-extlib | v2 | 已有，现有 0.488 已用 |
| samartalwar/casmi-2026-spectral-library-massbankharmonized | v1 | 已有，现有 0.488 已用 |
| metric/rdkit-2026-3-3-wheel | v1 | 已有官方身份所需 wheel |
| sanpier/catalogue-experiment-saner | 未下载 | V18 credits 明说本次不读取；公开清单没有 final_model.pt，不必为此方案下载 |

上表说明本地可复用范围；V18 API metadata 给出的是未定版的来源名称，不能把本地版本号自动写成作者当时实际输入版本。

补充公开元数据检查：对 `ozertuu/casmi26-our-scorer-v80-model` 的 SDK `get_dataset`（旧版 `dataset_view` 等价）和文件清单读取均返回 **HTTP 403**，未下载权重；不据此推断不可读原因。`user=ozertuu, search=casmi` 的公开列表仅返回 `ozertuu/frigidwheels-casmi26` v1，37,140,471 字节。记录在 `ozertuu_scorer_public_metadata_audit.json`。这份不可读 scorer 的 checkpoint 内容、与公开 V80 的关系以及是否对应空来源，目前均未确认。

## V80 的实际文件与训练范围

- 新模型：`assets/kaggle/popwenman/casmi26-scorer-train-v80/v1/casmi_spectrum_model_ours_v80/final_model.pt`，**11,872,818 字节**，SHA256 `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`。
- 同一输出的 `kit_staged/final_model.pt` 同样为 11,872,818 字节，SHA256 `44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642`；与我们已有的 Saner v1 权重逐字节一致。它不是第二个独立新模型，而且公开扫描器明确排除 `kit_staged`。
- V80 `config_used.json` 与公共模型的结构和推理相关参数一致：192 width / 192 embedding、3 layers、6 heads、96 peaks、2048 FP、temperature 0.1。训练上配置 80 epochs，实际早停于 56 epochs，最终 full-refit 52 epochs。
- `training_result.json` 明确 final_model 已用包含旧验证身份的全量数据训练；其 diagnostic MRR 不能替代干净留出分数或我们自己的榜分。
- 这些文件已于 11 月 6 日下载，有 `download_receipt.json` 与 SHA 记录，本轮没有重复下载。

## 必须修复的复现入口

V18 的 `_find_extra_bundles` 递归扫描整个 `/kaggle/input` 下的 `final_model.pt`，只按路径排除 `casmi-spectrum-model-v1` 和 `kit_staged`；它不按权重 SHA 去重，也不检查架构。后续虽可给所有找到的模型打分，但三模型融合公式只消费前两个成功 extra。

因此不能直接让它扫描我们整个本地资产根目录。D 盘当前会匹配出：

1. `bgunshui/casmi26-scorer-v2-model/v1/final_model.pt`；
2. `bgunshui/casmi26-scorer-v4-model/v1/final_model.pt`；
3. `popwenman/.../casmi_spectrum_model_ours_v80/final_model.pt`。

按其路径顺序，V80 可能被排在融合采用的前两个 extra 之外；v4 与公共模型的架构也不同，复制公共 `model.py/config.json` 后不能直接加载。仅复用我们 0.488 的 Kaggle 挂载清单也会额外引入 v2，改变作者的模型集合。

应将用于对照的 checkpoint 列表、数量、顺序、SHA、配置和预处理全部显式冻结。仅使用现在可解析的具名公开输入时，可确认一个新 V80 extra，对应 **0.5×z(Saner)+0.5×z(V80)**。源码里的 **0.5/0.25/0.25** 分支需要第二个实际成功 extra；两个空来源未解析前不能断言作者实际就是该三模型融合。

## 离线运行与建议

V18 本身是 GPU、禁网 Notebook；沿用相同 E006/公共基座，不需要重新训练模型。其 fast commit 会跳过真实推理并输出 dummy SMILES，这只能检查代码提交入口；必须另跑真实 smoke 或完整诊断，确认指定模型确实参与评分、候选 identity 合法、完整流水线预算可容纳。

建议先做两条互补准备：

1. 保留原 V18 源码快照和 unresolved 来源记录，准备一版基于可访问资产的配方复现，单独标明任何输入定版或模型集合替换；两个空来源与实际作者 checkpoint 未确认前，不称完全等价复现。
2. 在我们精确 0.488 上固定候选和其余阶段，只替换为显式 Saner+V80 集成；将其与公开新质量/加合物过滤分开，避免同时改几层后无法解释来源。

当前结论是“资产基本齐备、模型有实质不同、值得做成对实验”，不是“集成已证实能超过 0.488”。本轮五次正式提交已用完，不重复提交。

证据：`ozertuu_refresh_20261111T030240Z/0/metadata.json`、`source.ipynb`；`saner_public_file_inventory.json`；现有 V80 `output_inventory.json`、`download_receipt.json`、`config_used.json`、`training_result.json`；我们 0.488 的 `kernel-metadata.json`。
