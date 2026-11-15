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

来源公开下载、构建日志、文件大小与SHA均保留；上游为GNPS2、MassBank、MSnLib，`MassBank_NISTformat.msp`是MassBank的MSP格式文件名，不代表下载了专有NIST库。Kaggle标签为Other且说明为空，本报告仅记录来源事实，不额外授予许可或宣称完整再分发审计已完成。

失败及资源记录原样保留：旧首次列名预检、B峰列表内存降至Arrow流式处理、当前pilot首轮列名不符等均有独立日志。没有云端写入、正式提交、新榜分或旧produre重跑。源结果SHA及完成检查汇总：[completed_audit_summary.json](completed_audit_summary.json)。
