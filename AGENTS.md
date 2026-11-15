# 本项目的实验记录与文件维护

开始新实验或继续旧工作时，先读 `PROJECT_INDEX.md`、`docs/LESSONS.md` 和 `reports/improvement_ledger.json`，再查相关路线报告。不要仅凭较早的逐日日志判断当前最佳、失败原因或用户约束。

## 找模型与历史结果

- 模型位置、SHA、同内容分组在 `docs/MODELS.md`、`docs/model_registry.json`。索引是本地快照，实际部署仍核对固定recipe和权重。
- 把某个checkpoint当成新模型之前，先按SHA与当前组合去重；不同作者/数据集名不代表不同权重。公开V80 final与现用v2相同，验证阶段best才是不同候选。
- 正式提交在 `docs/SUBMISSIONS.md`、`docs/submission_registry.json`，当前批次状态以各批次官方读回文件为准。
- 活动/暂停/待验证路线在 `docs/EXPERIMENTS.md`；旧代理、oracle与真实ranker实验要区分。

## 完成一轮后

- 成功、降分、异常和被新证据推翻的判断都记录，至少写明父版本、实际改动、数据/模型指纹、指标类型、证据路径和下一步决策。
- 按 `docs/EXPERIMENT_TEMPLATE.md` 保存新实验；更新EXPERIMENTS与LESSONS。新高分按用户要求记录提升来源及归因边界，PENDING不记成成绩。
- 新增/改变模型或正式提交读回后，运行 `.venv\Scripts\python.exe scripts/refresh_project_index.py` 和同命令的 `--check`；它不联网。账本被后台watcher使用时避免并行手动写入。
- Kaggle请求被接受、可见运行通过、隐藏完整推理成功、榜分提升分别报告。fast_static或单组件小试不能称完整运行成功；检查数量不能代替真实生产初始化到CSV的路径覆盖。

## 路径与清理

- 所有新下载、缓存与临时文件放D盘，遵循用户已有约束。
- 不为整理目录移动既有 `assets/`、`runs/`、`submission/`、`produre1/`、`produre2/`，以免破坏引用和冻结源码绑定。新产物按新实验目录存放。
- 正式提交、模型/训练配置、日志/指标、审计和失败证据保留；缓存清理另留明确清单和回执。
- 大文件可能已通过硬链接共享，不能按路径大小直接去重。`docs/MAINTENANCE.md`说明维护规则。

- 提升记账：[improvement_ledger.json](D:/Paper/casmi/reports/improvement_ledger.json)，记录真实新高分、提升来源和归因边界。
全部提交：[SUBMISSIONS.md](D:/Paper/casmi/docs/SUBMISSIONS.md)，包括降分、异常和待评分结果。
经验与错路：[LESSONS.md](D:/Paper/casmi/docs/LESSONS.md)，记录失败原因、结论限制和再尝试条件。
模型位置：[MODELS.md](D:/Paper/casmi/docs/MODELS.md)，记录权重路径、用途和指纹。
