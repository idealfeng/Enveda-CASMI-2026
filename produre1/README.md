# produre1 执行结果（全十二步）

对应 `produre1.md` 工程任务书 EXT-LIB-001 的全部十二步（一～十二），即 P0-A、P0-B、P0-C、P1-A、P1-B、P2 六段工作。第 1–7 步含实际运行数据，第 8–12 步为设计/交付/执行验收/约束/终答。

- [step01_background.md](step01_background.md) —— 一、项目背景
- [step02_P0A_reproduce.md](step02_P0A_reproduce.md) —— 二、固定基座与复现 0.488
- [step03_P0B_attribution.md](step03_P0B_attribution.md) —— 三、Takumu / MassBank 贡献归因
- [step04_P0C_matching_audit.md](step04_P0C_matching_audit.md) —— 四、外部谱匹配可靠性审计
- [step05_P0C_promotion_audit.md](step05_P0C_promotion_audit.md) —— 五、外部候选提升机制审计
- [step06_P1A_validation_panel.md](step06_P1A_validation_panel.md) —— 六、建立外部谱库专用验证集
- [step07_P1B_enveda180.md](step07_P1B_enveda180.md) —— 七、Enveda-180 接入
- [step08_P2_architecture.md](step08_P2_architecture.md) —— 八、神经网络方向（架构设计）
- [step09_engineering_deliverables.md](step09_engineering_deliverables.md) —— 九、工程目录与文件交付
- [step10_execution_acceptance.md](step10_execution_acceptance.md) —— 十、执行顺序与验收标准
- [step11_constraints.md](step11_constraints.md) —— 十一、执行约束（合规自查）
- [step12_final_report.md](step12_final_report.md) —— 十二、最终研究报告（14 问）

机器可读产物：

- `artifacts/attribution_summary.json` —— 第 3 步归因与指标汇总（48 查询）
- `artifacts/per_query_attribution.csv` —— 第 3 步逐查询归因
- `artifacts/step6_validation_summary.json` —— 第 6 步 200 身份验证面板指标
- `artifacts/step6_per_identity.csv` / `step6_bclass_exclusion.csv` —— 第 6 步逐身份 + B 类排除
- `artifacts/step7_enveda180_summary.json` / `step7_enveda180_membership.csv` —— 第 7 步
- 脚本：`attribution.py`、`step6_validation_panel.py`、`step7_enveda180.py`、`reference_cell14.py`

## 重要边界（读任何数字前必读）

1. 第 3/4/5 步运行在**冻结 48 查询开发面板**；第 6/7 步运行在**冻结 `cross_development`（200 身份）面板**。都不是隐藏测试集。
2. 第 3 步基线是 **Flex48 V0 诊断排序**（非 0.482 MASS）；第 6/7 步用匹配层面的 rank-1 规则（无管线 base ranking）。
3. 因此 ΔA/ΔB/ΔAB 是"开发面板上的边际贡献"，**不能**直接等于"0.482→0.488 的涨分分解"。
4. 第 6/7 步的 membership / 排除是**原始 inchikey14 级别**，非完整官方身份（互变/立体别名可能有差异）。
5. 已知预训练曝光，结果只能作诊断，不是干净泛化证据。
6. 全部只读、无网络、无 GPU、无新提交。
