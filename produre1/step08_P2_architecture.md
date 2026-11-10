# 八、神经网络方向（P2）：Candidate-conditioned Multi-spectrum Matching 架构方案

## 结论

本步只做架构设计与数据准备建议，**不训练**（与任务书一致）。此前同分子式新 head 实验（Monitor 0.786→0.783、Eval 0.830→0.836，bootstrap 跨零 + 预训练曝光）证据不足支持扩大训练，故冻结为"设计待命"。

## 目标函数

\\[ f(C,\\ S_1,S_2,\\dots,S_n) \\rightarrow \\text{match confidence} \\]

其中 C 为候选分子结构，S_i 为不同 CE / Adduct / 采集条件下的质谱，输出候选结构解释整组质谱的匹配可信度。与现有"分别编码结构特征与谱特征、最后融合"不同，新模型显式学习二者之间的**条件关系**。

## 架构组件

1. **结构编码器**：GNN（GIN/GAT，RDKit 图或 2D 原子/键特征）→ 图级 embedding；可选加 3D 构象（RDKit 生成）以解释立体/连接差异。
2. **单谱编码器**：每张谱 → 峰列表（m/z、强度、前体、CE、adduct、离子模式）→ per-spectrum embedding。
3. **多谱聚合**：跨谱 attention（Set Transformer / Transformer 池化），把 n 张谱聚合成一个查询 embedding，显式注入 CE / adduct 条件。
4. **结构-谱条件融合**：cross-attention（结构 token 作为 query、峰/谱 token 作为 key-value），输出匹配 logit。
5. **碎片-峰对齐头**：可学习的碎片↔峰对齐（借鉴 in-silico fragmentation，或从结构编码器的 atom/bond 表征做 attention 到峰），显式建模"C 如何解释这些峰"。

## 关键设计点（任务书 8.1 逐条）

| 项 | 设计 |
|---|---|
| 分子结构图表示 | 2D 图 + 键特征；同分异构硬负例用分子式一致、图不同 |
| 多谱特征编码 | 每谱独立编码 + 跨谱 attention 聚合 |
| 不同 CE 条件 | CE 作为连续条件嵌入注入谱编码器 |
| Adduct 条件 | adduct 精确质量偏移 + 中性质量归一化 |
| 碎片峰对齐 | 结构 token ↔ 峰 token cross-attention |
| 解释关系 | 训练目标对齐"结构解释谱"的分数，而非独立融合 |
| 同分子式困难负例 | 从候选池按分子式采样 decoy |
| ranker 产生的 hard negatives | 用当前排序器的高分错误候选作为负例 |

## 数据准备建议

- 复用冻结 split：`cross_development`（200）开发、`cross_final_locked`（250）锁定，不污染。
- OOF / 身份隔离：按官方 InChIKey14 分子级分组，绝不按谱行随机切分。
- 负例：同分子式 decoy + 当前 ranker 高分错误候选（experience.md 已记录挖出 30,991 条实际 v2 高分错误负例，其中 15,445 同分子式）。
- 已知预训练曝光（FPNet full1 / Saner final_model full-refit）必须单列，不能当作干净 CV。

## 验收（对应任务书阶段 P2）

交付本架构方案 + 数据准备清单；不要求训练、不要求榜分。
