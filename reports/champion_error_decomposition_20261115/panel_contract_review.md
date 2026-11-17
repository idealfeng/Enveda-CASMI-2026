# 精确 .488 冠军：Class1/2/3 式错误分解的面板契约审查

2026-11-15。只读审查既有验证框架、冻结面板、生产 runner 和来源代码；没有执行模型、重跑 produre1/2、重抽面板、评价新结果或更改阈值。本文件是新生产诊断的实施契约，不是实验完成报告。

## 审查结论

最小可信路径是：**同一冻结查询，分别构造参考存在、目标参考删除、目标参考及静态结构删除三种条件；运行 .488 冠军所有生产阶段；统一记录候选到最终 CSV 的流向。** 先每种条件同一题 canary 验证隔离与全链，再放大到冻结48题。现成 `run_validation_pipeline.py` 仅支持 Flex/V43 的 Class1/2，它的结果不能冒充当前 .488 冠军；旧生成 harness 只跑 E006/V1FE，也不能替代完整冠军。

这里的 Class1/2/3 是显式的本地**受控可用性条件**，不是把隐藏测试的真实类别识别出来，更不据此推断隐藏类占比。三臂要分别报告；不把同一分子的三臂当三个独立样本，也不把它们加权成预期榜分。

## 固定父版本与不可混用的先前运行

- 父版本：`submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb`，当前文件 SHA256 `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`；正式提交 **58156482 / V1 / Public .488**，读回证据 `reports/optimization_20261109/mass_guarded_extlib/score.json`。
- 固定资产和来源以该目录 `recipe.json`、`kernel-metadata.json` 及其实际权重为准。`recipe.json` 的 `own_public_score=null` 是历史准备快照，不能盖过正式读回；读回的 `branch_sha256` 不是 Notebook SHA。
- `scripts/run_generation_production_20261113.py` 提供从真实 outer Notebook 到 CSV 的可借鉴 D 盘 mount/hardlink/执行框架，但其 stage 是 **12母体/300候选生成扩展**，不是冠军默认6/150，不能直接运行并贴 .488 标签。其 mount helper 还固定旧目录前缀，不能直接对新目录调用。
- `runs/generation_production_20261113_r2` 的两题全链约2,327秒是旧生成扩展的部署烟测，不是本轮的速度或隔离通过证据。后来披露该旧输入保留额外真值元数据，新的 `test.parquet` 必须按官方 test schema 严格选列，见下文。

## 最小查询面板与放大顺序

复用 `runs/validation_pilot_v2_20261104/manifest.json`：48个身份、240条谱，其中24个 NP（同仪器天然产物）、24个跨库开发身份。原查询和原先 cap12 不变；不要把 Extlib2 门控训练的 cap3 引入冠军本体。原 cap12 是开发预算，不是官方限制。

相关冻结指纹：

| 内容 | 固定路径/指纹 |
| --- | --- |
| 查询 | `runs/validation_pilot_v2_20261104/queries.parquet`；SHA `de8818acf93035c937f896ee93fa5aecfb1352af9727faf79eaa1af33bf9b5fc` |
| 标签 | 同目录 `truth.csv`；SHA `b47e21297d5b3b528430a9fd2286574589026b4d3f2228c3ac2b6d98f260fb7f` |
| 冻结 split | 同目录 `frozen_splits.json`；文件SHA `e80e6d806eb4fdb6e93a63b965a63ec95513e7b656d34b5860a12b5a8edc0ca5`；内容split SHA `7126c55aebbc33505d1659797550d0d90cbb3014e3116862cf75cdde0c3e7ee0` |
| 全身份排除 | 同目录 `class2_exclusion_keys.json`、`class2_exclusion_rows.parquet`、`structure_identity_audit.parquet` |
| 自身/精确重复排除 | 同目录 `query_duplicate_exclusion_rows.parquet`、`spectrum_duplicate_audit.json` |
| 原始行级选择 | 同目录 `query_selection_audit.json`；原数据完整性见 `dataset_integrity_report.json` |

**Canary：** 每个条件先运行同一 `cross_VXVNYCRICCVPTD` 的原冻结全部查询谱。选择理由是它有已知4个同官方身份 train SID（858、215890、224967、234305），能直接检验“只删首个 SID”的历史隔离漏洞；不是按分数挑容易样本。canary 只证明接口、隔离和生产执行，不计算统计收益。Class1 还要记录去掉查询本身后实际剩余同身份参考数；若为零，不得假称“参考存在”。

**放大：** 三条件 canary 全部满足隔离与完整运行检查后，固定全48题三臂（144个query-condition，但统计单位仍是48个分子）。若预算要求中间层，先按 `panel × query_source` 固定名额，再对 `sha256('20261115|'+molecule_id)` 排序取样；选样清单与哈希必须在新模型评分前冻结。可额外按原始极性、adduct、CE桶、谱数分层描述，不能按本轮错题再换题。

不抽取或评价 `cross_final_locked` 的250题；可以读身份清单用于训练排除，但不把锁定集悄悄变成研发面板。旧 NP250 与 cross-dev200 只有前48已抽出查询；扩大需要另立新 manifest，本轮不必重跑全 train 结构目录和原已完成重复扫描。

## 三种条件的隔离定义

| 条件 | 参考/analog | 静态候选结构 | 生成 |
| --- | --- | --- | --- |
| C1：其它目标参考可见 | 排除所选查询自身及已知重复；允许其它同官方身份实测参考，但逐题记录是否实际存在 | 保持原冠军结构来源 | 原6母体/60每母体/150总量、单/双步保持 |
| C2：目标参考不可见 | 全部来源中删除目标官方身份所有谱、全部adduct、全部SID及canonical alias；analog同样不可见 | 保留目标结构在原有结构库/知识表中的可用性；实测是否被候选检索物化 | 原生成保持 |
| C3：目标参考及静态候选不可见 | 与C2相同 | 所有静态结构来源按官方身份删除目标；允许随后算法重新生成目标 | 原生成保持，不能在最终输出把重新生成的目标再删掉 |

推荐沿用既有验证的**全cohort身份留出**语义：对完整48题，C2/C3参考mask同时屏蔽这48个目标身份，不是每题各留其它47题参考。canary 子集与48题因此是两种cohort规模；不能当完全相同任务直接对比分数。源代码按 query 分别需要的mask和审计可另行记录，但本轮不要无记录切换两种留出定义。

官方身份必须用 `validation/metric.py`：RDKit **2026.03.3**、去立体、tautomer canonicalize、InChIKey前14位。现有全train审计已覆盖51个raw家族/5,725谱/19种adduct；可复用其mask，不能仅用查询的10种adduct屏蔽参考。对新接触的 AB/静态结构来源，安全缩小规范化工作量可按**重原子组成**预筛；不能以存储的完整分子式、氢数、电荷或raw key相同代替官方身份穷举。

## 现成hook可复用处与必须补足处

1. `validation/pipeline_adapter.py:install_e1`：在任何 Library/extended Library 初始化前装hook，维持原CSR/谱行号，mask直接检索及 representatives；`_engine_reps` 同时屏蔽analog代表。它已处理扩展库清洗后精确query重复，仍需记录重复定义。
2. `validation/pipeline_adapter.py:install_e2`：先让完整结构池构建完成，C2仅令被排除谱的 `row_p=-1`，在 `build_index` 前落实，检查direct及all/pos/neg representative indexes没有被屏蔽行；**C2不能顺手过滤候选结构池**。
3. `validation/pipeline_adapter.py:patch_generated_e2/patch_pipeline_cell`：可参考其严格marker计数与候选记录方法；旧匹配文本针对Flex/V43，必须对冠军最终解压、确定性补丁后的真实运行文件逐一核对，不能只导入原assets组件小试。
4. **末端AB是额外入口。** 冠军 `scripts/external_library_overlay_20261109.py` 包装 `alex_v12_external_function.py`，独立再次载入AB参考。原validation E1/E2 hook不会拦它。C1必须跨AB排掉query内容重复；C2/C3必须在AB refs进入搜索索引前按官方身份屏蔽目标，记录A/B各source原始/删除/剩余数。不能在事后只禁止正确提议升首来伪装“参考缺失”。
5. **library_max必须随隔离条件重算。** 它由本次已隔离的原始生产推理生成到 `frozen_candidate_evidence.parquet`；后续MASS/AB保护使用本次值。此前 Extlib2 组件诊断复用了旧 cached library_max，有明确边界；P0完整误差分解不可继续复用那个上下文。
6. **C3还没有通用现成实现。** E1 pool、E2 COCONUT/BIO/PubChemLite/train并集、独立PubChem-tier检索、LOTUS backfill、其它静态 outsider/tail rescue 和参考直接候选入口均需逐一枚举。只drop一个E1 PID不能封住其它来源。
7. E1 `casmi/engine.py:run` 当前接受单个 `drop_pid`，且生成的 `exclude_keys` 从静态mass-window构建。C3要先过滤**所有同官方身份静态PID**，并从生成排除集合中去掉这些被隐藏目标，才允许生成重新造回；不能只在ranker后删。维持剩余原PID及特征数组坐标，不改共享资产原文件。
8. 对静态知识表中的目标行可以阻止它**作为候选入口**；对生成的新结构仍按生产原有方式计算可获得的候选特征。若研究问题还要求目标完全不在外部NP/流行度知识中，那是更严格的另一个消融，不能暗中混入本轮C3。二者应分开命名。

原 `produre2/q345_lib.py:find_truth_sid_pid` 只找首个SID、一个PID；此次不能直接复用其隔离逻辑。复用已完成问题清单、结构身份方法和旧路径证据即可，不重做Q3模板/质量容差/母体扫描。

## 生产执行与原参数约束

建立新 `runs/champion_error_decomposition_20261115/...` 目录、D盘缓存和独立生成源码副本。原assets、冠军Notebook、produre及旧run不写。hardlink输入文件可省空间，但**绝不能就地修改hardlink资产**；需要补丁的代码必须复制或写新文件，并记录原SHA、marker、补丁后SHA。

参照旧production runner设置 `KAGGLE_IS_COMPETITION_RERUN=1`、严格的 `/kaggle` 所有权/绑定检查、运行每个outer code cell。新输入 `test.parquet` 只取官方test实际列；真值、raw key、source_row、panel/source、排除mask放独立控制文件。明确的mask构造模块可以读取标签做受控移除，ranker/排序特征不能读取标签。sample_submission的SMILES仅为占位，不计为候选来源。

精确冠军关键参数在其outer cell4和原source固定如下：

- `VARIANT='CUSTOM'`，`w_top=.25,w_mid=.75,rescue=0`，`RRF_OFFSET=3`。
- PHYSICAL=True、PROVENANCE=False、FRAG_ON_V2=True；`POP_W=.10,SPEC_W=.10,NP_W=.12,LIB_HIT_GATE=.78`。
- `V8='MASS'`，中心-1.5ppm/free3/full8/weight.15；leader-off5ppm、library保护.9；RR8未启用。
- guarded head保留前7名，仅原同式位置8–25；两既有head不能替换为新模型。
- AB `TAU=.8,K_PEAKS=4,LIB_TAU=.9`，precursor窗 `10ppm+.002Da`，fragment `.015Da`；仍保持冠军raw-SMILES提议和官方身份合法性guard，不顺手引入身份alias新promotion规则。
- 原生成6母体、`gen_min_sim=.3`、每母体60、总150、`gen_tol_da=.004`、双步；`generate=True` 来自生产实例化，dataclass的默认False不能代表当前实际关闭。
- 原outer时间保护7.5小时、physical1500秒；其它原subprocess budgets由真实冠军stage配置完整导出并保持。旧验证runner按48题自动缩成ICE636秒/N1636秒，不应不经记录用于“原冠军完整生产”。预算中止、optional skip和空候选必须分开记录。

资源性改动如CPU worker=4可以沿用，但要明列资源适配和wall time。不能为了过canary跳过E2/PC、用旧候选分数、手动执行V1FE替代outer管线或走fast_static。第一题初始化可能占多数时间，目前没有本轮耗时实测，旧两题约39分钟不是承诺。

## 每题需要产出的误差证据

每个arm都保存实际候选事件 `molecule_id,stage,source,official_identity,rank,score,is_generated,parent/path_if_observed`，以及 `stage_status/coverage`。至少包括：E1原始检索与生成接受候选、E1实际ranker前后、E2物化mass-window与ranker输出、PubChem实际发出的候选、融合名单、原最终25、物理/神经/MASS/head后的名单、AB前后最终CSV。同一身份多个SMILES按官方评分语义评价，**不得为诊断更改生产实际顺序**。

三种召回分母要明确：源数据库可用身份、实际物化候选、最终25。现在 `validation/stages.py` 的E1仅在检索/生成/裁剪后记录，PubChem仅发出top列表；未补上更早观测时，只能写“所有**已观测**来源未出现”，不能写“完整源库根本没有”。阶段无行默认unknown，只有显式processed+empty才判召回miss。

建议用互斥结果加多标签原因：

| 结果桶 | 要求证据 |
| --- | --- |
| 正确首选 | 最终官方身份rank1 |
| 已进25但排序靠后 | 最终truth rank2–25；另标同式错误首选 |
| 真候选已物化但丢失 | 某实际上游stage有truth，final25无；记录最后存在/首次丢失及该stage覆盖范围 |
| 所有已观测候选均无truth | 每个必要stage处理状态完整；未观测全源则保留global recall unknown |
| 不可判定/运行异常 | 缺stage、budget/模型失败/占位填补；不能混入真实0分召回 |

“后处理改坏/改善”另按连续名单的RR和top1变化记事件，可与结果桶交叉，避免把最终rank2的后处理损失漏掉。生成单报全query coverage、生成后ranker/最终25留存，不能只报成功生成子集19/19。

最终报告至少有MRR@25、Top1、Recall@25、物化候选truth recall、各stage丢失、后处理修正/破坏、同式首选错数、各源贡献事件、运行失败与覆盖、耗时。按NP/cross、source、极性/adduct、CE和谱数分层；小格报告分母，不用canary或单例百分比当稳定规律。

## 不能消除的边界

- 这些谱来自训练集；FPNet full1声明见过全部训练fold，Saner final声明full-data refit含旧holdout，其他ranker成员未知；现有head也有项目内训练曝光。完美参考隔离仍不是干净模型泛化验证。
- NP公开面板已被公共作者使用；旧48也已多轮分析。它适合定位生产失误，不能作为未来无限扫参的无偏裁判。
- 旧数据只扫描float64精确原谱重复；近重复/截峰/不同精度/跨adduct转化不在该保证内。AB如另加严格/量化内容去重，必须三臂共同采用并单列“诊断去重适配”，不能说无改动复现榜分。
- 本轮结果不会揭示隐藏Class占比，也不能把本地三臂指标同.488 Public直接相减。任务是补齐同一冠军的可观察误差分解，随后决定新增信息/训练目标，而不是复验旧produre结论。

证据入口：`validation/datasets.py`、`validation/pipeline_adapter.py`、`validation/stages.py`、`validation/evaluate.py`、`validation/metric.py`、`scripts/run_validation_pipeline.py`、`scripts/run_generation_production_20261113.py`、`scripts/external_library_overlay_20261109.py`、`reports/validation_data_audit_20261105.md`、`reports/produre_review_20261111/Q345_NEW_REVIEW.md`、`reports/BOTTLENECK_ASSESSMENT_2026-11-12.md`、`reports/optimization_20261113/evidence_generation_release.md`。

## 本轮新增runtime隔离模块与目前核验范围

已实现独立 `scripts/champion_reference_masks_20261115.py`，不修改上述旧框架或冻结源文件：

| API | runner插入位置与作用 |
| --- | --- |
| `install_e1(code_root,config_path)` | inner36 `build_spec_cache` import前；复用全SID参考mask，C3另过滤Pool.window，原PID坐标/生成恢复保持 |
| `patch_generated_e2(path,config_path)` | inner32 `ENG = {}`前；原adapter源码marker校验后转入本模块install_e2，C3过滤pool_window |
| `patch_generated_pubchem(path,config_path)` | inner34 `PC = {}`前；C3过滤PC所有store window及行对齐prior，并过滤best_pool_fz结构窗口；Linux fork运行 |
| `install_ab_observer_filter(config_path,helper_module)` | outer32载入原AB helper后、run前；在refs.append前删除query内容重复、C2/3删除目标官方身份；原匹配数学和观察位点不变 |
| `patch_outer_static_cell(text,config_path)` | **outer20执行前**；C3必须通过唯一LOTUS backfill赋值marker过滤静态入口 |
| `assert_installation_complete(config_path)` | 最终CSV及各原audit之后；缺安装/参考/静态窗口/LOTUS证据报错，只检查安装证据，不替代候选或准确率审计 |

config需要`work_root,queries_file,exclusion_rows_file,exclusion_keys_file,reference_mode,base_train_rows,cohort_policy`；其中`queries_file`为带source_row的控制查询表，推理test仍严格官方列。`blocked_official_identities`若给定应与声明的global48相符；可另给`inference_queries_file`做AB内容匹配、`truth_control_file`提供mask身份的安全重原子组成加速。config在模块中缓存，runner应先冻结后执行，不能运行中修改。所有stage源码适配写生成副本，Notebook源字节不改。

已通过15项**无模型**检查：真实生成E2/PC源码三模式marker+AST可编译、C1/C2/C3静态结构语义、AB三模式query内容排除与目标参考保留/删除。原AB仍是2个reference观察点、1个match观察点。[源码契约核验](source_contract_preflight/verification.json)。该核验没有真实Library初始化、没有GPU模型、没有全生产；只为进入canary准备。全SID/索引mask实际生效、Class3目标能经真实生成回来、各阶段与最终CSV绑定仍须实际canary证明，不能由15项检查推出。
