# 三、Class 2/3 生成能力实验（阶段二~三）

> 2026-11-10 重跑：改用**真实 canqiang E006 Engine**（质量位移谱相似度母体检索 `search_shift`），
> 不再用"精确质量差命中模板"的 bounded 代理。旧数字（0.367/0.6/0.25）作废，见下方真实结果。

## 结论（真实谱母体通道）

- **生成器能恢复候选库中不存在的正确结构**：Class-3 下 **Generation Coverage = 19/48 = 0.396**（同分异构化 ON，6 母体）。
- 母体检索健康：6 个母体谱相似度 **mean 0.689 / min 0.379 / max 0.914**。
- 有效结构率 100%，但**同分异构化（delta≈0 中性组合）生成大量噪声、只多恢复 1 个查询**。

## 实验设计（真实 Engine）

- 48 dev 查询（truth + 精确质量），Class 3 = `exclude_sid`（隐藏真结构参考谱）+ `drop_pid`（候选池移除真结构）。
- 母体 = `Engine.analogs()` 用 `search_shift` 按质量位移谱相似度取 top 100，再取 sim≥0.3 的前 6。
- 对每个母体跑真实 `derive.derive(parent, delta, max_steps=2)`，官方 `score_key` 判恢复。

## 结果

| 指标 | 值 |
|---|---:|
| **Generation Coverage（Class-3）** | **19/48 = 0.396** |
| 母体谱相似度 | mean 0.689 |
| 恢复贡献模板 | 氢化/脱糖/糖基化/脱氢/脱羟基/去甲氧基/羟基化/脱乙酰/去异戊烯基 |
| 同分异构化净贡献 | 19 vs 18（只多 1 个查询） |

## 产物

- `artifacts/q5_real_paths.json`（真实反应路径 + 恢复明细）
- `artifacts/q3_ablation.json`（单因素配对消融）
- `q345_lib.py` / `q5_templates.py` / `q3_ablation.py`
- 见 `Q345_RESULTS.md` 汇总。
