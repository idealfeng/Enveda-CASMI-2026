# 四、指标与消融（阶段四）

## 指标（真实 Engine）

| 指标 | 值 | 说明 |
|---|---:|---|
| Generation Coverage（Class-3） | **0.396（19/48）** | 真实谱母体通道，同分异构化 ON |
| 母体谱相似度 | mean 0.689 | 母体检索健康 |
| Valid Structure Rate | 1.0 | derive 只产出合法 SMILES |
| Recall@25 / MRR / Top-1 | 见 Q4 | ranker 需 160 特征完整管线 |

## 消融（单因素配对，`artifacts/q3_ablation.json`）

| 条件 | 覆盖率 |
|---|---:|
| base（6 母体/2步/全模板） | 0.375（18/48） |
| n_analog=3 / 12 | 0.271 / **0.417** |
| max_steps=1 | 0.271 |
| min_sim=0.5 | 0.333 |
| additions_only / removals_only | 0.188 / 0.229 |
| tol=0.002 / 0.010 | 0.375（**无影响**） |

**瓶颈排序：母体数量 ≈ 反应步数 > 模板覆盖 > min_sim > 质量容差（无影响）。**

## 结论

- 生成器"能生成、合法、且能恢复真结构"，真实覆盖率 **0.396**。
- 母体数量是**可调且有效的第一杠杆**（3→13、6→18、12→20），但非唯一瓶颈。
- 质量约束不是瓶颈；同分异构化是噪声（只 +1/48）。
- 完整排名级 Q4 见 `Q345_RESULTS.md`。

## 产物

- `artifacts/q3_ablation.json`、`artifacts/q5_real_paths.json`、`artifacts/q4_smallscale.json`
