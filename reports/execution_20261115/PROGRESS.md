# 新实测谱、MIST与证据学习：11/15执行记录

状态：增量及真实推理已执行，MIST近常量输出排查中；新证据门控的独立训练pilot准备中。冠军仍58156482/.488，没有新高或新正式提交。所有路径在D，旧冻结提交、模型及produre1/2原件未改。

## 原榜分先结清

11/14五次均COMPLETE且无error：trained prefix1 58334939=.470；mean prefix1 58341597=.470；GL early 58335002=.481；dual 58335047=.449；旧AB多谱共识58341606=.488。当前这些固定策略均未超过冠军，不继续扫系数。新的extlib2资产与旧AB多谱共识不是同一数据源，不能用旧.488替代新C的验证。[官方绑定读回](prior_batch_bound_reverification.json)。

## Extlib2增量已实际核查

对照为生产A200724谱、B物理139744谱经生产过滤后124160谱，以及官方train的2539608谱/275810发布者raw结构键。C为490840谱/62782发布者raw键。

- raw-key口径：C缺AB的49408个键，缺train的1397个键，缺AB与train并集的115个键。raw键不等于官方tautomer身份。
- 对这115个raw新键做安全重原子组成预筛、官方RDKit2026.03.3身份核验后，确认115个官方身份、1365条谱不在现有AB与train；这只给该子集下界，不是全C新身份总数。全train窄列已扫描，相关10351个SMILES做了精确身份，不重算22万全表。[有界身份审计](../extlib2_increment_20261114/bounded_official_identity_audit.json)。
- 全train与AB谱哈希已扫描：C有72942行与train严格签名相同、178516行量化签名相同；量化签名未出现在AB/train并集的307122行可能受清洗、峰截断及精度影响，**不能称30万条独立新采集谱**。[完整谱重叠](../extlib2_increment_20261114/spectrum_overlap_complete.json)。

## 新库实际匹配的固定对照

复用旧48题，原AB相似度/质量窗/峰数门槛固定，先冻结A/B/C真实匹配表，再读标签评价。新C源使用真实记录precursor与mode。共同对照按官方身份保序去重，但实际0行变化；诊断升首按官方身份提升原生已有候选，有别于冠军原raw-SMILES整条拒绝保护，所以不是精确.488复现。

| 参考条件 | AB MRR@25 | AB+C MRR@25 | 增量 | C实际变化 |
| --- | ---: | ---: | ---: | --- |
| 参考存在 | .887153 | .901042 | +.013889 | 1题改善 |
| 从AB/C全部移除真结构官方身份参考 | .833085 | .791419 | -.041667 | 4题全下降 |

真参考移除后10个C高余弦错命中中9个同式。原pipeline置信度缓存未按该参考条件重新跑，旧模型也有已知预训练曝光；这里只是新的库组件条件对照，不是全栈Class2或隐藏增益。两题生产中间数据组件因原保护0.9输出不变。[实际匹配和原值](../extlib2_matching_20261114/verification.json)。

决策：不把+.013889单独摘出来当收益，不直接部署C固定强制升首；保留C多谱/多参考分数和缺失标识，改学匹配可信度。新训练必须使用独立结构样本，不用这48题反复拟合。

## MIST已经实际运行

官方MSG real-only checkpoint289222619B，SHA`6f8df582df36aa4a984f120efee14ee0a62f3a7723caa770b856a6e704236727`与MD5均通过。原代码commit`48e339be6535546c87ba4f6b81a0f787c2e4ac40`未修改，CASMI薄适配器复用原公式分配函数，明确候选公式条件化、正离子词表、4096位Morgan2及负离子精确fallback。没有把CASMI缓存伪装MSG。

- 两题/20谱：22个条件输入，44/50候选有分，72,296,996参数严格EMA加载，前向约4.37秒，GPU分配峰约293MB；不算MRR。[真实组件](../../runs/mist_casmi_20261114/verification.json)。
- 官方MSG小缓存身份核查：现有48题30题有已知train/val曝光，18题无已知train/val键，17题不在任何MSG已知raw别名家族。这不是全局无曝光证明；选定17题全为cross面板。[曝光范围](../mist_evaluation_20261114/active48_exposure.json)。
- 固定17题/425候选：73谱构造103条件输入，387候选有分；未读标签完成预测后才独立评价。控制MRR=.656162，MIST=.095962，0首选、15题下降，不能部署。[固定策略评价](../mist_evaluation_20261114/fixed_policy_evaluation.json)。

## MIST严重负向的实质原因仍在定位

新审计发现，103个CASMI条件输入和16个不同官方MSG验证输入均输出几乎同一个指纹，逐bit跨输入标准差约1e-9至1e-8。425个候选指纹与官方packed/unpacked定义逐项相同，输出sigmoid与soft-Tanimoto方向相同；原生验证的真FP与打乱FP平均相似度相同。85个权重张量有限且无整张全零。故不是“正常新基座略差”，而是当前权重/官方实现组合没有产生输入相关信号，需要定位激活在哪层丢失。

103个CASMI特征逐条与当前官方PeakFormula（同一重建树）比对，公式/离子/强度/CLS/长度/仪器/padding精确一致；仪器embedding在本checkpoint关闭，不能用timsTOF未知类别解释此次常量。MSG缓存float16量化差异仅约2.4e-4。[张量契约](../mist_contract_audit_20261115/feature_tensor_parity.json)、[原生输入和FP审计](../mist_fingerprint_audit_20261115/verification.json)。

层内定位已完成：原生16条验证输入的stem CLS差异标准差约.02258，attention0=.16169、attention1=.01302、attention2=5.69e-5、attention3=3.03e-9，pool仍3.03e-9，最后输出5.51e-10。差异在encoder末两层已经消失；decoder接收近常量表示。不能归咎于soft-Tanimoto或CASMI专属输入，也不因此断言所有MIST方法无效。[最终合同审计](../mist_contract_audit_20261115/verification.json)、[层激活](../mist_contract_audit_20261115/layer_contraction.json)。

决策：该冻结checkpoint＋官方源码组合未通过输入相关性准入，暂停生产接入及重排，不通过调系数掩盖问题。不改旧预测、分数或验证文件；运行通过与数值有限只保留为执行证据，不能称“已得到有效新特征”。新模型接入增加输入敏感性检查。官方来源/许可不等于性能或实现正确。

## 正在推进的独立训练pilot

准备新的官方训练结构样本，优先timsTOF/enveda-180，排除所有冻结验证身份和MSG已知身份；每个结构最多3谱，真实C匹配下构造参考存在/同真身份全部移除两种条件。先按官方结构分组划分训练/开发，再生成分数；arm、真值、结构身份及分组信息不进特征，旧48和MIST17只作已冻结外部诊断。先500步测速，报告固定门槛下正确/错误升首与覆盖，而不凭训练loss宣称榜分。

独立pilot已在评分前冻结500个timsTOF/enveda-180结构、400训练/100开发，目标最多3谱/结构。训练只用显式14个数值谱匹配特征及缺失标识，标签、参考条件、结构ID与split分开保存。初始构建在读C参考spectrum_id时失败（实际C只提供name，官方train也无原生spectrum_id）；首败日志和目录保留，revision2显式以train_row_<source_row>仅作查询来源标识，参考侧按内容签名去重，不伪称存在原始谱ID。[训练数据目录](../../runs/extlib_gate_pilot_20261115_r2/)、[数据构建脚本](../../scripts/build_extlib_gate_pilot_20261115.py)。

500步训练器已写入并预先固定seed20261115、CPU小MLP16隐藏单元、AdamW、最后一步权重、训练集均值/标准差及缺失标志，开发标签不选checkpoint/门槛。前瞻门槛p≥.9，其余门槛仅描述。只有训练数据验证通过后才启动，当前尚未开始新训练；不把数据准备写成训练结果。目标是匹配正确性门控，不是完整候选排序或隐藏MRR。[训练器](../../scripts/train_extlib_gate_pilot_20261115.py)。
