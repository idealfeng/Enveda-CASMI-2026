# produre2 执行结果（Class 3 候选结构生成能力审计与消融）

对应 `produre2.md` 工程任务书的前 5 步（执行指令第一步~第五步 = 阶段一~阶段五）。

- [step01_audit.md](step01_audit.md) —— 一、审计现有生成器与调用链
- [step02_isolation.md](step02_isolation.md) —— 二、身份隔离方案与泄漏审计
- [step03_generation.md](step03_generation.md) —— 三、Class 2/3 生成能力实验
- [step04_metrics_ablation.md](step04_metrics_ablation.md) —— 四、指标与消融
- [step05_report.md](step05_report.md) —— 五、测试 + 最终报告（9 问）

机器可读产物（`artifacts/`）：

- `reaction_template_inventory.csv` —— 46 个反应模板清单（第 1 步）
- `step2_leakage.json` —— 身份隔离/泄漏审计（第 2 步）
- `step3_generation_summary.json` / `step3_per_query.csv` —— 生成能力实验（第 3/4 步）
- `step5_tests.json` —— 12 项自动化测试（第 5 步）

脚本：`step1_templates.py`、`step2_leakage.py`、`step3_generation.py`、`step5_tests.py`

## 重要边界

1. 本任务聚焦**生成器（derive.py）能力**，用**候选池质量差匹配模板**作为母体的 bounded 代理，**未跑谱检索母体通道**（需 Library/GPU）。
2. 全部只读 + 派生实验，无 GPU、无网络、无 Kaggle 提交。
3. 生成能力实验是 **derive-only**，未测排序后的 Recall/MRR/Top-1（Q4 需全管线，未做）。
