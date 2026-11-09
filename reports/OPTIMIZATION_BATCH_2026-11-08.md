# 11月8日：0.481底座、新列表训练头与Na结构证据

全部新资产、环境、模型和日志在D盘。本轮保留已得0.481的旧MASS完整配方，五条新分支是机制对照、新组件、独立seed复验及组合，不再次提交相同基线或迁回V35。当前状态以`optimization_20261108/latest_status.json`及各分支`submission.json`/`score.json`为准；没有正式评分返回前，不称榜分提升。

## 分支和解释

| 分支 | 改动 | 解释范围 |
| --- | --- | --- |
| mass_no_np_bonus | 仅NP_W .12→0，关闭最终merge候选的NP身份加分 | 检验这项最终先验；不声称消除模型/检索器中的全部NP信息 |
| mass_gl_na | 原H+ GL过程保留，独立跑真实Na+，按每candidate实际finite观测数合并 | 检验新增结构评分；不假定Na预训练充分或一定有效 |
| mass_head_seed0 | 冻结v2，接入seed20261108的候选条件多谱匹配头 | 新训练目标，保留原public/v2等权及首选链 |
| mass_head_seed1 | 相同数据/目标、seed20261109独立训练头 | seed复验，不作为本地已证明收益的候选 |
| mass_guarded_head_tail_1108 | 原MASS完整运行后，前7名不动，只在8–25同formula原槽位用双head排序 | 两个全量head正式结果负向后，最后一次额度改为晚接入的机制对照 |

五条均保持原MASS质量首选纠偏、物理规则和原候选生成，头只替换v2的neural_score；原cos/fp/std诊断及public分支保留，主列表和outsider共用同一scorer。两头各107291字节，base64嵌入Notebook，离线阶段不用联网取新模型。

## 本次实际训练

已完成1024 Train、128 Monitor、128 Eval身份和4801张原始谱准备；原Saner预处理，4801谱未使用历史shared CSR的另一套清洗。实际v2质量窗检索挖30991条高分错误负例，15445条同formula；不是仅随机抽同式负例。训练列表可加正例，Eval不加真值，原目录Eval召回126/128。

数据准备465.32秒，冻结encoder导出/负例挖掘20.83秒。25986参数的小头：500优化步分别3.434/3.555秒，无非有限损失/梯度；两seed固定2500步的优化分别12.30/12.72秒。零头数值契约、padding/候选置换/候选新增不重标等8项检查及21项数据边界检查通过。未按Monitor结果挑步数或改已冻结权重。

| 组件诊断 | 原v2 | seed20261108 | seed20261109 |
| --- | ---: | ---: | ---: |
| Monitor MRR@25 | .786099 | .765281 | .757922 |
| 原目录Eval MRR@25 | .829744 | .844922 | .831022 |

**不能称稳定提升。** 两头Monitor都下降、Eval改善；seed0 Eval差的paired bootstrap95%区间跨0，seed1 Monitor有明显负证据。本次是用户授权的进取实榜实验，seed复验和组合不构成本地收益准入已通过。公共v2 encoder是full-refit，存在已知训练曝光；新头分组不消除它。结果不是完整Flex/MASS验证，也不是Public分数的增量预测。

独审另发现候选屏蔽使17个Monitor/Eval query各少1个其他heldout身份；7个Eval的候选已在冻结权重后另行补回，两个seed结果都完全不变，原权重和特征缓存不改。Monitor原受限列表10个query少1候选，作为监控局部诊断保留，不能冒称完全原目录。

训练完整证据：`CANDIDATE_HEAD_TRAINING_2026-11-08.md`、`../runs/candidate_head_20261108/summary.json`及`full_catalog_eval.json`。锁定250查询/真值未读；旧48只做接口诊断，没有用于训练。

## 新信息与运行检查

- NP对照：实际score函数和fast/动态hidden观察器16项fixture通过；只有原配置cell4与merge计数cell20改变。
- Na：原H+146谱和Na17谱的实际trace按每candidate finite数重构，46query/3774候选；加权均值最大重构误差1.11e−16。真实trace、Na-only、不同candidate不同count、无Na query精确保留、坏count拒绝等9项通过。独立stage observer及坏report/export拒绝19项通过。
- 曾尝试H+Na合并一次重跑，34个无Na query虽输入相同仍与旧H分数最大差.01348，原因未证实。因此没有部署这条联合重跑配方，而是保留原H过程、独立Na并计数加权；失败控制产物归档。上游源码本来有过H-only选择的历史备注，因此不宣称社区首次试过Na，也不把该备注当当前0.481可归因分数证据。
- 新head scorer：真实3query/36谱/75候选的零头与原v2差最大1.43e−6，cos/fp/std/coverage保持；独立13项dispatch、source/checkpoint/step拒绝fixture通过。真实两个训练头的嵌入payload已抽出安装和推理，75候选finite且键/覆盖一致，确实有不同于原均值的分数。
- 三个头Notebook增加源/权重/runtime manifest SHA、主/outsider实际执行及消费输出SHA门检。可见Save&Run是fast_static部署检查；完整新推理发生在正式代码提交的隐藏重跑。没有把占位CSV或本地诊断CSV作为正式预测上传。

## 提交绑定

manifest：`../submission/optimization_20261108/manifest.json`，最多5次。每条云端新私有V1、源码与dataset依赖回读、实际小产物/官方评分身份检查后，独占回执先写，再单次code-submit；结果不明不重试。原0.481版本不覆盖，也没有自动替用户更改最终两条选择。

11/8 20:50北京时间API刷新：NP对照 **58119805=0.481**；Na **58120288=COMPLETE带unhandled error，无有效分**；单头seed0 **58120385=PENDING**、seed1 **58120395=PENDING**。第五条最终改为纯双头集成`mass_heads_only_compact`，独审37/37通过，云端创建成功，创建后回读仍QUEUED，尚未正式提交。不能把可见Save&Run或模型头本地结果称为新榜分。

Na故障实查：从实际已提交MODULES抽出的worker，真实Na1query/1谱/8候选89.02秒通过，全部finite/count1；**未复现58120288具体异常**。另证实新增helper相对原fuse存在兼容风险：不接受带非fatal errors的可用部分输出，且allow_nan=False拒绝原runner允许的未知CE NaN；比较NaN还可能误报输入不等。修复候选另存`scripts/mass_gl_na_counted_hook_repair.py`，7项函数兼容fixture通过，但未做修复版真实全pipeline推理或再次提交。诊断见`na_hidden_failure_diagnosis_20261108/README.md`，不能写成隐藏根因已定位或已修复。

原头×Na组合创建返回HTTP400且后续own inventory无target、get403；没有重推该结果不明的版本，也没有竞争提交回执。其源码/claim留存；压缩头×Na草稿通过无损检查但未部署，因Na正式失败而停用。新的纯双头版完全不包含新增Na hook，819644字节，target为`stormseye/casmi26-mass-heads-only-compact-1108`，不同于失败创建的target。HTTP400的具体原因未取得，不把1MiB推测当成已证结论。

## 21:17最终处置与排队

| 已正式提交 | 当前API结果 |
| --- | --- |
| 58119805，NP加分消融 | COMPLETE，Public0.481 |
| 58120288，Na分路GL | COMPLETE带unhandled error，无有效Public |
| 58120385，head seed0 | COMPLETE，Public0.465 |
| 58120395，head seed1 | COMPLETE，Public0.470 |

两个全量head均低于0.481，停止当前全量head集成的正式提交。上面的纯双头云草稿尚未正式提交，已从active manifest移除，云claim/源码保留，没有自动重推。最后一条活动分支改为`mass_guarded_head_tail_1108`，target `stormseye/casmi26-mass-guarded-head-tail-1108`，Notebook SHA `6de37bec32c8aa8bfb46b2c5e94e374b53fe36137dff1cd7d1c4a295359f56fe`，836874字节。完整0.481阶段和原神经cell14不变，原BATCH完成后才执行新训练头，原控制CSV单独保存。前7名原文固定，原候选与官方身份multiset、每个尾位置formula均不变；失败/无谱的query保留原结果，整个模型或控制绑定失败则删除最终CSV。

24项actual函数/observer、7项source/preflight通过；另从最终Notebook真实解码安装payload，在3个旧开发query上完整调用双head CLI与晚接入模块，全部3query改尾，prefix7和候选集合保持，模型/输入/输出SHA与实际调用均通过。该小试有已知模型曝光、原控制来自旧诊断，只验证接口与策略，不能当0.481完整验证或收益证据。

新tail云可见V1已创建，当前QUEUED，**尚未正式提交第五条，仍剩1次额度**。`scripts/submit_ready_branch.py`已针对这个固定V1启动，实际PID44920，经CIM核验；每45秒查，最多6h，可见COMPLETE后重新核对源/依赖/输出/官方身份再只提交一次。既有accepted/unknown receipt、源变化、云失败或审计失败都不重试。15个无网络状态机场景、plan-only与并发锁通过。只读watcher实际PID42336，45秒/最多12h，最终manifest SHA `b82695156d8d01b5a5cb6bb7addfe47b977a58bea926a3eda4e948288edda0e9`。自动调度仍依赖本地电脑运行；已正式接受的四条Kaggle评分不依赖本地。

调度状态：`optimization_20261108/mass_guarded_head_tail_1108/ready_dispatch_status.json`；评分状态：`optimization_20261108/latest_status.json`。不将云可见fast_static或QUEUED当成正式提交或新榜分。
