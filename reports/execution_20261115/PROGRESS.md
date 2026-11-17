# 新实测谱、MIST与证据学习：11/15执行记录

状态：Extlib2增量/匹配、MIST实际推理与失效定位、500步门控训练及固定留出评价均完成；当前接法未获生产准入。转向精确冠军错误分解与独立模型小试。冠军仍58156482/.488，没有新高或新正式提交。所有路径在D，旧冻结提交、模型及produre1/2原件未改。

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

## MIST严重负向的实质原因已定位到表示收缩

新审计发现，103个CASMI条件输入和16个不同官方MSG验证输入均输出几乎同一个指纹，逐bit跨输入标准差约1e-9至1e-8。425个候选指纹与官方packed/unpacked定义逐项相同，输出sigmoid与soft-Tanimoto方向相同；原生验证的真FP与打乱FP平均相似度相同。85个权重张量有限且无整张全零。故不是“正常新基座略差”，而是当前权重/官方实现组合没有产生输入相关信号，需要定位激活在哪层丢失。

103个CASMI特征逐条与当前官方PeakFormula（同一重建树）比对，公式/离子/强度/CLS/长度/仪器/padding精确一致；仪器embedding在本checkpoint关闭，不能用timsTOF未知类别解释此次常量。MSG缓存float16量化差异仅约2.4e-4。[张量契约](../mist_contract_audit_20261115/feature_tensor_parity.json)、[原生输入和FP审计](../mist_fingerprint_audit_20261115/verification.json)。

层内定位已完成：原生16条验证输入的stem CLS差异标准差约.02258，attention0=.16169、attention1=.01302、attention2=5.69e-5、attention3=3.03e-9，pool仍3.03e-9，最后输出5.51e-10。差异在encoder末两层已经消失；decoder接收近常量表示。不能归咎于soft-Tanimoto或CASMI专属输入，也不因此断言所有MIST方法无效。[最终合同审计](../mist_contract_audit_20261115/verification.json)、[层激活](../mist_contract_audit_20261115/layer_contraction.json)。

决策：该冻结checkpoint＋官方源码组合未通过输入相关性准入，暂停生产接入及重排，不通过调系数掩盖问题。不改旧预测、分数或验证文件；运行通过与数值有限只保留为执行证据，不能称“已得到有效新特征”。新模型接入增加输入敏感性检查。官方来源/许可不等于性能或实现正确。

## 已完成的独立训练pilot

准备新的官方训练结构样本，优先timsTOF/enveda-180，排除所有冻结验证身份和MSG已知身份；每个结构最多3谱，真实C匹配下构造参考存在/同真身份全部移除两种条件。先按官方结构分组划分训练/开发，再生成分数；arm、真值、结构身份及分组信息不进特征，旧48和MIST17只作已冻结外部诊断。先500步测速，报告固定门槛下正确/错误升首与覆盖，而不凭训练loss宣称榜分。

独立pilot已在评分前冻结500个timsTOF/enveda-180结构、400训练/100开发，目标最多3谱/结构。训练只用显式14个数值谱匹配特征及缺失标识，标签、参考条件、结构ID与split分开保存。初始构建在读C参考spectrum_id时失败（实际C只提供name，官方train也无原生spectrum_id）；首败日志和目录保留，revision2显式以train_row_<source_row>仅作查询来源标识，参考侧按内容签名去重，不伪称存在原始谱ID。[训练数据目录](../../runs/extlib_gate_pilot_20261115_r2/)、[数据构建脚本](../../scripts/build_extlib_gate_pilot_20261115.py)。

500步训练实际完成，CPU参数更新1.459秒。预先固定seed20261115、MLP16隐藏单元、AdamW、最后一步权重、训练集均值/标准差及缺失标志；开发标签不选checkpoint/门槛。固定p≥.9的开发200条件行接受76条（74正确、2错误），原cos≥.8接受85条（81正确、4错误）。精度改善伴随正确覆盖下降，不是排序增益。模型`runs/extlib_gate_train_20261115/last_step_500.pt`，SHA`a9ecb106c26ac2ad61751697211e36def439ea05a4fea0bc5c6203f45e752a2b`。[训练结果](../extlib_gate_train_20261115/verification.json)、[独立审查](../extlib_gate_peer_review_20261115/verification.json)。

## 冻结模型的48题组件留出结果

旧48题与训练500结构按官方身份不交叉。评价前先固定C每题最多3谱以匹配训练输入范围，按相同seed/hash选取240→111谱，原AB/置信度保留全部谱；cos≥.8和p≥.9均使用同一限谱C候选。模型预测先保存，之后才读truth评价，没有选门槛或续训。r2不限谱版只作诊断。[限谱核验](../extlib2_execution_20261115/gate_holdout48_capped_verification.json)。

| 参考条件 | AB | C固定cos≥.8 | C学习门控p≥.9 | 门控相对AB |
| --- | ---: | ---: | ---: | ---: |
| 参考存在 | .887153 | .901042 | .901042 | +.013889 |
| 全部真身份参考移除 | .833085 | .791419 | .812252 | -.020833 |

参考存在时门控接受7条全正确、1题实际改善；固定cos接受11条全正确。参考移除时门控仍接受4条错误提议、2题下降；固定cos接受5条错误提议。门控减少部分危害，但未消除无真参考时的负效应，暂不接入冠军、不增加训练步数或用旧48扫阈值。仍是旧候选/旧置信度的组件诊断，不是完整冠军或隐藏分类成绩。[完整评价及逐例](../extlib_gate_holdout48_20261115/verification.json)。

评价首次绑定检查误把`truth_control_metadata_sha256`当context哈希，标签读取前即拒绝；核实实际绑定truth.csv后，对r3全部输入、C匹配及元数据和context分别绑定再完成评价。没有改变模型/阈值。

## 下一阶段：减少旧证据的反复重排

用户要求重心转向新能力，不继续现有分数系数/门槛扫描。P0只补精确.488缺失的生产阶段归因：复用冻结查询，记录原候选、生成、过滤截断、中间名单及MASS/head/AB最终名次；Class1/2/3显式隔离参考与静态结构，保留原模型和生成6/150。先一题真实初始化到CSV核验，不重做produre1/2，不使用锁定最终面板。1题8谱输入已准备，**准备不等于完成运行**。[面板契约](../champion_error_decomposition_20261115/panel_contract_review.md)。

FIORA-OS v1独立MSnLib v7开放训练权重53814639B已取得，SHA`83221e187991f116a8aed1bf272dd656cf31721a177dcbb0239f414c8df31a0e`；依赖单独放D盘target。实际CPU小试成功：67/67严格加载、13447861参数；同式位置异构体各11峰，最大raw差异.125625，两次前向/出峰.594/.0136秒，首次导入100.7秒。仅组件通过，无排序/榜分。旧48的240谱无明确HCD，不能直接作原生域内评价，正在核实timsTOF显式迁移方案。冠军已有ICEBERG/GLACIER，互补待测。SpecTUS因EI域/NIST来源不选；DiffMS尚未大下载，编码器需先输入相关性准入。[真实小试](../new_paradigm_20261115/README.md)、[可行性](../new_paradigm_20261115/FEASIBILITY.md)。

精确冠军Class2首轮E2未产出JSON，原源码吞异常继续fallback。已停止该不完整运行，保留执行快照/日志/operator_stop。同时间内核OOM杀约6.18GB匿名内存Python并耗尽swap；PID命名空间映射按高置信关联记录，未倒填未知退出码。[故障诊断](../champion_error_decomposition_20261115/canary_class2_oom_diagnosis.md)。r2单独目录重新初始化，E2 workers=1、复用原资源释放helper、保存真实子进程returncode并failfast；**r2运行中，不是完整成功**。[r2日志](../../runs/champion_error_decomposition_20261115/canary_class2_r2/full_run.log)。索引路径数因hardlink视图增长，不是独立模型数增长。
