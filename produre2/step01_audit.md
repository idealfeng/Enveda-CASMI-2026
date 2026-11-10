# 一、审计现有代码与正式预测流水线（阶段一）

## 结论

- **生成器确实存在且被正式流水线启用**：`EngineCfg(generate=True)` 在 Flex V56 中实际生效，生成候选以 `pid=-1` 进入统一候选池并参与排序（有 `is_gen`/`gen_parent_sim` 等专属特征）。
- 生成器 = `derive.py` 的 **RDKit Reaction SMARTS 衍生物生成**：给定母体结构 + 质量差，枚举质量匹配的单步/双步反应模板。
- 已解析 **46 个反应模板**，产出 `reaction_template_inventory.csv`。

## 实际调用链（已追踪）

```
Engine.run() (engine.py:236)
  └─ if cfg.generate and analogs:
       gen = self.generate(analogs, target, set(P.key[c] for c in win))   # :251
            ├─ parents = [a for a in analogs if a.sim >= gen_min_sim][:gen_n_analog]  # :178
            ├─ tol = max(gen_tol_da, target * ppm_win * 1e-6)                          # :179
            ├─ for each parent: delta = target - struct_mass[parent]
            │    prods = derive.derive(parent_smiles, delta, tol, max_steps=2,
            │                          max_per_analog=gen_max_per_parent)              # :185
            │    → standardize_smiles → score_key → dedup(seen) → mass check → fingerprint
            │    → append {smiles, key, mass, fp, sim, steps=1, tan}                    # :204-205
            └─ stop when len(out) >= gen_max_total
  └─ C = self.candidates(target, drop_pid, gen)   # :252
       → generated candidates get pid=-1, is_gen=1, gen_steps, gen_tan (engine.py:219-233)
  └─ 特征 G 通道: is_gen / gen_parent_sim / gen_steps / gen_parent_tan / n_gen / gen_rank_fz (:457-462)
```

Flex V56 侧（`cell_37`/`cell_39`）：`EngineCfg(generate=True)`；生成候选 `pid<0`，在 popularity 重排中**保留自己的槽位**，formula 加 `|gen` 单独成 ICEBERG 组。

## 生成参数（源码确认，与任务书表一致）

| 参数 | 值 |
|---|---:|
| `gen_n_analog`（母体最大数量） | 6 |
| `gen_min_sim`（最低母体相似度） | 0.3 |
| `gen_max_per_parent`（每母体最大生成） | 60 |
| `gen_max_total`（每查询最大生成） | 150 |
| `gen_tol_da`（质量容差） | 0.004 Da |
| `max_steps` | 2 |
| 实际质量容差 | `max(0.004, target*10ppm)` |

## 关键发现（审计中值得注意的 3 点）

1. **`gen_steps` 被硬编码为 1**（engine.py:205），尽管 `derive` 内部支持 2 步组合——即排序特征里的 `gen_steps` 不反映真实的双步生成。
2. **生成候选与池内已有身份去重**：`seen = set(exclude_keys)`，池窗口内已有的 key 不会再生（engine.py:177,193）。
3. **质量差匹配是精确质量级**（0.004 Da），模板组合 delta 是离散值，因此只有质量差恰好命中某模板组合的母体才会触发生成。

## 反应模板清单

46 个模板，分类计数：糖基化/脱糖 9、羟基化/氧化 6、甲基化/甲氧基化 5、乙酰化/脱乙酰 5、其他 10、氢化/脱氢 3、脱羟基 2、脱甲基 2、硫酸化/脱硫酸 2、脱羧 1、脱甲氧基 1。

完整清单：`artifacts/reaction_template_inventory.csv`（含 reaction_smarts、formula_delta、exact_mass_delta、类别）。

## 产物

- `step01_audit.md`（本文件）
- `artifacts/reaction_template_inventory.csv`
- `step1_templates.py`
