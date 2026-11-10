# 九、工程目录与文件交付

## 结论

任务书第 9 节建议的目录/脚本/产物，本次已用 `produre1/` 自包含目录落地（用户指定），命名按任务书映射；产物以 JSON/CSV 为主，Parquet 仅保留已有数据，未生成巨大 CSV。

## 实际交付结构

```
produre1/
├── attribution.py              # ≈ run_external_overlay_ablation（第 3 步归因）
├── step6_validation_panel.py   # ≈ build_external_library_validation（第 6 步）
├── step7_enveda180.py          # ≈ audit_enveda180_membership + build_enveda180_overlay（第 7 步）
├── reference_cell14.py         # 上游 Alex V12 匹配源码（审计引用）
├── step01~step12_*.md          # 各步结果与结论
└── artifacts/
    ├── attribution_summary.json / per_query_attribution.csv        # 任务书 3.2 逐查询归因
    ├── step6_validation_summary.json / step6_per_identity.csv
    │     / step6_bclass_exclusion.csv                              # 任务书 6.4 指标 + 逐身份 + B类
    └── step7_enveda180_summary.json / step7_enveda180_membership.csv
```

## 任务书建议 vs 实际

| 任务书建议 | 实际 |
|---|---|
| `reports/external_library_audit_20261110/` | 由 `produre1/` + `reports/EXTERNAL_METADATA_AUDIT_2026-11-09.json` 覆盖 |
| `scripts/audit_external_library.py` 等 | `attribution.py` / `step6_*.py` / `step7_*.py` |
| `baseline_manifest.json` / `source_schema_audit.json` | 已分散在 `recipe.json`（SHA/常量）+ `attribution_summary.json`（composition/schema）+ `EXTERNAL_METADATA_AUDIT` |
| `adduct_audit.csv` / `precursor_mass_audit.csv` | 未单独产出 CSV；结论已写入 step04 与 EXTERNAL_METADATA_AUDIT 的 rows_by_adduct |
| `promotion_audit.csv` | 由 `step6_per_identity.csv` / `per_query_attribution.csv` 覆盖 |

## 保留的版本/可复现信息

每个产物均记录：库文件 SHA256、RDKit 版本、排序常量（TAU/K_PEAKS/LIB_TAU/tolerance）、来源路径、随机种子（bootstrap 用 20261104）、scope 与 caveats。脚本运行无网络、无 GPU、无提交。
