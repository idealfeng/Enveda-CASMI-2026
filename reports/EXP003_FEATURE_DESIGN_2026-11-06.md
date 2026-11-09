# EXP003-A：GL 逐谱候选 margin 支持率，先审计信息再比较排序

日期：2026-11-06。状态：`design_frozen_no_truth_no_model_no_ranking_change`。本文件只基于源码；没有读取 query 真结构、任何标签或锁定250，没有运行模型或评价效果。参数和分组规则在查看支持率分布及真值结果前固定。

## 1. 增量到底在哪里

`gl_runner.py:727–748` 对每个候选逐张覆盖谱算 entropy similarity，跳过缺失预测和非有限值，最后取有限相似度的普通均值。`gl_fuse.py:94–139` 只接收这个标量：在原 top_n 内按已有 formula 分组，计算 `z(base)+Σ lam*z(model_mean)`，至少一个模型覆盖 `max(2,min_covered)` 个候选才重排；放回原公式组的槽位。`_z` 使用 ddof=1，缺失/常数/不足2值记0；至少2个重评分列实际贡献时按 `tie_eps=1e-9` 网格稳定处理平局。覆盖数量门槛不是逐谱支持率。

已有 `tri_v30/embedded/ranking.py:30–60` 定义 `neural_std`、`neural_top_gap`、`neural_agrees_top1`、`engine_agreement`、`neural_delta_rank` 等特征；不能声称整套系统没有 margin、离散度或一致性。当前 fixed RRF 实际调用 `rrf_order`（`consensus.py:38–48,111`；`ranking.py:11–17`），不调用该 `make_features`。本次唯一新增对象是：**同一 query、同一公式候选之间，在重复谱处理后的真实观测 CE 组上的两两分数差支持率**。它不能从每候选均值、单候选谱间 std 或跨引擎出现数恢复。

纯手工例子：A 三个 CE 得分 `(0.90,0.10,0.10)`，B 为 `(0.35,0.35,0.35)`；A 均值略高，B 在2/3个CE组胜出。这里没有查询标签，也没有声称支持率优于均值。

来源冻结：

| 文件 | SHA256 |
|---|---|
| `assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier/gl_runner.py` | `5c4f74313ac54263d05d987c39d012d81ec57c5f35e1095ecd49a5bcb6440fca` |
| 同目录 `gl_fuse.py` | `ea390f5f29705c015f39c509cc2b86e6a360d0bb90db61c87c507068f38ae58e` |
| `scripts/forward_trace_runner.py` | `1f51a106b532bec40b59ed01e83393bdc9660277d893d7f89660dae964d34fe4` |
| `experiments/EXP003_FORWARD_SPECTRUM_CONSISTENCY.md` | `e28b74ac08f723818bc387b84227e494b7d40602d069cb0dc659995f6628df26` |

最后一项是本设计读取时的历史快照；Root 随后仅澄清当前输入均 H+、runner 也支持 Na，该计划文件 SHA 因此改变。导出门不将此文案变化误报为 runner 或特征算法变更。

## 2. 固定候选与身份

- 分子和候选只来自已经冻结的 runner input；不得加真结构、扩大候选池或按结果重新挑面板。第一步可以对全45个已缓存 query 导出，不要求重放检索及其他引擎。
- 原排序对照使用该次运行原 `smis/keys/scores/formulas`、ICE/GL 均值、原 lams/top_n/min_covered/tie_eps。公式身份和原始次序原样保留。
- 官方身份使用候选结构的 RDKit2026.03.3 official IK14 sidecar；不能用 forward 环境 RDKit2025 代替。身份不等于真值。
- 初始无真值信息审计可用候选自身 RDKit2026 `CalcMolFormula` 派生公式；必须标注 `candidate_rdkit_formula`。真正排序干预前必须与原排序 `formulas` 逐候选核对；不一致的组跳过，不能悄悄替换原 formula。
- `H` 是某 query 某非空公式在冻结候选表中的全部成员，固定竞争集合，`K=|H|`。同一组存在无身份候选或重复 official identity 时，主特征标为不适用并记录原因；不去重、不删候选、不拿别名增加对手权重。至少2个唯一身份才有候选对照。正式干预的 H 必须进一步绑定原 top_n 公式组。

## 3. 重复谱和 CE 的精确定义

1. **观测去重先于 CE 分组。** 同一 mid 内，以 trace 的 `spectrum_content_sha256` 分簇；它由原始 `mz,it,prec,adduct,mode` 的确定性 JSON 计算。无论 spectrum_id 是否不同，同内容只允许一张观测投票；相同 ID 却不同内容不合并。不同 query 绝不合并。
2. 同内容簇的 `(adduct,instrument_token,ce_units,prediction_mode,ce_bucket)` 必须相同。若有冲突，整簇排除并记录 `duplicate_metadata_conflict`；不任挑一个 CE，不跨 CE 投两票。同簇候选得分必须逐项相同且完整；不相同记审计冲突，不取最大值。代表观测为最小原 `spectrum_index`。
3. 这只是**精确原谱去重**，不声称识别峰顺序变化、近重复或同一次采集的相关谱。第一轮不添加相似度阈值聚类；残余相关性作为限制报告。重复多不等于独立重复实验多。
4. 首试只用 upstream 实际覆盖的正模式 `[M+H]+`，且 `prediction_mode=single_ce`、bucket 有限。runner 本身 `COV` 还支持 `[M+Na]+`（`:52,427–430`）；这里 H+ 是实验范围限制，不是声称模型不支持 Na。
5. 直接使用 trace 的 `ce_bucket`，绝不另算四舍五入：上游为 `np.round(ce/5)*5`，最小5；NCE 从原文本数字均值解析，其他情况按 ce_ev 均值/legacy ce，见 `:409–424`。禁止把 NCE20 与 eV20 当同一 CE。
6. stratum 为 `(mid,adduct,instrument_token,ce_units_raw)`，其中缺失单位用显式 `unspecified`，保留为单独层，不与 eV/NCE 合并。CE 组为该 stratum 内相同有限 bucket 的去重观测。未知CE的 `merged_20_40_60` 不参与本特征：它是一次合成预测，不是三张独立真实观测；仍保留在原均值对照里。
7. 对 H 只使用全部候选在该观测上均 `status=scored` 且 score 有限的共同观测集合。任一候选缺失/非有限，则此观测对整组不投票；不补0、不把缺失当败票、不按候选分别挑容易谱。各 CE 组内对剩余唯一观测取算术均值 `s[b,c]`，每组一个票重。
8. 每个 stratum 至少2个不同有效CE bucket。若多个 stratum 都合格，固定选择有效CE组数最多者，再按有效唯一观测数最多者，最后按 `(adduct,instrument_token,ce_units_raw)` 字典序选一个。选择不看均值大小、支持率或真值；所选/弃选层及原因全部导出。用同仪器同单位内的跨CE支持，避免把仪器差异算作CE重复。

## 4. 唯一新增特征

设选中的 B 个 CE 组、K 个候选为 H。对每一对不同 official identity 的候选：

```text
delta[b,c,d] = s[b,c] - s[b,d]
v(delta) = 1        if delta >  1e-9
           0.5     if abs(delta) <= 1e-9
           0        if delta < -1e-9
R[c] = sum_b sum_(d!=c) v(delta[b,c,d]) / (B*(K-1))
F[c] = 2*R[c]-1
```

`R∈[0,1]` 是 CE 等权、对手等权的候选支持率；K=2 时恰为候选在 CE 组上的胜率（平局半票）。它不是 margin 大小的再平均。`1e-9` 固定为浮点平局处理，沿用原 glue 的量级，不按结果调参。不再叠加 std、最差 CE、最大竞争者 gap、三模型投票或覆盖分数。B<2/K<2/重复身份/无完整共同观测时，R/F 输出 null 和原因，排序臂整组不干预，不能宣称 F=0 是观察到的中性证据。

同 R 的候选保留原顺序。导出信息审计中的 winner 使用集合：`argmax(mean_GL)` 与 `argmax(R)` 各保留完整并列集合，报告“集合不同”“完全无交集”“均值唯一winner不在支持率winner集合”三个计数；不通过随意破平局制造冲突。均值 GL 既报告上游原均值 winner，也另列相同 CE 等权观测下的均值 winner，从而区分 CE 平衡/去重和“均值→胜率”的变化；这些均是信息诊断，不是额外实验臂。

## 5. 最小无扫参的固定候选对照

先做**stage-level 信息审计**，不改排名、不读真值；只有 trace 重建原均值逐项完全一致、覆盖完整、分组审计通过，并出现有严格可动槽位且 F 非常数的 query，才值得进入下一步。此阶段不重训模型、不跑外层融合、不占正式提交。

后续只有两个预登记臂，不扫权重：

- C：原 `rerank_multi`，必须重现已有阶段输出索引，候选与公式组 slots 原样不变。
- T：用同一次的原组内 `T0=z(base)+Σlam*z(original_mean)`（**原全组范围**，不在尾部重算 z）加唯一项 `0.10*F[c]`。F 不再 z 标准化，避免几乎常数时放大；0.10 是预先固定的较小 z 分单位扰动，不声称最优。沿用原 n_act/tie_eps 网格规则。若原 T0 浮点值/参数不能精确恢复，先停止，不拿位置分数冒充原融合分数。

T 只可重排 C 的 rank2–25 中、formula 与 C 的原 top1 完全相同的候选，放回这些候选原来的槽位；固定 top1、其余公式、rank26之后及候选集合。H 为原 top_n 内该公式全组，F 的对手集合不能因尾部限制而改变。至少2个可移动槽位才动；不满足特征条件则逐项沿用 C。平局以 C 中原位置稳定排序；`0.10=0` 的退化检查必须与 C 完全一致。这个 gate 是预先限定干预范围，不在看到真值后调阈值。

此对照一次只改变一个固定数值特征；CE/重复谱处理只用于 F，原 ICE/GL 均值及原权重不变。不得同时以“新聚合均值”替代原 mean，也不得再加神经RRF/LOTUS/engine间一致性。

**可见性限制必须直说：** 保护 top1 后，Top1 accuracy 必然不变；不换 top25 集合后，候选召回和 top25 recall 必然不变。只能观察已在2–25且与原top1同公式的真结构 MRR 变化。真结构原在26+、原top1公式错误、只剩一个可动同式候选、支持率只想改变top1时，真实可用信号都会被该 gate 隐藏。严格臂零收益不能推出逐谱特征无价值；应同时报告宽松信息可用组数与严格可动组数，但不能事后扩大干预范围再当同一实验。

## 6. 先交的无真值产物与停止条件

建议独立导出，不写 submission：

- `candidate_support_features.jsonl`：mid、原候选位置/SMILES/official identity/公式、原 GL mean、CE 平衡 mean、B/K、R/F、所选stratum、缺失原因；没有 label/truth 字段。
- `support_information_audit.json`：输入/trace/sidecar/代码 SHA，原/covered/精确去重谱数，冲突/merged/缺失排除数，同式≥2唯一身份组数、≥2独立CE组的 query/group 数、F非常数组数、均值与支持 winner 冲突数、每条排除原因计数。原均值 winner 对照包含完整平局集合。
- 有原 stage 排名 sidecar 时再加严格可动 query/slot 数和同 top1 公式限制；没有该 sidecar 就明确 `strict_gate_not_audited`，不可从 runner cands 次序假称最终 top1。

若未绑定 source/identity、原均值不能精确重建、trace有不完整候选×谱对、分组冲突未解释，停止派生特征。若没有合格组或 R 全为常数，登记信息不足；不扫描 CE 切法/epsilon/0.10/可动范围来凑信号。仅当进入预登记效果评估时再由独立评估器读取标签，NP/cross 分开，登记逐例收益/损失与阶段和最终流程之差。旧开发面板及模型训练曝光限制继续保留，不能称干净泛化或预告银牌收益。
