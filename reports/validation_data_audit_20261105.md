# 48 分子开发诊断数据审计

当前数据：`runs/validation_pilot_v2_20261104/manifest.json`。这是参考库隔离诊断，**存在明确预训练目标曝光，不是干净独立泛化验证**。

- 24 个同仪器 NP 身份 +24 个跨库开发身份，共240条真实谱。原峰、adduct、仪器、极性、能量等所有原始字段，均与 `source_row` 指向的 train 行逐值一致。
- RDKit 为官方2026.03.3，先移除立体化学再做 tautomer canonicalization。48个标签的官方身份一致。
- 275,810 个 raw key、277,566 个 raw key/SMILES 变体全部解析重原子组成；仅对组成可能与查询一致的5,987个变体做昂贵规范化。没有用 full formula 或电荷/H数作为排除 gate，没有未解析结构。
- 48个查询身份对应51个需屏蔽的 raw key；官方身份等价的额外 raw key 已被纳入。Class2参考/analog共屏蔽5,725条谱，覆盖19种训练 adduct，包括官方查询列表外的 dimer、金属等加合物。候选结构不按这些 mask 删除。
- 完整2,539,608条训练谱已做精确重复扫描：哈希包括原 float64 precursor、adduct、mode，以及排序后的原float64峰对。发现240条匹配（查询本身），没有额外跨库精确重复。Class1排除文件包含这240行。未声称覆盖近重复、舍入变体或加合物转换相似谱。
- 查询只保留官方10种adduct中的谱，实际出现8种；全库排除不受该 whitelist 限制。仅dimer的开发身份 `DJNFXUFERDZHCD` 从活跃小样中跳过，以冻结dev清单中的下一身份补足。原开发200与最终250清单未重抽。
- 每分子最多12谱只是本轮开发预算，不能作为隐藏测试限制。36个分子多谱、24个多adduct、17个双极性、24个多能量。cap共舍去70条支持谱；`cross_DKZBBWMURDFHNE` 原68条谱、35个adduct/CE桶，当前12条只覆盖正模式。这项采样偏差已经记入逐分子选择审计；以后扩大数据时应先保证极性/加合物覆盖，再增加能量覆盖。本轮不事后改冻结样例。
- NP完整250、跨库开发200、最终锁定250的split保持原hash。最终250没有生成查询数据、预测或评分，活跃身份交集0。锁定仅指本项目不参与选择，不能消除预训练曝光。

已知曝光：FPNet full1 的上游说明声明用全部训练fold；Saner `final_model.pt` 的 `training_result.json` 明确 full-data refit，包含原validation身份，并要求不要用该holdout评估final模型。fold0的NP排除声明只对该组件有效，不能担保全栈。其他公共模型/ranker成员身份未知。

2026-11-05仅修订 manifest 污染说明与query whitelist文字，没有修改查询、标签、mask、split或资产hash。新manifest SHA-256为 `8e1ab36f2d8b7f800aa88baf845c0ffdc3790d36bdcabbb6d465ace05a571b09`。旧 `f20ea449…` 被记录为明确的元数据前驱，已启动运行继续保留其原始config绑定。

完整一致性结果：`runs/validation_pilot_v2_20261104/dataset_integrity_report.json`（passed）。重验命令：

```bash
source scripts/linux_env.sh
.venv-linux/bin/python scripts/audit_validation_dataset.py \
  --manifest runs/validation_pilot_v2_20261104/manifest.json
```

实际模型运行结束、`validation_runtime_audit.json` 为passed后，再汇总阶段候选和固定候选消融：

```bash
.venv-linux/bin/python scripts/evaluate_validation_run.py \
  --manifest runs/validation_pilot_v2_20261104/manifest.json \
  --run-root runs/validation_flex_c2_20261105b \
  --output reports/validation_flex_c2_20261105b
```

评估输出含分panel指标、分子级MRR、真实观测阶段的truth presence、阶段间候选丢失、V0对V1/CUSTOM固定identity集合审核和paired bootstrap。E2质量窗只属于E2结构池，E1记录是候选已物化/剪枝后，PubChem只导出top列表；未观测的全球候选召回和缺失stage行明确为unknown。
