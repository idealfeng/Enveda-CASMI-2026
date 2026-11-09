# V43运行来源身份补充核对

本次实际来源是 `prvsiyan/analog-propagation-casmi-2026-baseline` **V43**。原Notebook SHA-256为 `a1da86c791cdbcb553254a12cef8bca8b527b991f40953d9dcb2a9c819d3c852`，与本地wrapper的`SOURCE_SHA256`及V43c外层`validation_run_receipt.json.source.source_sha256`一致；冻结元数据`currentVersionNumber`为43。

`e004_verification.json`里的`source_version=80`、`source_version_id=356740494`、`source_code_sha256=eee496a...`并非本轮新增标签。它们已硬编码在下载的原始V43 Notebook第30个单元（从0计数）的E004报告构造中；第33个单元的E006 provenance也保留同一组上游标识。本地wrapper早已注明源E004报告保留ancestor-source identifiers。

这些字段应解释为嵌入的祖先/协议来源标识，不能据此将实际执行版本改称V80。原Notebook、E004/E006报告全部保留原样；实际执行来源以原文件哈希、V43元数据和外层验证回执为准，也不从这些标签推断隐藏榜分。

逐单元行号、原报告哈希及核对证据见 [结构化补充](v43_source_identity_addendum_20261105.json)。没有执行模型或全量数据扫描。
