# 2026-11-11 项目整理回执

用户希望实验扩大后仍能找回模型、经验和失败路线。本次新增索引与维护方式，保留已有实验和部署路径。

## 已完成

- 更新根README的过期最佳分：整理时已确认0.488 / 58156482。
- 新增 [统一导航](../../PROJECT_INDEX.md)、[失败与经验](../../docs/LESSONS.md)、[路线状态](../../docs/EXPERIMENTS.md)。
- 扫描并计算54个模型文件的SHA，建立 [模型表](../../docs/MODELS.md) 和完整JSON；其中17组存在相同内容，保留所有原始路径。
- 建立 [正式提交表](../../docs/SUBMISSIONS.md)，共26个编号：当前本地快照有20个有效Public分、1个异常提交、5个PENDING。已处理旧API字符串分数、旧error字段和批次简表缺字段的情况。
- 新增实验模板、维护规则、索引刷新工具以及根AGENTS说明，帮助后续工作先查旧结论、再记录新证据。
- 检查Windows及WSL均没有活动安装任务后，仅清理大于24小时的pip缓存及pip-*安装临时文件，共446个文件，逻辑大小6,339,905,785字节（5.904GiB）。硬链接可能使实际释放磁盘空间少于逻辑大小，未把目录计数当作实际释放量。

## 保留与核验

- 既有submission、produre1、produre2、experience和两份提升账本共325个文件，清理前后SHA相同。
- 没有删除或移动模型、正式提交、实验产物、用户实验原件和官方数据。
- 保留离线wheels、Windows CA证书、共享谱缓存及非pip临时目录。
- 新导航和文档链接已检查；模型路径/大小已核对；Windows RDKit和Kaggle SDK可正常导入。
- 本次没有新增Kaggle运行、提交或训练。现有只读评分watcher不受目录清理影响。

机器清单：[删除计划](cache_cleanup_plan.json)、[删除回执](cache_cleanup_result.json)、[受保护文件原指纹](protected_before.json)、[提交索引语义检查](submission_index_verification.json)、[整理摘要](summary.json)。

后续刷新索引：在项目根目录运行 `.venv\Scripts\python.exe scripts/refresh_project_index.py`，再加 `--check` 核对。索引是本地快照；最新榜分仍查当前批次watcher。
