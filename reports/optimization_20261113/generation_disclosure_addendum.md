# 11/13 generation 生产路径核验：输入声明更正

此次完整执行的是冻结的 `generation_production` Notebook（SHA `a9debc93f59213d3c80a8b3ee0e4808ee930d6ada34c3ee908f1469fa35cfa2c`），经过真实 FROZEN 初始化、原有排序和融合、双神经评分、MASS、guarded head/tail、AB 外库，最终输出两行、各 25 个候选。耗时 2327 秒，约 38 分 47 秒。四项真实运行审计和独立复核均通过。仅证明这两个输入上的实际生产路径可执行，未证明完整隐藏测试资源预算或榜分提升。

原 `runs/generation_production_20261113_r2/verification.json` 的 “unlabelled” 表述错误，原准备声明 `no_truth_loaded=true` 也不成立。本次测试文件取自诊断面板，保留 `normalized_smiles`、`inchikey`、`inchikey14`、`molecular_formula`、`official_identity` 等额外元数据，共 12 个非官方测试字段。这些列还随全量 query frame 被写入 `effective_query_spectra.parquet`。因此本次不能称为无标签测试、清洁验证或结构召回率评估。

独立源码审查覆盖 FROZEN39/41、实际 E2、PubChem runner、神经评分、learned head、guarded tail 和 AB 查询解析：审查未发现它们把查询标签作为预测输入，实际使用的是谱字段和候选结构。这是源码审查结论，没有进行运行时字段访问插桩；保留这一证据边界。

本更正不改动已执行输入、冻结 Notebook 或原 verification 证据。`preparation.json` 和 `input_schema_review.json` 已更正实际来源。后续 prepare 入口已经改为按官方 `test.parquet` 的字段白名单投影；未来完成回执也不再自动写 “unlabelled”。本次选择的两个查询不用于选参或估计收益。

证据：`runs/generation_production_20261113_r2/verification.json`、`input_schema_review.json`，以及同目录下 `reports/optimization_20261113/evidence_generation_review.json` 和 `generation_disclosure_addendum.json`。原 verification 的错误声明以本更正为准，其余执行证据保留。
