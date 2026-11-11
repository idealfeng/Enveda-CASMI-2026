# Q3 / Q4 / Q5 全量重跑结果（真实 Engine，谱相似母体通道）

方法修正：本轮改用**真实 canqiang E006 Engine**——母体由**质量位移谱相似度（`search_shift`）**检索，
不再用"精确质量差命中模板"的代理；Class-3 通过 `exclude_sid`（隐藏真结构参考谱）+ `drop_pid`
（从候选池移除真结构）实现，且推理代码不读 truth 选产物。

## 结论速览

| 问题 | 答案 |
|---|---|
| Q5 真实反应路径 / 覆盖 | **19/48 = 0.396**（同分异构化 ON）；母体相似度均值 0.689 |
| Q3 瓶颈 | **母体数量（n_analog）> 反应步数 > 模板覆盖 > min_sim；质量容差无影响** |
| Q4 排序增益 | 160 特征真实 ranker：恢复 19/48，**19/19（100%）进 top-25**，Class-3 MRR 0.2958 |

## Q5：真实反应路径（`artifacts/q5_real_paths.json`）

- 母体检索健康：6 个母体，谱相似度 **mean 0.689 / min 0.379 / max 0.914**。
- **真正恢复真结构的模板**（按命中次数）：`hydrogenate_CC`、`dehexose`/`hexose_O`（糖基化/脱糖）、
  `dehydrogenate`、`dehydroxyl_*`、`demethoxy`、`hydroxyl_*`、`deacetyl_O`、`deprenyl`。
- **使用量最高但基本是噪声**：`hydroxyl+dehydroxyl`、`hydrogenate+dehydrogenate` 等 delta≈0 中性
  组合（同分异构化枚举），生成大量产物但**只多恢复 1 个查询**（19 vs 18）。

## Q3：单因素配对消融（`artifacts/q3_ablation.json`，transformation-only）

| 条件 | 恢复数 | 覆盖率 |
|---|---:|---:|
| base（6 母体/sim0.3/tol0.004/2步/全模板） | 18 | 0.375 |
| n_analog=3 | 13 | 0.271 |
| n_analog=12 | **20** | **0.417** |
| min_sim=0.1 | 18 | 0.375 |
| min_sim=0.5 | 16 | 0.333 |
| tol=0.002 / 0.010 | 18 | 0.375 |
| max_steps=1 | 13 | 0.271 |
| additions_only | 9 | 0.188 |
| removals_only | 11 | 0.229 |

瓶颈排序：**母体数量（+5%/+4%）≈ 反应步数（+10%）> 模板覆盖（additions+removals 各自不足）> min_sim > 质量容差（无影响）**。
即：母体数量是"可调且有效"的第一杠杆，但不存在单一致命瓶颈；质量约束不是瓶颈。

## Q4：排序增益

- `ranker_v4b.pkl` 有 **160 个特征**（`fe_v4` 融合：casmi 94 + derivation/frag2/analog_struct/model_views/fragnet 66），入口是独立代码 `fe_v4/V1FE.py`，非正式 notebook。
- **真实 160 特征 ranker（`artifacts/q4_full_rank.json`）**：Class-3 generate ON：
  - 恢复 **19/48**，其中 **19/19（100%）进 top-25**，名次 = `[1×12, 2, 3×3, 4×2, 5]`（12 个 top-1）。
  - Class-3 有生成 MRR = **0.2958**；恢复的 19 个平均 MRR = **0.7474**。
- **轻量 fz 近似（`q4_light_fz.json`）**：18/19（94.7%）进 top-25，MRR 0.2246 —— **160 特征 ranker 明显优于 fz 单特征**（top-25 100% vs 94.7%，Class-3 MRR +31%）。
- dev 面板（Class-2，真结构本就在池内）：生成**完全冗余**，排名增量 **0**。
- **结论**：生成恢复的真结构在真实 ranker 下**全部能进 top-25（100%）**；生成在真正 Class-3（库外结构）上的价值被 160 特征 ranker 确认，且比 fz 下界更强。
