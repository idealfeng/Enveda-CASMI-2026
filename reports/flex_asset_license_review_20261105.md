# Flex V56 输入许可与署名核对

依据本地已冻结的数据卡、README、ATTRIBUTION、SOURCE-LICENSES和实际V56依赖清单，核对8个附加输入。**本页是来源事实记录，不是法律意见或奖牌/奖金资格判定。** 没有push、submit、模型或数据大下载；本地验证继续。

## 主办原文的核实边界

[Discussion745072](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/745072)没有成功取得原文：Web0行，公开页/comments API/internal只读RPC均404空响应，精确索引检索无结果。详细尝试见 [获取记录](discussion_745072_primary_20261105/REVIEW.md)。无法确认该帖作者/Host身份或“只由官方train派生的NC资产”解释范围；不将模型卡的转述升级为主办授权。

可读的官方Kaggle索引中，[741359](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/741359)将 David Healey 标为Competition Host，说明获奖方案外部资源应与商用/再分发授权相容；[744470](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/744470)中其Host回复针对NIST明确禁止。两处都不是745072的具体例外证明，也不能把参赛者提问当成主办答复。

## 8个附加输入

| 输入/本地固定版本 | V56实际需要 | 卡片与文件声明 | 应保留的署名/具体来源 |
| --- | --- | --- | --- |
| [sanpier/casmi-spectrum-model-v1](https://www.kaggle.com/datasets/sanpier/casmi-spectrum-model-v1) V1 | 是：Saner神经模型 | 卡片Apache-2.0，明确覆盖作者原始checkpoint、脚本、配置和配套产物；同时保留第三方/数据来源条款。`final_model.pt` full-data refit是训练范围说明，不是许可豁免。 | Saner Turhaner；第三方依赖及Enveda训练数据来源。保留模型bundle的README/config/hash和原作者链接。 |
| [dmitriigluzdov/casmi26-fold-safe-fpnet](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-fold-safe-fpnet) V5 | 是：fold0 checkpoint | 卡片Other。README将checkpoint/比赛派生文件指向competition data条款，注明非商用与署名；训练/评估/audit脚本Apache-2.0，复制代码和bit indices保留旧声明。 | Dmitrii Gluzdov训练/审计；Ahmed Berat Özer架构、数据加载与bit选择；Enveda谱数据。 |
| [dmitriigluzdov/casmi26-natural-product-knowledge-table](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-natural-product-knowledge-table) V10 | 是：知识/外部参考等 | 卡片Other，汇编声明按限制较严组件保留非商用/署名。LOTUS 2026-04-13快照CC BY4；NPAtlas明确CC BY-NC4；PubChem贡献数据可有来源特定权利。外部谱按每条记录保留CC0/CC BY等原文，不是整包统一换许可。 | Dmitrii Gluzdov汇编；LOTUS/Rutz等；NPAtlas/van Santen等；NLM/PubChem/Kim等；外部谱原作者/提交者/记录ID。 |
| [dmitriigluzdov/casmi26-natural-product-panel-benchmark](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-natural-product-panel-benchmark) V10 | 是：基线读取panel相关资料 | 卡片Other。标识、质量、答案公式、分数、validation assignments指向competition data条款；added replay helper Apache-2.0；PubChem/LOTUS/NPAtlas注释分别保留来源条款，不因不含原谱就全部变CC0。 | Enveda面板；Ahmed Berat Özer管线/FPNet/ranker；Dmitrii Gluzdov汇编；COCONUT/Sorokina等；NLM、LOTUS、NPAtlas、PubChemLite对应作者。 |
| [dmitriigluzdov/casmi26-pubchem-popularity-prior](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-pubchem-popularity-prior) V13 | 是：tier数组与对齐prior | 卡片Other。PubChem政府生成信息/贡献者权利分别处理；LOTUS快照CC BY4；NPAtlas membership/counts来源CC BY-NC4。附带Ahmed PubChem tier原样复制，ATTRIBUTION不重新许可。 | Dmitrii Gluzdov；Ahmed Berat Özer tier构建；NLM/PubChem；LOTUS/Rutz；NPAtlas/van Santen；原始贡献者。 |
| [dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets) V9 | 是：主骨干、E2、模拟器与候选等 | 卡片集合CC BY-NC-SA4；每个复制组件保留原许可。其SOURCE-LICENSES明确Notebook Apache不覆盖权重/候选/数据；其中既有官方train派生NC，也有外部候选、模拟器与独立代码，不能作为同一种来源处理。 | 下表列出；必须保留ATTRIBUTION.md、SOURCE-LICENSES.md、各子目录notice及源dataset链接/hash。 |
| [ahmedberatozer/casmi26-spectrum-model-long](https://www.kaggle.com/datasets/ahmedberatozer/casmi26-spectrum-model-long) V1 | **否**：仅附加，V56未采用 | 卡片Other；描述competition train的CC BY-NC组件，要求遵循源许可、非商用/署名。未为本次V56下载大模型，不应列为实际加载的模型。 | Ahmed Berat Özer训练；Saner Turhaner架构/特征/代码；Enveda数据。 |
| [sanpier/catalogue-experiment-saner](https://www.kaggle.com/datasets/sanpier/catalogue-experiment-saner) V1 | **否**：仅附加 | 本地card许可Unknown，不能凭同作者另一数据集Apache卡推定相同许可。未运行/下载其payload。 | Saner Turhaner；实际采用前需查该资源自己的条款和来源，当前不归入V56依赖。 |

8个输入的原卡路径、SHA-256、owner、license字段和许可段摘录保存在 `flex_asset_license_inventory_20261105.json`。卡片快照不等于原Notebook历史挂载版本证明；源码硬编码模型pins另行保留。

## Attributed bundle内的混合组件

| 组件 | 本地notice所记许可/来源 | 应署名 |
| --- | --- | --- |
| `casmi26-v4b-models`、`casmi26-v3-models`、`casmi26-v2-pool`、`casmi26-fpnet-full1` | 原卡Other；部分来自比赛train的CC BY-NC组件，COCONUT派生池CC BY4；具体文件/模型notice优先保留 | Ahmed Berat Özer、Enveda、COCONUT/Sorokina等；DreaMS后裔另保留其notice |
| `casmi26-fp-models-v2`、`casmi26-ranker-features`、`chebi-lipidmaps-casmi26`、`coconut-casmi26-candidates` | prvsiyan卡/ATTRIBUTION明确CC BY-NC-SA4，保留原始候选来源条款 | prvsiyan；COCONUT、ChEBI、LIPID MAPS原来源 |
| `casmi26-iceberg`、`casmi26-glacier` | Other，包内ms-pred推断代码MIT，已发布权重另有训练来源；RDKit BSD3、Lightning Apache、einops MIT等各自notice保留 | Coley group/ms-pred、Goldman等；Ahmed Berat Özer runner/shim；各依赖作者 |
| `casmi26-simulated-ranker-rows` | megayak数据卡CC0；本次主要使用模拟ranker行，CC0标签不抹去别的模型来源 | megayak及所引上游 |
| `casmi-chebi-lmsd-structures` | sergiomalv所发布资源CC BY4 | sergiomalv、ChEBI与LIPID MAPS |
| `casmi26-pubchemlite-cc0-candidate-fingerprints` | franciscoangulo发布CC0，源于cosmicbe/PubChemLite | franciscoangulo、cosmicbe、Schymanski等 |
| RDKit wheels、DreaMS相关复制项 | wheel/代码/权重分开读notice；本次没有因整包卡标签将它们重新许可 | metric/eveliaveldrine打包者、RDKit；hengck23、Bushuiev等DreaMS作者 |

外部参考谱：`external_reference_spectra/LICENCES.md`说明按记录保留MassBank原LICENSE/作者/出版物、MoNA作者/submitter及例外、GNPS原贡献者和导入来源。该文件报告保留数据中存在版本未指定的`CC BY`/`CC-BY`字符串，应保留原文，不能擅自补成4.0。实际使用751谱只是来源集合的子集，不能用全包的许可总计替代这751谱的逐条来源清单。

Flex外层代码署名还应保留原Notebook的完整credits链：Flexonafft、busyaprime、Roman Tamrazov（Spectral Parallax）、Saner Turhaner、Roman Rozen、Alex Chilton、文档prior相关作者，以及冻结E006/Ahmed/prvsiyan等祖先。数据表owner不等于全部代码作者。

## 供提交材料整理的事实事项

当前能做的是生成“实际读取文件 → SHA →源dataset/版本 →原notice →用途 →署名”清单，并把**官方train派生**、**NPAtlas等外部NC数据**、**第三方模型训练来源**分开保留。745072原文若以后可读，应记录其具体作者/Host标记、原句、上下文与覆盖范围，再与每类资产对应；当前不作扩大解释，也不要求停止本地验证。
