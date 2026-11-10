# produre2 执行结果（Class 3 候选结构生成能力审计与消融）

对应 `produre2.md` 工程任务书。

## 最终结论（2026-11-10 真实 Engine 重跑）

- **真实 Generation Coverage（Class-3）= 19/48 = 0.396**（真实谱母体通道 `search_shift`，6 母体）。
- 恢复的真结构**高度可排名**：18/19（94.7%）用 fz 排进 top-25，多数 rank 1-2。
- 瓶颈排序：**母体数量 ≈ 反应步数 > 模板覆盖 > min_sim > 质量容差（无影响）**。
- **决策：生成作为后续独立研发挂起，不占今日 5 次提交名额。**

## 报告与产物

- [step01_audit.md](step01_audit.md) —— 一、审计现有生成器与调用链
- [step02_isolation.md](step02_isolation.md) —— 二、身份隔离方案与泄漏审计
- [step03_generation.md](step03_generation.md) —— 三、Class 2/3 生成能力实验
- [step04_metrics_ablation.md](step04_metrics_ablation.md) —— 四、指标与消融
- [step05_report.md](step05_report.md) —— 五、测试 + 最终报告（9 问）
- [Q345_RESULTS.md](Q345_RESULTS.md) —— Q3/Q4/Q5 全量重跑汇总

机器可读产物（`artifacts/`）：

- `q5_real_paths.json` —— 真实反应路径 + 恢复明细（Q5）
- `q3_ablation.json` —— 单因素配对消融（Q3）
- `q4_light_fz.json` —— 恢复结构 fz 排名（Q4 轻量近似）
- `q4_smallscale.json` —— dev 面板 Class-2 oracle 上界（Q4）
- `step2_leakage.json`、`step5_tests.json`、`reaction_template_inventory.csv`

脚本：`step1_templates.py`、`step2_leakage.py`、`step5_tests.py`、
`q345_lib.py`（真实 Engine harness）、`q5_templates.py`、`q3_ablation.py`、`q4_light_fz.py`、`q4_smallscale.py`

## 方法边界

1. Q3/Q4/Q5 使用**真实 canqiang E006 Engine**（Library 2.5M 谱 + Pool 710k 结构 + fpnet GPU），母体由谱相似度检索，非"质量差匹配模板"代理。
2. Class-3 = `exclude_sid`（隐藏真结构参考谱）+ `drop_pid`（候选池移除真结构），推理不读 truth。
3. Q4 排名是 **fz 单特征近似**（94 特征里最强），不是 160 特征完整 ranker（`ranker_v4b.pkl` 需完整 Flex 融合管线）。
4. 全部只读 + 派生实验，无 Kaggle 提交。

## 决策记录

- 生成在真正 Class-3（库外结构）上：**候选层 19/48 + 排名层 94.7% 进 top-25**，价值真实。
- dev 面板（Class-2）上生成**完全冗余**（真实恢复的查询真结构都已在基线 top-25，排名增量 0）。
- **生成作为后续独立研发，不占今日 5 次提交名额**（见 `reports/improvement_ledger.json`）。
