# Extlib2实际增量与固定匹配结果

已完成的语料/谱内容/官方身份局部核查全部复用11/14真实产物，本轮没有重新扫描或重跑这些已完成实验。新训练小试另存新目录，不使用旧48或MIST17题拟合。

## 已确认增量

| 口径 | 结果 | 解释 |
| --- | --- | --- |
| C发布者raw InChIKey14 | 62,782个 | 不等于官方评分身份数 |
| raw key不在原AB | 49,408个，293,584谱 | 对原两外库增量较大，但还要比较官方train |
| raw key不在官方train | 1,397个，6,391谱 | 不能把这些全部称官方新身份 |
| raw key同时不在AB与train | 115族 | 此115族已做额外官方身份解析 |
| 该115族的精确官方核查 | 115个身份、1,365谱均不在AB或train | 1,364谱来自MassBank、1谱GNPS2；仅此有界子集的确认数 |

最后一项没有按完整分子式做排除。先用安全的重原子组成确定所有可能的AB/train竞争SMILES，精确处理10,351个字符串，覆盖277,566个训练SMILES/raw-key对目录及完整AB来源的相关组成。目标125个SMILES归为115个官方身份；87个目标谱的发布者key与评分身份不同。不能因此假设整个C库都已做了官方身份全集去重，全集官方净增可能更大，当前没有声称。

依据：[元数据](../extlib2_increment_20261114/metadata_audit.json)、[有界官方身份审计](../extlib2_increment_20261114/bounded_official_identity_audit.json)。

## 谱内容去重边界

官方train的2,539,608谱已全量流式扫描。

| C谱与来源匹配 | float32严格归一内容签名 | 定量化签名 |
| --- | ---: | ---: |
| 原AB | 291 | 12,710 |
| 官方train | 72,942 | 178,516 |
| 两者均未匹配 | 417,677 | 307,122 |

严格签名含同mode、float32 precursor、排序m/z及max-normalized强度；定量化签名取top128，m/z到1e-4Da、强度到1e-5、precursor到1e-3Da。原B保留实际部署的合成±H precursor语义。**未命中不是独立新采集证明**：不同清洗、截峰、精度和precursor处理都可改变签名；相等也只证明这些表示相同。[全谱结果](../extlib2_increment_20261114/spectrum_overlap_complete.json)。

## 真参考存在与缺失时，固定升首的行为不同

复用旧48题缓存候选及谱，固定原AB数学、.8余弦/4匹配峰/.015Da碎片窗/10ppm+.002Da前体窗，C只做gap-fill。所有源的真实匹配表先冻结，之后才读评价标签。以下是组件诊断，非精确.488候选、非干净CV、非隐藏榜分。

| 控制 | AB MRR@25 | AB+C | 增量 | 改善/下降 |
| --- | ---: | ---: | ---: | --- |
| 参考保留 | .887153 | .901042 | +.013889 | 1/0 |
| 在AB与C均删除目标全部官方身份参考 | .833085 | .791419 | -.041667 | 0/4 |

参考保留时C有33个≥.8最高匹配，32真/1错，33个身份都已在原候选中，22个被既有保护挡住；唯一改善是旧候选第三名升首，不是新增正确候选召回。真参考删除时C有10个≥.8错误最高匹配，9个错同式；4次实际改序全部下降，其中1个错误身份原候选中不存在。

限制：此前cached pipeline library_max没有随删除控制重建；所以这不是整个生产栈的class2消融。诊断promotion对官方同身份别名保留原生SMILES，是两臂共同适配，不是原.488 raw-SMILES guard的逐行精确复刻。两题真实生产中间件另做组件检查，因原pipeline≥.9保护均零变化，不计算收益。旧48控制实际保序去重改变0行，此前“有大量重复”的目测判断作废。

依据：[真实匹配与审计](../extlib2_matching_20261114/verification.json)、[事件归因](../extlib2_matching_20261114/evidence_summary.json)。

## 可复用证据与下一步

- 已有`runs/extlib2_matching_20261114_v2/candidate_library_features.parquet`：1,250行，A/B/C实际候选证据，未知评分保留NaN及has_observed_score，不含truth标签。它是旧诊断/两题组件材料，**不能拿MIST17题拟合新门控**。
- 新增独立C-only门控训练pilot：从官方train选500个结构、优先enveda-180/timsTOF、每结构最多3谱；排除全部冻结验证身份及MSG训练/验证/测试raw key，400/100按官方结构分组预先固定。同一query两参考条件必须同split；reference arm、真身份和标签均不得作输入特征。先生成真实匹配特征，模型训练与500步测速由主控独立执行。数据及验证完成状态见同目录`gate_pilot_verification.json`，未完成时不称已训练。
- C没有reference spectrum_id，使用精确/定量化谱内容屏蔽query重复，不能伪称完成reference-ID去重。官方train也没有spectrum_id，新query标识仅由真实source_row稳定生成，不冒充原采集ID。
- 不直接把新C的高cosine提议强制升首。潜在收益来自实际新增参考或不同测量条件，以及学会区分真参考与同式相似错误参考；当前固定gap-fill的负控制已反证“高cosine必然可信”。

## 新500分子门控数据已实际完成

最终数据目录为`runs/extlib_gate_pilot_20261115_r2/`，不是首轮失败目录。500个query结构全部来自enveda-180/timsTOF，固定seed 20261115，从33,480个满足raw排除条件的结构池中预先选择。排除全部现有冻结panel的raw家族与官方身份，以及MSG train/val/test raw key；并检查所选官方身份不与上述key相等。未知MSG tautomer别名仍可能存在，这不是普遍无曝光证明。

- 500个官方身份分为400训练/100开发，先固定split再计算匹配。
- 1,461条谱，每结构最多3条；两参考条件共1,000条候选提议记录。
- 实际计算104,256个余弦谱对，保留58,735个至少4峰匹配事件。
- 训练参考存在条件381/400提议正确，开发参考存在94/100；参考完全移除条件训练0/400、开发0/100提议正确（条件定义所致，不是预测成绩）。
- 14个数值/布尔特征独立保存，标签、真身份、参考条件、split都不进入模型输入。缺失分数保留NaN，另有has_match。
- 源query仅写官方12谱列，source_row映射单独保存；没有抽取最终锁定panel的任何查询谱。
- 内容绑定检查：组内重复谱0，训练/开发精确或定量化谱签名交叉0，官方query身份交叉0，1,000个row_id唯一且特征/标签/元数据逐行对齐。
- 全部生成耗时91.3秒，峰RSS约1,013MiB；没有在本脚本中训练模型或提交。

模型训练读取约定：

| 文件 | 内容 |
| --- | --- |
| `features.parquet` | row_id及14个明确特征，详见feature_schema.json |
| `labels.parquet` | row_id、label、has_recalled_truth（后二者均属标签侧，非输入） |
| `row_metadata.parquet` | row_id、molecule_id、official_query_identity、reference_condition、split、proposed_identity、reference_row |
| `selection.json` | 选样与所有排除项指纹，400/100官方身份分组；在匹配前固定 |
| `match_events.jsonl` | 实际谱对证据，未含正确/错误标签 |

依据：[数据生成审计](gate_pilot_verification.json)、[独立绑定检查](gate_pilot_learning_data_review.json)。主控可用固定500步训练测速，不能使用旧48或17题重调参数。

## 旧48题独立门控留出输入已冻结

`runs/extlib_gate_holdout48_20261115_r2/`含96行、48query两条件；从既有C匹配表重组，未重新匹配、未训练。使用与上述500分子完全相同的14特征函数；96个最高参考身份全部复现原固定C matcher。500分子的官方训练/开发身份与48题无交集。标签单独保存，后续必须先冻结模型输出再读留出标签评价。

此处为参考缺失条件构造而使用旧官方身份删除目标参考，这是显式控制，不是模型输入。条件名称`all_true_identity_references_absent`对应旧结果`all_truth_references_absent`。原pipeline cached library_max仍保留；旧48还存在其他基座预训练曝光，因此仍不称精确.488干净CV。另需注意：训练每query最多3谱，而旧48/隐藏可能更多，`query_spectra`数值会发生外推；不能因个别留出改善就省略这项部署边界。

依据：[留出特征绑定](gate_holdout48_verification.json)。旧1250候选特征依旧留原路径；没有拿这些旧开发题拟合新门控。

## 预先固定与训练一致的C查询最多3谱

主控在读取新留出结果前，固定部署C门控最多取3条查询谱，与500分子训练一致。新增`runs/extlib_gate_holdout48_20261115_r3/`为主留出输入；r2全谱仅保留为诊断，不用于择优比较。每题以训练同一`sha256(seed|spectrum_id|source_row)`排序后取前3，选择先于参考存在/缺失条件且不使用标签；240条原查询谱均可从已冻结`train_row_`标识恢复真实source_row，无回退规则被使用。实际保留111条、丢弃129条，缓存C事件由12,344条过滤为6,105条，没有重新计算余弦、拟合模型或搜索阈值。

该96行输入仍使用同一14特征函数，500分子与48题官方身份不交叉，9项检查全部通过。完整选择清单在r3的`query_selection.json`。比较固定cosine≥.8和已训练概率≥.9时，两者必须使用同一个最多3谱的C最高身份；原AB与pipeline保护上下文保持原全谱。筛谱可能改变C最高身份，因此不能拿r3模型与r2全谱固定门槛比较。此生成脚本没有计算r3标签成绩，后续应先冻结模型输出，再单独评价。[最多3谱绑定](gate_holdout48_capped_verification.json)。

来源公开下载、构建日志、文件大小与SHA均保留；上游为GNPS2、MassBank、MSnLib，`MassBank_NISTformat.msp`是MassBank的MSP格式文件名，不代表下载了专有NIST库。Kaggle标签为Other且说明为空，本报告仅记录来源事实，不额外授予许可或宣称完整再分发审计已完成。

失败及资源记录原样保留：旧首次列名预检、B峰列表内存降至Arrow流式处理、当前pilot首轮列名不符等均有独立日志。没有云端写入、正式提交、新榜分或旧produre重跑。源结果SHA及完成检查汇总：[completed_audit_summary.json](completed_audit_summary.json)。
