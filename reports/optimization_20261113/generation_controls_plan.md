# 11/13 两条追加生成单因素探索

用户明确要求剩余四次继续探索提交。原“只提交已见局部正收益候选”的筛选建议被这条新授权覆盖。这里交付其中两条生成对照，不预报涨分。

共同父版本为精确 .488 冠军（ref 58156482，Notebook SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`）。共同保留原 head、AB、神经评分、MASS、FROZEN 及其他原 32 个 cell 对象。只在原 cell12 追加 runner 路由，并加最后一项生成审计。现有已提交/已验证冻结版本未覆盖。

| arm | 唯一算法改动，相对冠军 | 固定配置 | Kaggle target |
| --- | --- | --- | --- |
| generation_noiso_control | 关闭近零质量差中性枚举 | 6 母体 / 总量150 / 每母体60 / 双步 / iso=False | stormseye/casmi26-gen-noiso-only-1113 |
| generation_budget_only | 总生成上限150→300 | 6 母体 / 总量300 / 每母体60 / 双步 / iso=True | stormseye/casmi26-gen-budget-only-1113 |

构建入口：`scripts/build_generation_controls_20261113.py --prepare`。新冻结目录已存在，脚本会拒绝覆盖；需要新修订时应另建目录。

runtime 从已完成真实生产路径验证的 e494 engine 绑定版派生。所有观察器的 `[:12]`、母体12上界、产物300上界、强制False和derive参数检查都由 CONFIG 统一驱动。报告中的 `parent7_12_calls` 仍表示超过原6母体的实际调用，这两版都固定6，因此应为0。

## 实际完成的检查及边界

`scripts/check_generation_controls_20261113.py` 在 WSL 官方 RDKit 2026.03.3 执行，每版19项检查全部通过。包括嵌入 module/runner 字节、recipe/Notebook/metadata、原32 cell保留、源码编译、hooks/derive pin、配置边界，以及真实原始 derive 函数和新 wrapper 函数体的语义检查。

固定简单结构 `COc1ccccc1O`：noiso 版把 delta=0 的6个产物变为0，非零 delta=15.994915 的7个双步产物与原函数完全相同；budget 版两者均与原函数完全相同。错误步数会被拒绝。这只是实际派生组件核验，不是 Engine/V1FE、ranker 或完整模型推理，未加载大谱库、神经模型或占用 GPU。

复用的完整路径证据是 `runs/generation_production_20261113_r2/verification.json`，其 CONFIG 为12/300/noiso。**这两个新 CONFIG 没有重跑完整生产链，也尚无隐藏结果。** 该既有两查询输入含未消费的标签元数据，只能当部署路径证据，见 `generation_disclosure_addendum.md`。新 stage 的 recipe 和 static review 已明确这些边界。

## 固定指纹

| arm | Notebook SHA256 | runtime module SHA256 |
| --- | --- | --- |
| generation_noiso_control | `794a4aeff3d71347db36b7da76beb23fae1a6eb754cb726432c5f8a29b351aaf` | `283c7f49a4a77d821f2f44d347c934c001a18ee65fd637706e4cbe7760bdb062` |
| generation_budget_only | `7f87816791ce5fb87b68d747286acebd6e803d7ab1752edcfb5f5ee951595272` | `b7e3366aeb19b03da7caa1eadfdbf7c3afc25025b8e013d154a0e5ccc5773b3f` |

共同专用 runner SHA：`153c85fb59025f3c2fa75cf9a64ffe7aa6cdb26b25113fee9fa46643c22f1182`。实际生产 engine pin：`e4943fb26a8141f47ea95e744910c2d0f4746e36e72ef43e3263e7f327cfc0b5`。各目录 `branch_spec.json` 绑定 recipe、Notebook 和 metadata；机器检查结果在 `generation_controls_checks.json`。

若其中有新高分，再根据它相对精确冠军的单一改动记录来源；没有真实榜分时不写成收益。完整路径仍可能遇到不同 CONFIG 的候选数量、显存/内存或隐藏数据边界问题，提交后以官方结果为准。
