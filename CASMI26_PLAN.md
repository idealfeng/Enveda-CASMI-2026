# CASMI26 冲银牌作战计划

2026-11-09 15:37（北京时间）执行更新：今日5个不同机制分支的源码/权重/配方已冻结且通过本地实际推理与独审。**58155921（前3保护）、58155938（原v2mean消融）已正式接受/PENDING**；新同式head和Alex外库复现的云V1排队，原0.482仅追加外库版等待空槽。后台按最多2个未完成云运行自动核验并单次提交剩余分支；当前仍最佳0.482，无新榜分。只读查分同步将新个人最佳写入提升记录，30项隔离检查通过。提交调度/记录更新需要本机运行；已接受的Kaggle评分可独立继续。[最新状态](reports/optimization_20261109/latest_status.json)、[调度状态](reports/optimization_20261109/batch_dispatcher_status.json)、[本批说明](reports/OPTIMIZATION_BATCH_2026-11-09.md)。

2026-11-09 15:08（北京时间）官方 API 已确认 **58129661 / guarded head tail 1108 V1 = 0.482、COMPLETE、无错误**，超过旧 MASS 0.481；今天 0/5 已用，5 次可用。新默认锚点为该固定版本。提升改动是原 MASS 完整运行后，固定前 7 名，仅用 v2 双 head 对第 8–25 名同式候选原槽位重排；尚未拆分训练增量与晚接入原 v2 的收益。用户要求每次提升记录来源，统一维护 [提升记录](reports/IMPROVEMENT_LEDGER.md) 与 [机器可读记录](reports/improvement_ledger.json)。今日范围对照、新同式残差目标训练和近期公开方案核查并行；未核实的新标题分数不能当复现结果。

2026-11-08 21:17（北京时间）实战更新：本轮四条正式结果为NP加分消融 **0.481**、Na分支 **运行错误/无分**、新训练head seed0 **0.465**、seed1 **0.470**。当前最佳仍0.481；停止将当前head全量接入主排序及其全量集成。最后一次额度改为原MASS完整基座之后的**前7名完全固定、只在8–25同formula原槽位排序**，新target `stormseye/casmi26-mass-guarded-head-tail-1108` 已创建但可见运行仍QUEUED、尚未正式提交。真实3query晚接入模型CLI已跑通并确认prefix/候选不变，24项功能/观察器与7项源码门检通过。固定源单次提交dispatcher已启动（实际PID44920）等待可见COMPLETE后核验并单次code-submit，最多6h；只读评分watcher实际PID42336，最多12h，均已核对命令行身份。[最新状态](reports/optimization_20261108/latest_status.json)、[第五条调度](reports/optimization_20261108/mass_guarded_head_tail_1108/ready_dispatch_status.json)、[本轮记录](reports/OPTIMIZATION_BATCH_2026-11-08.md)。排队期间保持本地任务运行才能自动交最后一条，前四条已接受的评分不依赖本地。

2026-11-08 更新：11/7下午五版全部COMPLETE：V35原版 **0.469**、弱先验 **0.476**、v2加权 **0.458**、稳健质量 **0.469**、取消outside强插 **0.469**。本批没有超过旧MASS **0.481**，停止以V35作为研发默认底座。官方讨论区已读回151条主题目录、21篇重点正文及评论，快照在`reports/discussion_review_20261108/`。新的主投入是**真实检索困难异构体驱动的候选条件多谱匹配头**，外库增量并行；不每天重复交基线，不为用满5次提交轻微变体。覆盖审计发现原48的9个候选内错首选真结构已有GL+ICE分，不能把补覆盖当主要涨分依据；Na补评分canary另12query/1030候选已102.74秒跑通，无重排/新MRR/提交。新开源Majyles流水线作者自报0.313，已只取110995字节源码至D，借鉴验证设计，未作为更高基线复现。详见[讨论与决策](reports/DISCUSSION_RESEARCH_2026-11-08.md)。

2026-11-07 算法主线调整：用户希望一个月内按系统路线推进。以已得0.481的部署版本保底，主要研发转为**可信验证＋按查询条件融合＋实际检索错误驱动的困难负例匹配头**，外部参考增量并行；编码器末层微调在小头有证据后开展，不把扩大模型和固定权重扫参当默认路线。原48查询存在预训练曝光，新增head分组不能消除该边界；独立小组件验证与全栈诊断分开。详见[四周算法路线](reports/MONTH_ALGORITHM_ROADMAP_2026-11-07.md)。今天五条提交继续只读查分，当前没有新训练任务被启动。

2026-11-07 14:58（北京时间）最新状态：官方确认上一批dual **0.480**、tri **0.475**、MASS **0.481**、激进RR **0.436**；截图131名为用户观察。保留0.481，停止当前v4/强RR配方。下午搜索发现新Gold Apex **V35**有实质代码变化，但未核实更高公开真实分数；已正式提交新基线及四项优化共5条：58082815原V35、58082822弱先验、58082871 v2权重.75、58082895跨谱中性质量中位数、58082938关闭4槽outside强插。五条均PENDING、无新分，今日额度5次已用完。新只读监控已核对进程24376，每45秒查分；[最新状态](reports/aggressive_batch_20261107_pm/latest_status.json)、[本轮配方与检查](reports/AGGRESSIVE_BATCH_2026-11-07_PM.md)、[提升归因](reports/ROUND2_ATTRIBUTION_2026-11-07.md)。下一条独立路线是审计Enveda-180通用外部参考谱增量，不将公开目录数量当隐藏覆盖。

2026-11-07 00:48（北京时间）最新执行：原V56已确认Public **0.479**；上轮完整tri V30实分 **0.475**，未提升。按用户新的积极冲分授权，当前4次可用额度已全部用于四条不同V1代码提交：V56双模型58063780、V56三模型58063822、公开MASS复现58063883、允许异构体首选变化的V56激进RR58063870。四条当前均 **PENDING，无新分数**，旧0.479保留。可见运行采用明确标注的fast_static，不称新模型可见全流程已完成；真实全量由Kaggle隐藏重跑。公开V32与Roman代码重复，未浪费额度分别提交。[批次记录](reports/AGGRESSIVE_BATCH_2026-11-07.md)、[最新查分](reports/aggressive_batch_20261107/latest_status.json)。下一步按四条真实榜分选择主线，EXP003特征支线保留，本轮不再局限保护首选的小幅尾部调整。

2026-11-06 EXP003最新状态：完整45查询/3679候选的GL逐谱证据已导出，178秒完成，12187条评分无缺失；[完整独立核验](reports/EXP003_GL_TRACE_FULL_2026-11-06.md)30/30通过，聚合输出与旧缓存逐字节相同。[跨CE候选支持率定义](reports/EXP003_FEATURE_DESIGN_2026-11-06.md)冻结后，首次纯特征导出有14查询/34同式组可用，其中7组支持率winner与原均值winner集合不同。这只说明新增信息存在；还没有排序效果评价。下一步恢复原阶段排名/公式sidecar、核对严格可动槽位，再执行固定候选C/T对照，不扫权重或扩库。新正式提交58051406仍PENDING，榜分沿用已确认0.479。

2026-11-06 16:22（北京时间）最新状态：新三模型公开配方可见试跑COMPLETE，运行产物核验41/41通过；已正式提交 **58051406**，固定云端Notebook `stormseye/casmi26-public-tri-v30` V1，当前 **PENDING / 暂无新Public分数**。只读后台每45秒查询，见[新提交状态](reports/public_tri_v30_submission_status_20261106.json)。原始Flex V56仍为COMPLETE/0.479。可见试跑只有12实际查询，隐藏全量由正式代码提交重跑，不能混淆。详见[完整复现记录](reports/PUBLIC_TRI_V30_REPRODUCTION_2026-11-06.md)。EXP003逐谱记录canary已独立核验30/30通过，下一步在原45查询/3679候选上导出逐谱证据，不重训或扩库。

2026-11-06 16:13（北京时间）执行更新：原始Flex V56首次正式提交58021256已由官方API确认 **COMPLETE / Public 0.479**。新公开三模型的[固定候选实验EXP004](reports/EXP004_PUBLIC_NEURAL_2026-11-06.md)完成：48查询CUSTOM层MRR 0.845106→0.850955，3例改善、0例回退，首选均不变；这是有预训练曝光的诊断，收益集中在少数样本，不能加到榜分上。完整Gold Apex V30公开配方已创建为[私有离线Notebook V1](https://www.kaggle.com/code/stormseye/casmi26-public-tri-v30)，当前RUNNING，尚未正式提交这条新分支，也没有新榜分。其完整配方还改变NP先验、leader规则及LOTUS，须与单因素实验分开记录。后续先核验三模型真实覆盖、混合分数及CSV，再正式提交；所有资产及产物仍在D盘。

2026-11-06近期公开方案复查：官方API已确认我们首提COMPLETE/0.479。官方高分/近期列表各100条发现新地址Roman V17、Helios V2、Gold Apex V30和Pablo V4，不能再根据搜索索引遗漏认定没有更新。[完整审查](reports/RECENT_PUBLIC_BASELINES_2026-11-06.md)区分0.480官方页面记录、0.481作者个人best、0.482标题与具体版本证据。bgunshui v2/v4现已公开，两checkpoint合计约29MB已在D盘，完整性16/16及严格加载/两谱CPU前向通过；尚未复现新基线得分。优先在固定候选上比较新公开神经组件，再推进完整基线与EXP003；暂不扩充大谱库。

2026-11-06更新：用户确认原始Flex V56复现Public为0.479，约800名，当前银线参照约0.481/200名。已读回提交58021256的原始源码SHA绑定，没有本项目新算法混入；早先SSL故障已修复，官方API现已确认COMPLETE/0.479，榜位仍按用户观察记录，见[观察记录](reports/baseline_score_observation_20261106.json)。第一项低成本单因素实验已完成：固定48分子候选与首选，仅移除最终流行度项，MRR差−0.000684、区间跨零，无改善证据，不提交。见[EXP002](reports/EXP002_FINAL_PRIOR_2026-11-06.md)。源码窄审确认ICE/GL已经聚合CE/adduct分数，但forward重排接口尚未使用逐谱margin支持率/离散度；下一项[EXP003](experiments/EXP003_FORWARD_SPECTRUM_CONSISTENCY.md)先导出逐谱证据，再检验新增一致性信息。快速消融与干净自训小组件两线推进，不把从零重训全栈作为起点，也不承诺小改动线性累加到银牌。

调研日期：2026-11-04（北京时间）。目标：最终榜至少银牌，执行上争取前 3%，给最终榜波动留余量。用户从零开始，每周可投入 20 小时以上，可集中投入算力。下文实验顺序和资源分配是我们的计划，不是已经取得的成绩。

当前执行状态：**2026-11-04 三套公开方案的本地 12 分子全流程检查均已通过。** 与准确版本上游对照，首选均为 12/12 一致，部分后续排名有差异，尚未验证隐藏榜分。具体结果见 [REPRODUCTION.md](REPRODUCTION.md)。所有后续下载、环境、缓存和临时文件必须放在 D 盘项目目录。

2026-11-05进度：验证器已按官方metric V14校准，实际准备24个NP和24个跨库查询、240张谱，并冻结250个最终留出身份；参考隔离与Flex/V43诊断运行正在落实。审计已确认FPNet full1和Saner final_model有全训练数据曝光，本轮全栈结果必须标“隔离参考谱后的已知模型曝光诊断”，不能称独立泛化CV。首次提交的本地草稿见 [准备状态](reports/SUBMISSION_READINESS_2026-11-05.md)。

本次续跑：两套48分子全流程与审计已完成，V43 MRR0.8207、Flex基础排序0.8504、固定候选轻量Saner0.8573、Flex完整最终输出0.8389。完整方案首选44/48相同、共同漏同两例，互补有限；轻量Saner增量区间含零，且均有已知模型曝光，不据此改主线或推断榜分。另32分子的组件诊断0.7823→0.7998，只2例改善，负候选训练/开发接触仍有边界。锁定最终250未评估。详见 [本地验证](VALIDATION.md) 和 [两方案对照](reports/VALIDATION_COMPARISON_2026-11-05.md)。

首次正式提交（11月5日19:30，北京时间）：**提交58021256、云端Notebook V2，现已COMPLETE / Public 0.479。** [私有离线Notebook](https://www.kaggle.com/code/stormseye/casmi26-flex-v56-baseline)保持原始V56源码，T4×2上可见运行约21分钟完成。提交前29项门检查及19项独立复核通过；400行CSV合法，但可见试跑只计算12分子、388行占位，正式代码提交由Kaggle替换隐藏输入重跑。早期PENDING是历史状态，不能当作当前结果。详见 [提交状态](reports/SUBMISSION_READINESS_2026-11-05.md)。

下一阶段优先 [干净组件实验](reports/NEXT_CLEAN_EXPERIMENT_2026-11-05.md)：重新划分未查看的开发评估身份，从零训练小编码器和匹配头，排除正例、负候选、监控和预训练依赖中的目标身份。先500步测速，再冻结预算；本计划尚未训练，不预测锁定250。

## 1. 比赛事实和证据边界

- 报名、合队截止：北京时间 **2026-12-08 07:59**；最终截止：**2026-12-15 07:59**。
- 指标 MRR@25：每个分子第一条正确候选在第 r 位，得 1/r，否则得 0；每个分子最多 25 个 SMILES，以分号拼接。
- 匹配使用 **RDKit 2026.03.3** 的互变异构规范化及 InChIKey14。相同评分身份的立体异构体、等价互变异构体应去重。
- 必须通过离线 Kaggle Notebook 提交，CPU/GPU 时限均为 9 小时，输出 `submission.csv`。公开免费外部数据和预训练模型可以使用。

来源：[官方比赛说明](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/overview/evaluation)。

本赛标注授予积分和奖牌。1000 队以上，银牌门槛为最终前 5%，比例向下取整。**当前银牌分数线尚未核实**；搜索快照人数和历史榜分不能用于确定当前门槛。[官方奖牌规则](https://www.kaggle.com/progression/competitions)

可下载 `test.parquet` 是训练样本组成的占位输入，正式提交会替换成隐藏测试。Public LB 来自隐藏测试的一个子集，不是占位测试成绩。只把本地 test 用于接口、速度和稳定性检查，不据此判断真实泛化能力。[主持人澄清](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/741404)

官方数据说明：隐藏测试约 400 个分子、1500 张谱，均为 timsTOF，一个分子可以有多个能量、多个 adduct；三类分子为有公开谱、数据库有结构但无公开谱、数据库外新结构，比例保密。需要支持 10 种 adduct，不能从占位文件只有 7 种推断真实范围。输入不提供真实分子式。[Kaggle Input 页中的官方数据说明](https://www.kaggle.com/code/evgendvorkin/enveda-casmi-2026/input?scriptVersionId=350922451)

完整 Rules 页早期未取得可读正文。每天提交次数已于11/9由登录API确认今日剩余5次；最终选择数和队伍上限仍应核实。11/9补查发现，主办已于10/17取消非商业开源数据限制，CC-BY-NC/NC-SA外部数据可以使用；NIST及不可再分发衍生权重仍不允许。代码许可证不覆盖所有输入文件，应保留实际来源和许可。[主办许可更新](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/750330)、[NC-SA答复](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748363)。

## 2. 公开强方案：先复现，再改善

以下是检索到的页面记录，不是我们复现的成绩，也不是实时榜名次。Kaggle 动态页部分无法直接读取，分数主要来自原页搜索索引。不能从 Notebook 的金银铜图标推断比赛排名，它也可能是 Notebook 奖牌。

| 方案 | 核验到的公开成绩记录 | 用途 |
| --- | --- | --- |
| [Flexonafft: Closing the Evidence Gap](https://www.kaggle.com/code/flexonafft/casmi26-closing-the-evidence-gap) | 页面 V61：Public 0.473，Best **0.479 V56**；V61 运行 19m52s、T4×2 | V56、V61 源码及必要输入已固定到本地；优先复现 V56，不能把 Best 归给 V61 |
| [prvsiyan: Analog Propagation](https://www.kaggle.com/code/prvsiyan/analog-propagation-casmi-2026-baseline) | **0.456 V43**；27m25s、T4×2；16 个输入，代码 Apache-2.0 | 结构清楚的对照基线；输入含指纹模型、ranker 特征、PubChem popularity、PubChemLite 候选 |
| [Canqiang E006](https://www.kaggle.com/code/canqiang/casmi26-e006-window-40-ice-fallback-true) | 第三方复现记录为 **0.440 V1** | 查阅 ICEBERG/GLACIER 集成、版本隔离与部署；分数证据为下方独立复现记录 |

[Canqiang 复现记录](https://github.com/billylu24/Enveda-CASMI-2026---Molecule-ID-From-Mass-Spectra/blob/main/research/canqiang_e006_20261011/README.md)保留原代码单元和固定输入，并记录正式提交得分。另 [cubres 的 10 月 21 日历史记录](https://github.com/cubres/enveda-casmi-2026/blob/main/README.md)称 0.456 当时为 382/3744，说明强公开基线也不自动达到银牌；其 Gluzdov V16=0.464 等线索暂只按作者审计记录处理。

可读的[四通道实现](https://github.com/shiferaxa/casmi26)使用训练结构与 COCONUT 候选，按中性质量召回，再计算谱库熵相似度、analog 传播、断键解释、谱图到指纹分数，最后由 GBDT 排序。这是我们架构的参考，不能据此声称上述最新 V56 的内部实现完全相同。

## 3. 讨论给出的具体行动

1. **CV 与 LB 会背离。** [约 30 次提交的经验帖](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743254)指出天然产物小面板与大谱库代理各有偏差，候选常是同分子式异构体，连接关系证据更关键。我们保留两套验证，并单列同分子式排序。
2. **250 个同仪器结构有用，但不能反复调到过拟合。** [重实现实验日志](https://github.com/nghianguyen7171/casmi26/blob/main/docs/EXPERIMENT_LOG.md)记录仅用 np 内部 CV 选出的配置会掉榜分。我们采用留库验证、结构分组和独立最终留出集，不用一个加权 CV 数字拟合隐藏类别比例。
3. **生成命中不等于识别成功。** [生成讨论](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/750241)自报在适当父本下可生成 100/130 真结构，但最终 top1 仅 7/130；应分别测生成、过滤、排序的损失。[Class 3 讨论](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/751300)也报告代理改进难迁移。
4. **精密校正要先做对照。** [正离子约 0.5 mDa 偏移讨论](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743395)仍有隐藏数据处理版本未确认的问题；只在紧容差碎片匹配中测试，不直接全局改数据。

## 4. 我们的技术路线

`各分子的全部谱 → 清洗与 adduct/质量校验 → 候选召回 → 多证据打分 → 学习排序与置信度融合 → 评分身份去重 → 最多25候选`

优先级按投入产出安排：

- **P0：跑通强基线。** 冻结 Notebook 和输入数据版本、运行镜像，检查所有依赖可公开取得；首次正式得分作为锚点。V56 输入若缺失，先用 V43 建锚点，限时处理依赖问题。
- **P1：多谱融合、同分异构体排序。** 保留每张谱的模式、碰撞能量和质量；比较 max、top-k mean、质量加权。对同分子式候选增加连接结构证据，训练 LightGBM ranker，并避免损伤高置信谱库命中。
- **P1：有控制的候选扩充。** 先量候选召回和过滤损失，再比较 train+COCONUT、定向 PubChem/PubChemLite。扩大候选池也会加难负例，不能把候选数增多当作收益。
- **P2：互补神经网络与正向谱模型。** 小型 spectrum→fingerprint 多视图集成；只对 top-K 候选计算或缓存 ICEBERG/GLACIER 谱预测，比较其额外信息和耗时。[官方 ms-pred](https://github.com/coleygroup/ms-pred)提供实现，但不同训练数据对应的权重须分别检查可用性。
- **P3：新结构补缺。** 仅在前几项形成稳定收益后投入。比较结构多样化 analog 父本、有限反应枚举，必要时试 [DiffMS](https://github.com/coleygroup/DiffMS)。候选只在验证支持的置信区间插入，避免挤掉已有正确候选；测试不提供分子式，formula-conditioned 方法须包括分子式预测误差。

时间建议：约 60% 用于排序/融合/谱预测，25% 用于验证、复现和部署，15% 用于生成探索。根据失败分解调整；这不是固定的类别占比假设。

## 5. 验证设计与实验门槛

- 采用官方评分规范化后的结构身份分组。保留 `enveda-np-examples` 同仪器面板，同时从多个来源建立约 2000–5000 结构的大代理集；另冻结一份不参与日常选择的最终留出集。
- Class 1 场景允许参考库有同结构的独立实测谱，但排除查询本身、逐峰相同谱和相同采集的重复；不能用自匹配成绩当参考库能力。
- Class 2 场景从所有谱库移除目标身份，候选池保留真结构。自训指纹/谱预测模型也须按目标身份隔离；预训练模型的训练划分不明确时，标明其验证污染风险，不能把它当作干净独立验证。
- Class 3 proxy 从候选池移除真结构；干净的生成验证还须从训练谱、生成器/指纹/正向谱模型的训练样本、analog 父本和预缓存生成候选中排除该评分身份。无法审计公共预训练模型时，单列潜在污染结果，仅作管线诊断。删除一个已知分子仍不能模拟真正数据库外新分子的难度，不据此推断真实类别比例或得分上限。
- ranker 按查询分子分组，使用 OOF 特征或独立训练查询；做跨库留出。最终选择同时看同仪器面板和大代理，绝不随机拆谱图行。
- 每轮只变一个主要因素；同时记录全系统 MRR@25、top1、top5、top25、候选召回、真结构过滤保留率、同分子式子集、分层退化、时间/内存。对相同分子做 paired bootstrap，必要时重复种子。
- 将不确定的小提升保留为实验分支；有明确机制、多个验证集支持的变化才优先花正式提交机会。不要从少量公开榜变化反推隐藏答案或固定三类比例。
- 输出 ID 必须来自运行时的测试文件，不能硬编码占位的 400 个 ID，也不能拿公开 sample IDs 强制校验隐藏输入。支持全部 10 种 adduct、质量范围变化、空候选和缺失元数据；不用随意的固定 SMILES 掩盖整批预测失败。

每条实验记录保存：实验 ID、唯一改动、代码版本、数据/模型版本与来源、split、seed、候选召回、分层 MRR、paired 区间、耗时、显存、Notebook 版本、正式榜分、采纳结论。

源码对照后，首个排序实验定为 `VAL001_NEURAL_INCREMENT`：固定 Flex 基础候选集，对比基础排序和预先固定的 Saner 神经排序配置，再逐项测物理重排等层。三套公开管线高度共享模型与检索骨干，先量化错误相关性再考虑集成；12 个占位例子不能用于选冠军或调权重。同仪器 250 面板已被公共方案开发使用，删掉参考谱也无法消除预训练模型中的目标身份，须如实标记验证污染。详细组件表和实验步骤见 [组件对照与首个验证实验](reports/public_pipeline_components.md)。

## 6. 六周节奏与交付

| 时间（北京时间） | 工作 | 验收交付 |
| --- | --- | --- |
| 11/04–11/07 | 固定评分环境、完整读规则、查实时银线；获取强公开基线及输入 | 一次有效离线正式提交；基线配置和分数可追溯 |
| 11/08–11/14 | 建同仪器与跨库验证，拆解候选召回/排序失败，建立实验台账 | 冻结 splits；复现基线的全系统本地指标 |
| 11/15–11/24 | 多谱融合、同分子式排序、ranker、受控候选扩充 | 单因素消融表；择优正式提交；淘汰不迁移方案 |
| 11/25–12/04 | top-K ICEBERG/GLACIER、指纹互补集成；有余力再测生成 | 有互补性的候选版本；完整运行预算 |
| 12/05–12/11 | 稳定最终管线、冷启动离线重跑、最终留出验证 | 最终候选冻结；权重/数据版本清单；在规则允许时保留稳健和进取两个版本 |
| 12/12–12/14 | 检查可重现性、提交状态与最终选择，预留故障缓冲 | 在北京时间 12/15 07:59 前完成规则允许的最终选择 |

里程碑首先看有效提交和泛化证据。排名目标逐步推进到前 10%、前 5%，执行上争取前 3%；不预设 0.48 或 0.50 必然对应银牌。

## 7. 本地检查结果与下一步

已完成数据检查、下载和环境准备，正在复现公开方案；公开脚本启动时会拟合树排序器，尚未自行训练神经模型或提交：

- `train.parquet`：3,033,286,496 字节，**2,539,608 张谱**，原始 `inchikey14` **275,810** 个；此处尚未按评分流程重新规范化计数。
- `enveda-np-examples`：1184 张谱、250 个原始结构身份，可作为同仪器验证来源；必须跨库清除目标结构来模拟 Class 2。
- 占位 `test.parquet`：1213 张谱、400 个分子、7 种 adduct；这个分布不用于约束隐藏测试。
- GPU：RTX 4060 Laptop，约 8GB 显存。项目内已建立 WSL / Python 3.12.3、PyTorch 2.9.1+cu126 专用环境，CUDA 实际计算和 FPNet 实谱组件检查已通过。
- 主流程 RDKit 已固定为官方 **2026.03.3**；旧谱预测模型使用原方案的独立 RDKit 2025.03.6 环境。依赖、缓存和临时文件均在 D 盘。
- 原始文件保留。详细计数见 `reports/data_inventory_2026-11-04.json`。

三套方案的源码、必要输入和共享谱缓存已到本地，12 分子全流程均已通过。V43、E006 恢复运行分别 575.604、532.866 秒（复用 Engine 2）；Flex V56 完整运行 1597.724 秒（使用共享谱缓存）。三套首选与上游均相同，后续排序并非完全一致；这不是 400 分子完整推断或隐藏榜分复现。具体证据见 [REPRODUCTION.md](REPRODUCTION.md)。下一里程碑是按 `VAL001_NEURAL_INCREMENT` 建立独立验证、审计冲银所用资产，再准备有效离线提交。当前阶段无需先租大卡；4060 用于开发和小模型试验，只有验证出大显存需求后才安排付费算力。

## 8. 新增四份资源的采用决策

2026-11-04 已审查用户补充的四个链接；详见 [资源审查](reports/RESOURCE_REVIEW_2026-11-04.md)。轻量源码与回执均已保存到 D 盘，没有新增模型/数据下载或训练。

- **优先采用 shiferaxa 的验证/训练工程思路。** 固定提交源码快照已保存；复用特征导出、查询 mask、失败分解和自训 FPNet 配方，先统一官方评分身份、跨文件查询 group 与正确质量范围。其旧四通道骨干不作为第四个独立模型投票。
- **José EDA 只取可靠的数据分析方法。** V3 已归档；其中将 dummy test 当作 Public LB 的推论被 [主办澄清](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/741404)纠正，不能据此忽略榜分。统计计数与清洗阈值在当前数据重算。
- **743254 经验帖落实到实验设计。** 为 `VAL001_NEURAL_INCREMENT` 增加固定候选的同分子式硬负例子集；双验证、多 seed，冻结最终留出集。作者报告的98%、±0.007等不作为我们的普适常数。
- **Roman V8 保留源码，先不重复下载大资产。** 与现有 Flex 的冻结基线/helper/Saner pins 相同，新增线索是第二神经模型集成和 TAX 先验；当前标题/源码中的分数字样不等于经核实的当前榜分。先核查第二模型来源和静默回退，再单独验证新增信息。

- **evgendvorkin V27 已保存完整源码。** [归档与审查](third_party/evgendvorkin_enveda_casmi26/README.md)含原始Notebook、API元数据和内嵌引擎源码。它沿用多引擎骨干，新增重点是五折FPNet的PubChem集成和第24名的第六个PubChem位置；目前仅归档，不下载缺失的fold1–4权重，不把它作为独立第四模型或已复现成绩。
