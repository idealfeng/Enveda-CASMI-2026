## 2026-11-10：0.488确认、DeepSeek两组结果审阅与五次规划

- 官方API20:11（北京时间）确认昨日五条全COMPLETE/无错误：前3保护58155921=.482、v2mean58155938=.482、新同式残差58156404=.482、Alex公开配方58156414=.484、原.482仅加两库58156482=**.488**。**相对受控父版本.482，新增外库组件净增.006**；相对当时个人最佳.484再增.004。不能拆成单个库/训练收益。今日0次已用、5次可用。[线上快照](reports/optimization_20261110/initial_live_status.json)。提升记录及JSON已更新。
- 用户交付`produre1.md`/`produre1/`和`produre2.md`/`produre2/`，本轮只读独审和规划，未改用户原件、未创建今日Notebook或正式提交。报告在`reports/produre_review_20261110/`。
- produre1的48查询用旧Flex控制，遗漏正式official-IDguard，base自身还1条重复身份。B9条“正确提升”proposal均非法（8条新重复+1原base问题），不可据此断言MassBank是.488主贡献；模拟输出guard的诊断重算也不是正式helper复现分。200排除实验13个命中中2个仍是真官方身份。step7有14位身份查27位MassBank key、训练结构表当完整候选池的问题，431个新增身份未被证实。
- produre2确完成derive-only 12/48恢复、19232生成、5timeout；Q4的+.03125是读truth强插rank1的oracle，还把一条原rank2的同身份别名误作新候选。不能作为实际ranker收益。原.488已启用生成；实际100个质量母体/关闭isomerisation与生产约6谱相似母体不同。生成支线先补真实排序对照，今日不占名额。
- 今日五槽规划：**B-only、A-only、AB+Enveda仅补缺、AB+Enveda竞争、AB+可信B前体纠偏**。全部固定原.488的模型与上游排序；分库必须从精确.482外库前控制重算并保留正式guard。Enveda限定同H+/H−adduct；非法E提议保留AB输出。B纠偏只处理元信息一致且原±H索引错位的1281条，其余保持旧值。实施和真实接口检查尚未执行，不当作五版已准备/已提交。
- 新公开AlexV13自报.487、排序代码与V12相同；V8是384维新模型但不同预处理/训练源与权重实测待核，不挤本轮新信息和来源归因。详见[今日五次规划](reports/SUBMISSION_PLAN_2026-11-10.md)、[公开更新](reports/PUBLIC_UPDATE_2026-11-10.md)。

## 2026-11-09：0.482 成功版本与提升归因

- 15:37（北京时间）五条实验已冻结：oldhead前3、原v2mean前7、新同式残差前7、AlexV12外库复现、原0.482仅追加外库。前两条正式提交已接受，编号 **58155921 / 58155938**，仍PENDING。新isomer和Alex云V1已创建/QUEUED，最后外库版等待空槽，不能说5条已正式提交。
- 固定manifest `submission/optimization_20261109/manifest.json`（SHA e0779b1b...91517）；dispatcher实际PID35228，至多2个未完成Notebook、45秒循环、最长6小时；查分/提升记录进程实际PID40236，最长12小时。两个命令行身份均已核对。已接受的隐藏评分由Kaggle继续执行；剩余自动启动/核验/提交及本地记录更新需要本机任务运行。[本批状态](reports/optimization_20261109/latest_status.json)、[提交调度](reports/optimization_20261109/batch_dispatcher_status.json)。
- 自动提升记录有30项隔离检查，只接收固定分支、确定正式编号、COMPLETE且无错误的真分；原源码/metadata/recipe指纹也须匹配，严格超过已登记最佳才追加，并记录来源及归因限制。同分不写成提升，Pending不算榜分。
- 新外库5文件共264,584,131字节已在D，actual两库匹配和staged入口通过，54项独立复核通过。复现版保留Alex实际public/public fallback；优化版保持旧0.482全部32cell，仅追加相同实测谱匹配。0.484仍为作者自报，不是我们本轮已有成绩。
- 官方750330已于10/17取消开源非商业数据限制，NC/NC-SA谱库可使用，NIST及不能再分发的衍生权重仍不允许；旧文档笼统商业兼容说法已更正。第三方权重完整训练源可复现审计仍须单独完成，不能以license标签代替。

- 官方 API 15:08（北京时间）确认昨天第五条 58129661 COMPLETE / Public **0.482** / 无错误，今日剩余5次。旧本地 PENDING 为陈旧快照，已读回刷新。[线上证据](reports/optimization_20261109/initial_live_status.json)。
- 有效改动为完整 MASS 之后晚接入双 head，固定前7、仅 ranks8–25 同公式原槽重排。候选集合、查询顺序不变。新训练head本身的贡献尚未与晚接入旧v2 mean分开；昨天内部全量接入与今日晚接入位置不同，不能将负向分数当单一范围归因。
- 用户要求每次有提升记录来源，现统一使用 [提升记录](reports/IMPROVEMENT_LEDGER.md) 和 `reports/improvement_ledger.json`；包含父版本、真实编号、源码/权重指纹、指标差、负向对照、归因边界与后续计划。
- 今日计划：先检验晚接入原v2 mean及前3/前1保护的范围边界；并行训练真正只针对同式候选、固定谱均值+小幅残差的新目标，500步测速后固定预算；同时核实11/9新公开代码，不预先耗完新方案的名额。

## 2026-11-08：真实训练与新五分支

- 21:17北京时间最新正式结果：NP消融58119805=0.481持平，Na58120288运行错误无分，head seed0 58120385=0.465、seed1 58120395=0.470。两头均低于基座，停止全量head及全量均值路线；未提交的纯双head集成云草稿保留但不再正式提交。
- 第五条最终换为mass_guarded_head_tail_1108：原MASS全流程与cell14原文不动，在原BATCH完成之后才装双head并对最终候选(含LOTUS/outside)评分，前7逐字节固定，只在rank8–25同formula原槽位换序。24项actual函数/observer+7项source门检全过；另真实3query CLI小试实际双head调用、3query均改尾且prefix/候选不变(runs/guarded_tail_actual_canary_20261108/verification.json)。全局模型/控制绑定错则删最终CSV、保留control，防止silent baseline；invalid/无谱query保留。新云V1已创建但QUEUED，仍尚未占第五次competition submit。
- 固定manifest/source dispatcher实际PID44920已启动，45秒查可见状态、COMPLETE后完整source/产物门检再单次submit，最多6h，unknown receipt绝不重试；15离线状态机场景及plan-only/并发锁检查通过。只读评分watcher实际PID42336已启动45秒/最多12h，命令行身份均核实。状态reports/optimization_20261108/latest_status.json与mass_guarded_head_tail_1108/ready_dispatch_status.json。电脑关闭会停本地自动交第五条，已接受前四条Kaggle评分继续；不承诺自动发聊天提醒。
- 已从原始train准备1024 Train/128 Monitor/128 Eval身份、4801张去重谱，官方身份核验59901候选，挖30991条实际v2高分错误负例(15445同formula)。数据准备465秒、冻结encoder导出20.83秒；25986参数候选条件多谱head两seed固定各2500步完成。500步优化3.434/3.555秒，全梯度loss finite，不代表完整谱encoder训练耗时。原48与locked250未用于训练，Eval不注入真值，公共encoder full-refit曝光仍在。
- 组件结果不稳定：Monitor原.786099→seed0 .765281/seed1 .757922；原目录Eval .829744→.844922/.831022，置信区间与known-exposure边界详见reports/CANDIDATE_HEAD_TRAINING_2026-11-08.md，不可直接加到Public .481。
- 新四条已正式提交：58119805 NP最终加分消融、58120288真实Na分路GL、58120385新head seed0、58120395新head seed1。20:50北京时间API确认NP=.481持平、Na为COMPLETE但unhandled error无有效分、两head仍PENDING。第五条改为纯双head集成、不带已失败Na，37项独审通过，新云V1创建成功/QUEUED，尚未正式提交。配方、回执和状态见reports/OPTIMIZATION_BATCH_2026-11-08.md与reports/optimization_20261108。
- Na原H+Na合并重跑会牵动无Na分数，已改为保留原H过程、独立Na并以actual finite count加权；数学/observer检查通过仍未保证完整隐藏路径成功。本地actual staged worker canary及错误兼容政策排查正在进行，未取得隐藏具体trace，不能把某一猜测写成58120288根因。
- 原头×Na云创建HTTP400结果不明，未对同一target重推，读回无owned记录/get403。后续compact Na组合草稿也未部署。最终第五候选为独立新target的无Na双head集成，原失败claim与草稿保留，没有占用第五次competition submit。
- Na实际staged worker最小真实重放89.02秒通过(1query/1真Na谱/8候选全finite/count1)，未复现隐藏具体异常。已证helper兼容风险：把nonfatal errors/可用partial当fatal，以及allow_nan=False拒绝原runner支持的unknownCE NaN、NaN直比误判。另存mass_gl_na_counted_hook_repair.py及7项兼容fixture，尚未修复版完整推理/提交，不能称58120288根因已证或已解决。见reports/na_hidden_failure_diagnosis_20261108/README.md。

## 2026-11-08：失败批次收口与讨论区复查

- 官方API确认11/7下午五条均COMPLETE：V35原版0.469、weak_prior0.476、v2_emphasis0.458、robust_mass0.469、no_interleave0.469；当前最好仍是旧MASS0.481。停止V35扩展、固定v4和强RR路线；不将同一显示分解释成相同预测。
- 官方SDK讨论接口可读。分页取回全部151主题目录，并保存21重点帖子/评论原文、来源、时间和SHA至reports/discussion_review_20261108。新稿、他人自报、官方回复与我们的实验严格区分，类别比例/约130个Public分子均不是官方已证实数量。细节reports/DISCUSSION_RESEARCH_2026-11-08.md。
- 新开源Majyles完整流水线作者自报0.313，重点借鉴跨仪器Class1/全身份Class2验证，不替换0.481。已按commit 26aa5c6097922fd3fade397ea9d011f909dcb4cc下载28个小源码/文档共110995字节并核对Git blob至third_party/majyles_casmi_20261108；没有执行该仓库。
- 749412的E2首选插rank2、752356的candidate自身PubChem gate、743254四项MetFrag参数都已在0.481里。不能重新照搬后宣称新算法。新方向是量化实际finite forward覆盖，保留逐谱/真实CE候选分差并训练列表目标；扩候选时保护原列表相对统计，别把扩大候选数当收益。
- 源码确认V35还删除旧MASS最终质量首选纠偏，同时放宽physical首选并加入NP升首；因此−0.012是多项变动的整套结果，不能归因质量中位数或单个先验。保留旧0.481完整首选链。源码位置与已有机制见reports/DISCUSSION_MECHANISM_REVIEW_2026-11-08.md。
- 外库218514313字节谱parquet及116885字节aliases已全量下载D，fresh完整SHA均匹配发布manifest。730252总谱/166777发布者keys不是新增；3720 aliases关联参考谱1600张(H+1377/H−223)，仍须官方train身份复核，不能叫隐藏覆盖。全身份审计可续跑，不因新head切分抹去public full-refit曝光。
- forward覆盖实审已完成：旧Flex48主25的1200行按官方身份，GL1100行/ICE1125行已有finite分；9个真结构在候选内但首选错的query，真结构全部已有GL+ICE，因此补覆盖不应继续当主收益假设。Na缺口12query/17谱可补GL，其中11query原首选已对、1query原rank8；已冻结原候选与真实谱作一次信号canary，不把模型接口支持等同Na训练证据，也不自动改排名。详见reports/forward_coverage_20261108/summary.json。
- Na-only GL canary随后实际完成：1030原候选/1511逐谱分数无缺失或非有限，逐候选均值重构最大差5.55e-17，独立14项通过；102.74秒/峰显存0.44GB，旧H+输入输出fresh SHA不变。没有重排、新MRR、训练或新提交。实证将下步收敛到真实困难异构体的候选条件多谱匹配头，而非默认扩大模型或反复固定权重。产物runs/gl_na_probe_20261108/verification.json。

Lessons from ~30 submissions: where the MRR actually goes
We've spent a lot of submissions learning what does and doesn't move the score in this competition. No code or solution here, just measurements and pitfalls that might save others some time.

Don't analyse the visible test file. As the data page says, test.parquet is a placeholder drawn from train.parquet, and submissions are re-run on a hidden file. Statistics or outputs computed on the visible file tell you nothing about the score. We lost two submissions to this before re-reading the data page.

Evaluate exactly like the metric. Matching is on InChIKey14 after RDKit tautomer canonicalisation. Deduplicate your candidate list with the metric's key, not raw InChIKeys, or you waste slots on tautomers of the same structure. On our holdout, about 8% of molecules had a tautomer copy of the truth under a different PubChem key.

Most database-route errors are isomer errors. When the true structure is in our candidate list but not ranked first, the wrong winner has the same molecular formula about 98% of the time. Formula scoring and mass windows aren't the lever; separating constitutional isomers is. A small "same-formula isomer panel" (truth plus its best-scoring isomers) made a much more sensitive development metric than overall MRR.

Mass window width barely matters on timsTOF. On instrument-matched timsTOF spectra, 99% of precursor masses were within about 5 ppm. Going from 8.5 to 10 ppm left candidate counts essentially unchanged: the window is full of exact-mass isomers anyway.

Curated NP databases didn't add coverage beyond PubChem ∪ COCONUT for us. For public-library molecules missing from PubChem ∪ COCONUT, ChEBI, LIPID MAPS and NPAtlas contained none of them. Membership flags in curated databases also looked great on public holdouts and hurt on the leaderboard (holdout molecules are over-represented in curated DBs).

Be careful with "novel molecule" simulations. Deleting the true structure from the database and asking whether a derivative generator recovers it overstated reach about 3× for us, compared with molecules that are genuinely absent from the databases. Validate novelty work on real absent molecules. In our hands, adding generated candidates to the final list has not yet paid off on the leaderboard, even when only inserted for molecules predicted to be novel.

Know your noise floor. One test molecule is worth about 0.0025 MRR. Retraining the same GBDT ranker with a different random seed moved our holdout MRR by up to ±0.007. Compare averages over several seeds, and don't chase differences below about 0.005.

Your two best proxies can disagree. We track a public-library class-2-style holdout and a small timsTOF natural-product panel. For one change the public holdout predicted the leaderboard gain while timsTOF was flat. For another, the reverse. When a change targets natural-product chemistry specifically, the timsTOF panel was the better predictor for us. Watch both.

For database candidates, the remaining errors are about connectivity. Once the formula is right, similarity signals that don't "see" how atoms connect plateau quickly. Evidence that depends on the structure itself (in-silico fragmentation and similar) is where we found gains.

## 2026-11-07 下午实战记录

- 一个月算法路线已固定为可信验证/条件融合优先、实际检索错误hard-negative匹配头、外部参考增量并行，末层微调需先有小头证据。源码复核：当前consensus实际调用fixed rrf_order，make_features里置信度/分歧特征未进入该路径；Saner原训练本已有同formula+近质量hard pool，不能把泛泛“加hard negatives”说成新方法，新增应是当前retriever真实最高分错误候选挖掘及列表目标。full-refit预训练曝光与新head的split边界必须分开，不能包装成全栈clean CV。四周计划与72小时交付见reports/MONTH_ALGORITHM_ROADMAP_2026-11-07.md；本次仅研究/规划，没有启动新训练或替换现有部署基座。
- API刷新上一批4条均COMPLETE无error：dual_only58063780=0.480、tri_only58063822=0.475、MASS58063883=0.481、RRaggressive58063870=0.436。用户截图0.481/131名；只独立确认分数，名次记录为截图观察。旧watcher因本地关闭停留PENDING已刷新，不能凭旧状态推断仍在运行。
- 双模型相对原V56的+0.001可归于该固定神经组合；tri是用v4替掉半个v2后−0.005，暂停这一组合。强RR−0.043，停止加码。MASS整套比dual再多0.001仍混杂先验、LOTUS、质量与outsider，不能全算质量项。细节reports/ROUND2_ATTRIBUTION_2026-11-07.md。
- 下午新扫各100条官方高分/近期列表并拉17份源码，未独立核实>.481的新公开实际数值，但Gold Apex V35实质更新：逐谱physical、更松top1判据、outsider双融合、质量内联、NP promotion和4槽outside强插。Alex .481及若干clone与我们旧MASS源码相同，没有重复耗额度。
- 本轮5条正式提交均被接受：58082815原V35 baseline；58082822先验恢复SPEC.05/NP.02/gate.87；58082871 public/v2=.25/.75（主及outside八个赋值一致、日志同步）；58082895所有effective谱nm中位数、raw10adduct只补缺；58082938只禁rank8/14/20/24 outside强插、保留空槽补位。旧0.481未改，五新条当前PENDING。官方额度从0/6/5变5/11/0。
- 质量中位数是实际新功能：原effective export保存每行neutral_mass，只有另一个_targets表用中位数；原V35 merge仍drop_duplicates首张，确受谱行顺序影响。优先聚合已有effective nm以保留精确常数；原V35本已支持全10adduct，不能再将补脱水说成新改动。mass本身不能区分同分子式连接异构体。
- 五版独立审查分别13/14/15/13/15项全过，实际observer fast/hidden合成检查过、错误主混合必拒绝；robust map另6项边界过。云端五个Save&Run COMPLETE、source和来源/格式/观察器回读通过；均fast_static，只验证部署和占位格式，新算法完整效果仍须等隐藏正式评分。
- 五条PM只读watcher已启动且实际进程24376/launcher23264核对，每45秒最多12h，状态reports/aggressive_batch_20261107_pm/latest_status.json；只poll accepted固定ref，manifest SHA锁定，全部终态停。支持1–5条和manifest指定baseline，旧四条默认不受影响，4项watcher测试通过。下一批依据新V35对照分数选方向，不混比不同底座。
- 独立外部数据方向已做来源/许可/小文件审计：主办允许Enveda-180，公开mirror egehseyinca/enveda180-casmi26-reference-ccby4/1约218MB/730252 H+/H−谱，可云挂载。仅下载小元数据+55KB footer，确认无CE字段；多数可能重复train，3717source-only aliases不等于训练库外可匹配谱或隐藏命中。尚未写matching overlay，下一批先去重/官方身份及结构池覆盖审计，再做same-adduct质量窗检索。详见reports/EXTERNAL_REFERENCE_INCREMENT_2026-11-07_PM.md。新增均D盘。

## 2026-11-07 凌晨实战记录

- 用户明确授权更积极使用每日5次额度，同时尝试公开复现和若干修改版。官方刷新确认上轮tri V30为0.475，原V56仍0.479；本地48查询收益未转化为榜分，不能把已曝光的小面板当准入硬门槛或保证。
- 新搜实际代码后确认：Gold Apex V32、pop V32和Roman V17全部代码cell相同，只有宣传markdown不同，不应重复占额度。popwenman的0.482标题V2相对Roman只有V8=BOTH→MASS，即关闭学习RR、保留质量修正；标题实际分数未单独核实。原生OURS ckpt完整SHA与已有bgun v2完全一致，config只输出目录不同，已保存原始权重和等价证据。
- 00:41–00:47四条正式提交均被接受：58063780原V56+双模型、58063822原V56+三模型、58063870原V56+激进RR、58063883公开MASS配方。四条当前PENDING；原0.479保留。开始API只剩4次，提交后num_today5/num_total6/num_allowed_now0。每版代码/配方/输入与独占回执分别保存，未知结果不自动重试。
- 激进RR不再全局保护top1：原V56/public Saner与弱先验不变，使用公开102特征LightGBM，alpha1.5/lib_tau0.95/2700秒，同式非train候选可移首选。真实小型CPU特征/模型推理7项通过；另13项独立审查与fast fixture通过。公开MASS独立静态11项、fast/hidden合成observer10/17项通过；双/三模型各12项静态和3项保护fixture通过。
- 四条云端可见Save&Run采用fast_static，均COMPLETE、源内容/私有离线/来源/小CSV/观察器检查通过，但没有在可见输入上跑新变体模型。正式提交绑定云V1，隐藏阶段执行全模型并检查实际权重、覆盖、融合/质量/RR执行；不能将fast占位文件称为预测结果。
- Kaggle本次新建dual的实际slug来自title，和metadata.id不同；只读回读10项证明同源码V1后记录actual_target，未重复push。后续title和目标slug显式对齐。Notebook cell.source表示归一化继续保留其他全部JSON字段相等。
- 四分支只读watcher已启动并核对实际进程37680，每45秒、最长12小时，只查固定提交编号；最新在reports/aggressive_batch_20261107/latest_status.json，全部终态即停。云端评分不依赖电脑开机；关机仅停止本地刷新。完整记录reports/AGGRESSIVE_BATCH_2026-11-07.md。所有新增资产/缓存仍在D盘。

## 2026-11-06 实战记录

- 跨CE两两候选支持率首次纯特征导出：113个同式组中34组/14查询可用，31组非常数；27组重复官方身份、52组CE不足，按预先冻结规则跳过。支持率与原均值winner集合7组不同、4组无交集，去重/CE等权均值对照6组不同、3组无交集。另15/15独立检查通过，从原trace独立重算一组3候选×4CE的全两两投票，R最大差0。这是新增信息存在的证据，尚无效果提升证据。下一步恢复真实阶段排名/公式sidecar核对strict gate，再进行唯一固定+0.10*F干预；不把runner候选次序冒充最终top1、不扫权重、不扩大候选。
- 完整EXP003逐谱导出完成：原45查询、146张H+谱、3679候选，178.15秒（装载75.83秒、预测96.13秒），显存峰值0.45GB。12187条候选—谱评分无缺失/非有限，3679候选均值精确重构；新旧GL聚合输出逐字节相同，SHA424ffecab17f571a858da452c27a6f1ce2dda64d01549b0854d1ce1c0b0c62d9。保留原候选和顺序，未读真值或锁定250。125张为single CE，21张为merged CE；后者不能当成3个独立观测投票。首次支持率定义见`reports/EXP003_FEATURE_DESIGN_2026-11-06.md`，先导出信息审计，再做固定候选单因素效果评价。
- 16:17新V30云端可见试跑COMPLETE；只下载115,899字节小产物，离线核验41/41通过。三模型各300候选/12查询，覆盖相同、混合分数误差0，outsider组合也一致；400行CSV格式/顺序/合法评分身份通过且无重复。16:21正式提交58051406被接受，16:22为PENDING，尚无新榜分；固定V1、独占回执后单次code-submit，未上传本地48查询CSV。新只读watcher已确认实际进程17756，每45秒查分，最长12小时，关机只影响本地监控，Kaggle隐藏重跑继续。
- EXP003两查询canary的有/无逐谱记录输出SHA完全相同；独立核验30/30通过，136个candidate-spectrum适用pair完整，16候选均值逐项重构精确相等，缺失/非有限0。观测器可以用于下一步完整45查询证据导出；不能把观测等价证明说成提升证据。
- EXP004固定候选双/三神经模型对照已完成，用时127.71秒。原public CUSTOM输出逐字节复现，三模型输入/预处理/有效谱覆盖一致，无静默回退；public/dual/tri MRR为0.845106/0.849074/0.850955。tri只有3例改善、0例回退，首选均不变，最大两例贡献97.5%收益；有全训练预训练曝光，95%区间下界为0，不能称稳定增益，也不能加到Public 0.479上。独立复核41/41通过，见`reports/EXP004_PUBLIC_NEURAL_2026-11-06.md`。
- 15:53创建新的私有离线GPU Notebook `stormseye/casmi26-public-tri-v30` V1，16:13仍RUNNING，尚未正式提交新分支。三独立模型及LOTUS均有输入SHA门检，运行后还须验证实际覆盖和逐query z-score混合。完整V30同时改变先验/leader/LOTUS，必须单独记录整套复现结果。
- Kaggle会将部分Notebook cell.source由行列表转换为字符串；本次原始字节SHA因此不同，但逐cell内容、代码AST和其余全部Notebook JSON字段一致。正确绑定应保留两份SHA并验证这种精确表示变换，不能遇到差异就重复推送，也不能宽泛忽略其他字段。
- EXP003逐谱观察canary已冻结2查询、17张原谱、16候选；只按谱数和不同CE桶选择，不读取真值或锁定250。先串行比较有/无观察器的原模型输出，确认相同后才能把逐谱margin/CE一致性用于后续实验；这一步是观察等价检查，不是效果验证。

- 近期基线搜索不能只靠Web索引：官方高分/近期列表各100条找到了改名后的Roman 0.482 V17、Helios V2和新三模型/多seed分支；标题、个人best和当前版本成绩要分开。详见`reports/RECENT_PUBLIC_BASELINES_2026-11-06.md`。
- 新公开bgunshui v2/v4两checkpoint合计28.79MB，D盘下载、16/16 fresh SHA及weights_only严格加载通过；两条可用真实谱/两候选CPU前向通过。没有训练或新提交，也没有得到新0.480/0.481/0.482自己的榜分。
- 新模型仍使用同一官方train、无external_paths、full refit；目前收益路线优先是更好的模型融合与逐谱证据，不是扩充海量数据。额外参考谱只有在确认训练集外结构/条件增量时才定向补。
- 官方API证实首提58021256已COMPLETE且Public 0.479；之前SSL问题通过D盘进程内Windows受信根CA补齐解决，保持TLS验证开启。旧PENDING文件不是当前线上状态。

- 用户先确认当前0.479、约800名，银线参照约0.481/200名。提交58021256绑定原始Flex V56源码，是公开代码和资产的复现分，不是本项目新算法增益。早先API刷新SSL失败；随后已恢复官方读取并确认0.479，即时排名仍按用户观察标记，不能把本地旧PENDING文件当最新状态。
- EXP002首次单因素实验完成：固定候选评分身份集合和首选，只将最终流行度项POP_W 0.10→0，保留谱库/天然产物先验及去重补位。对照先逐字节复现原CSV，再评价干预。
- 48分子诊断MRR 0.838914→0.838229（−0.000684，95%区间[−0.004136,+0.002083]），一例6→5、一例8→17，NP不变；无提升证据，不提交、不围绕此面板反复扫权重。用时53.38秒，无新训练或模型推理。
- 小改进不是固定涨分按钮，也不能线性累计。快速实验先确保单因素、固定候选和逐例收益；干净自训组件线负责明确曝光边界。优先补充原方案尚未使用的异构体结构证据，先查清已有CE/adduct聚合，避免重复已有能力。

## 2026-11-05 实战记录

- 19:30（北京时间）首次正式提交被接受，编号58021256，私有Notebook `stormseye/casmi26-flex-v56-baseline` V2，使用原始Flex V56；19:32读取仍PENDING，未出真实榜分。
- T4×2云端可见运行约21分钟成功；12分子计算、388行占位只证明部署可运行。隐藏400路径必须等待正式代码重跑，不能将400行占位CSV称为完整推理。
- 29项提交门检查与19项独立复核均通过。CSV以官方RDKit2026.03.3核验合法候选、评分身份去重、ID顺序及SHA；主模型64项manifest和Saner四项完整pin检查均通过。祖先版本标签、旧NOT RUN字符串不能替代实际版本源码或模型meta。
- 小产物只下载约267KB至D盘。大文件对照只确认大小及首尾指纹，不能称完整哈希验证；实际数字dataset版本未在服务器元数据中暴露，需明确区分请求版本与内容指纹证据。
- 提交使用固定云端代码版本；排他回执先写，再调用一次API，结果不明不自动重试。只读后台每45秒跟踪该编号，状态写`reports/kaggle_first_submission_status.json`。
- 下一步执行`reports/NEXT_CLEAN_EXPERIMENT_2026-11-05.md`：从零训练干净小组件，隔离正例、所有训练负例、监控集及派生统计，不继承公开曝光checkpoint；锁定250继续不预测、不评估。

