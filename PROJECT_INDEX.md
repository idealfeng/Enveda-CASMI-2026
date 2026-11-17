# 项目导航：先从这里找

2026-11-11整理时的主线：**0.488，正式提交58156482**。分数是已确认的Public MRR@25，不代表Private。自动查分可能更新提升账本；下面的历史日期文字不是实时状态。

| 想找什么 | 去哪里 |
| --- | --- |
| 换窗口后快速接手，当前做到哪一步 | [当前交接状态](docs/CURRENT_STATUS.md) |
| 11/17公开.492复现+优化 | [本轮说明](reports/public_network_20261117/EXPERIMENT.md)、[冻结清单](submission/public_network_20261117/manifest.json)；正式58455482/58455510均PENDING，官方原始状态在`reports/public_network_20261117/` |
| 11/16 FIORA单版正式探索 | [本轮计划](reports/new_paradigm_20261116/SUBMISSION_PLAN.md)、[冻结清单](submission/optimization_20261116/manifest.json)、[组件实际执行](reports/new_paradigm_20261116/runtime_canary/REPORT.md)；云端原始状态见 `reports/optimization_20261116_fiora/` |
| 11/16新基座排名：100题最终与下一步 | [完整结果与取舍](reports/new_paradigm_20261116/RESULTS_AND_NEXT.md)、[逐题评价](reports/new_paradigm_20261116/candidate_validation100/evaluation/REPORT.md)、[错误分解](reports/new_paradigm_20261116/ERROR_ANALYSIS.md)、[100/主92预声明](reports/new_paradigm_20261116/CANDIDATE100_EXPERIMENT.md) |
| 11/15新信号实际执行 | [C审计/MIST失效/500步门控与留出](reports/execution_20261115/PROGRESS.md) |
| 精确.488生产错误分解 | [三类隔离契约](reports/champion_error_decomposition_20261115/panel_contract_review.md)、[runner](scripts/run_champion_diagnostics_20261115.py)；未完成前不当分层指标 |
| 跳出旧调参：独立新模型/直接结构生成 | [FIORA真实500步结果](reports/new_paradigm_20261115/TIMSTOF_500_RESULTS.md)、[研发决策](reports/new_paradigm_20261115/DECISION.md)、[源码级迁移依据](reports/new_paradigm_20261115/TIMSTOF_TRANSFER.md) |
| 当前最高分、每次提升来自哪里 | [唯一提升账本](reports/improvement_ledger.json)、[易读版本](reports/IMPROVEMENT_LEDGER.md) |
| 所有已提交方案，包括降分和错误 | [正式提交结果索引](docs/SUBMISSIONS.md) |
| 走过哪些错路、哪些结论后来被推翻 | [经验与失败路线](docs/LESSONS.md) |
| 现在有没有Class3能力、瓶颈在哪 | [生成与排序的分层证据](reports/BOTTLENECK_ASSESSMENT_2026-11-12.md) |
| 哪些实验已完成、待做、暂停 | [实验路线索引](docs/EXPERIMENTS.md) |
| 模型在哪、是否重复、用哪份权重 | [模型索引](docs/MODELS.md)、[完整SHA与配置](docs/model_registry.json) |
| 当前冠军可复现入口 | [固定Notebook](submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb)、[配方](submission/optimization_20261109/mass_guarded_extlib/recipe.json)、[原始分数](reports/optimization_20261109/mass_guarded_extlib/score.json) |
| 11/14本轮提交与运行状态 | [五版当前评分](reports/optimization_20261114/latest_status.json)、[调度回执](reports/optimization_20261114/batch_dispatcher_status.json)、[固定清单](submission/optimization_20261114/manifest.json)、[方案与证据边界](reports/SUBMISSION_PLAN_2026-11-14.md) |
| 11/13五次最终结果 | [结果及解释](reports/ROUND_RESULT_2026-11-13.md)、[官方原值及指纹](reports/optimization_20261114/prior_batch_final.json)、[原固定清单](submission/optimization_20261113/exploration_manifest.json) |
| 11/12五次最终结果 | [最终官方复核](reports/optimization_20261113/prior_batch_reverified.json)、[旧批说明](reports/OPTIMIZATION_BATCH_2026-11-12.md) |
| 11/11五版正式结果 | [结果及解释](reports/ROUND_RESULT_2026-11-11.md) |
| 最新公开V18与我们的区别 | [源码比较](reports/public_update_20261111/ensemble_comparison.md)、[资产核对](reports/public_update_20261111/public_asset_audit.md) |
| 11/14最新讨论与公开方案 | [下一轮优先级：extlib2/MIST](reports/discussion_review_20261114/RECOMMENDATIONS.md)、[论坛全文核查](reports/discussion_review_20261114/forum_review.md)、[6份最新源码](reports/discussion_review_20261114/notebooks/NOVELTY_REVIEW.md)、[MIST接入可行性](reports/discussion_review_20261114/mist_feasibility.md) |
| DeepSeek结论：总览入口 | [produre1 README](produre1/README.md)、[produre2 README](produre2/README.md) |
| DeepSeek结论：完整论证与数字 | [produre1最终14问](produre1/step12_final_report.md)、[produre2最新Q345/160特征](produre2/Q345_RESULTS.md)、[produre2最终9问](produre2/step05_report.md) |
| 原始任务书与独立复核 | [produre1任务书](produre1.md)、[produre2任务书](produre2.md)、[真实Q345复核](reports/produre_review_20261111/Q345_NEW_REVIEW.md)、[核心报告阅读说明](reports/produre_review_20261111/CORE_REPORT_READING.md) |
| 长期计划、逐日记录 | [作战计划](CASMI26_PLAN.md)、[经验日志](experience.md) |
| 以后怎么存实验、何时清理 | [维护规则](docs/MAINTENANCE.md)、[新实验模板](docs/EXPERIMENT_TEMPLATE.md) |
| 后续协作者先读什么、怎样持续记账 | [项目协作说明](AGENTS.md) |

查找顺序：先看此导航和结论索引，再打开证据。旧报告中的PENDING和“今日计划”是当时快照，不能覆盖后来官方读回的结果。

本次整理保留原有路径。`submission/`固定源码、`assets/`权重、`runs/`实验产物及用户实验原件均未迁移。模型和结果表可用 `scripts/refresh_project_index.py` 重新生成。
