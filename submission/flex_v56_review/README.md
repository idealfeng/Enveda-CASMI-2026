# Flex V56 离线提交审查草稿

这里是本地准备产物，未创建或更新 Kaggle Notebook，未提交比赛。

- `notebook.ipynb`：原始 V56 的逐字节副本，保留原作者署名及运行逻辑；不混入本地验证排除逻辑。
- `kernel-metadata.template.json`：私有、GPU、断网模式的模板，含明确用户名占位符；没有可自动执行的发布命令。
- `kernel-metadata.json`：用户提供用户名后已在本地生成，id为 `stormseye/casmi26-flex-v56-baseline`，title与slug对齐；尚未鉴权或调用云端服务。
- `local_asset_manifest.json`：447 个必要文件存在且记录尺寸匹配，447 项均有来源 SHA；其中 444 项来自目标旁回执，3 个 PubChem 数组通过源回执、已有 alias pin、真实同文件 hardlink 和尺寸核验继承 SHA。本次未重新读取大数组计算内容哈希。云端仅附数据集 slug 不保证得到相同历史版本，必须复核源内模型 pin 和文件 manifest。
- `preparation_report.json`：源码校验结果和仍需完成的事项。

原脚本通过实际输入及重跑标志选择可见12分子检查或正式全量运行。新增的 [48分子诊断](../../reports/VALIDATION_FLEX_48_2026-11-05.md) 已完成，使用独立生成的参考隔离适配器且有已知模型训练曝光。它验证了更多运行时ID与候选路径，仍不等于原Notebook正式全量分支、隐藏输入或冷启动预算已验证。

本地已安装 Kaggle 2.2.5 / kagglesdk 0.1.38 的源码确认 `machine_shape`、`docker_image`、GPU及断网布尔字段会传入请求，当前T4名称在SDK文档中。历史Docker digest是否仍为当前账号可用镜像、GPU配额和云端附件版本尚未通过服务验证；模板未指定 `docker_image_pinning_type`，不能声称云环境已固定。CLI读取的正式文件名是 `kernel-metadata.json`，现已为stormseye本地生成；通用 `.template.json` 另保留用户名占位符。详见 [SDK元数据复核](../../reports/submission_metadata_sdk_review_20261105.md)。

资产审查不能仅按数据卡上的 NC 字样做统一结论。有发布者引用主办745072，称仅因官方 train.parquet 产生的非商业限制不妨碍本赛使用；应核验主办原文并区分其他外部数据/权重的独立限制，保留署名和来源。当前草稿不作完整获奖资格保证。

生成或复核本地账号草稿：从项目根运行 `python scripts/prepare_submission_review.py --username stormseye`；不带用户名可复核通用模板。该脚本只读已有源码/资产并写本地审查文件，不调用任何发布或提交 API。
