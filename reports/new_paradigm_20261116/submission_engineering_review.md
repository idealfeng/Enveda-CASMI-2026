# 11/16 FIORA 提交工程独立核验

状态：只读源码核验；没有上传、创建数据集、启动Notebook、提交竞赛或运行模型。用户本轮明确授权“先提交本轮的，明天看结果”，覆盖旧可行性文档中“主92显著阳性后才值得工程接入”的先后建议；本地收益不确定性仍保留。

## 最小接入点

固定冠军 `submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb` 为33个cell；最后cell32负责原AB外库overlay。新FIORA应append cell33，消费**AB后的实际 `submission.csv`**，先保存父输出，然后限定真实机型/离子/CE，按候选自身公式、原slots重排。原cells0–32逐cell不变，可最大限度避免重演改错内层FROZEN源码绑定的问题。

`effective_query_spectra.parquet`来自原inner真实查询，可能含遗留truth列；新runtime必须 `read_parquet(columns=白名单)`，不能整体读后再删。最终候选需从冠军CSV解析，不可使用早于MASS/head/AB的旧evidence代替。

冠军SHA为 `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`；新增runtime、payload、模型、参数、Notebook、metadata及recipe均应单独固定SHA。新模型放私有Kaggle dataset并在metadata追加**明确版本**，不得替换冠军已有dataset列表。

## 可见运行和隐藏重跑

冠军cell4默认 `COMMIT_MODE='fast'`。cell5根据 `KAGGLE_IS_COMPETITION_RERUN` 或真实test签名决定 `IS_RERUN`；非rerun fast会输出可见占位CSV而不执行原模型。cell29和31的原observer在 `not IS_RERUN` 分支强断言 `fast_no_model`。因此**仅把COMMIT_MODE改smoke会与原observer冲突**，不能称最小无损修改。

真正完整可见生产验证可通过新增、明确记录的早期cell设置 `KAGGLE_IS_COMPETITION_RERUN='1'`，使原初始化、全部可见query、原audits及新FIORA到最终CSV完整执行。必须注明这是“真实可见全路径”，不是已通过隐藏测试；其耗时可能明显高于普通Save&Run。代码绑定含此适配、所有路径和最终CSV应验证。`kaggle_batch.csv_audit`固定官方sample400行，不能拿12行独立smoke结果冒充该正式stage的可见输出。

另一种可快速得到正式隐藏反馈的工程取舍是保留原fast可见，额外在目标镜像执行独立无标签FIORA组件canary（真实候选构图、strict load、谱评分、实际CSV消费），随后正式提交让隐藏首次完整运行。这类记录必须继续写 `fast_static` / “组件成功、隐藏全路径待验证”，不能写“完整生产已通过”；用户是否接受探索由本轮明确授权及主agent判断，不能用检查项数量替代证据。

## 现有云端提交引擎

`scripts/kaggle_batch.py`支持schema1 manifest、1–5个唯一新V1分支、`validation_mode='fast_static'`或`'smoke'`、每分支最多8个JSON runtime audit。使用新manifest/state_root；不改旧历史manifest、receipt或冻结源码。

1. `local_preflight`校Notebook/metadata SHA、私有/offline/GPU/competition/model_sources、每个codecell可编译；fast_static需要源绑定静态review。
2. `launch`枚举完整本账户Notebook，确认新slug未存在，**先写独占 `cloud.json` claim再 `api.kernels_push(... no_run=False)`**。未知结果只读reconcile，不重push。
3. `live_binding`读回私有、offline、GPU、V1源码与dataset/kernel源；当前 `slugs()`只对比owner/slug，**不证明数值dataset版本**，需额外runtime对新增payload逐文件SHA保证内容。
4. 可见session COMPLETE且无failure后，`audit_outputs`下载submission.csv和指定JSON，限定体积，校400行ID序、格式及官方RDKit身份、每个observer字段及checks。已有三个父audit要在FIORA执行前生成，FIORA新增audit应明确父CSV SHA与最终CSV SHA链，不要要求旧AB audit的CSV等于FIORA变更后的最终CSV。
5. `submit`检查本轮claim数量、唯一description/已提交kernel版本、实时每日余量，**先独占 `submission.json` claim再 `competition_submit_code(file_name='submission.csv', kernel=ref, kernel_version=1)`**。该方法提交代码重跑，不上传本地验证CSV。未知结果只能按ref或唯一description读回。
6. `poll_submission`按ref读回；COMPLETE+有限public_score才记成绩，仍需检查 `error_description_present`。PENDING/RUNNING不计新高。

单分支也可直接依次调用已有CLI `--manifest 新manifest --branch 分支 --launch`、`--status`、`--audit-outputs`、`--submit`、`--poll`。`dispatch_subset_batch_20261112.py --watch`最多2个Notebook并行、6小时，**其prepare强制manifest.max_submissions==5**，因此若本轮固定1次提交，直接调用引擎CLI即可，不应为迁就dispatcher制造5个实验。

## 私有payload上传机制

本地Kaggle SDK的 `dataset_create_new(folder, public=False, quiet=False, convert_to_csv=True, dir_mode='skip', ignore_patterns=None)`读取 `dataset-metadata.json`，要求owner/slug、title、恰好一个license。title和slug长度6–50；可用 `convert_to_csv=False` 保存原始模型/代码字节。**默认dir_mode='skip'会跳过payload子目录**；应上传单一确定性payload zip，或显式 `dir_mode='zip'` 并核最终挂载布局，不能默认为递归目录直接可见。

该SDK本身create调用内部 `with_retry`；不应在外层捕获后再次自动调用。上传前主工作流需独占claim并保存本地文件SHA/大小，异常后只查dataset状态/列表复核是否创建。`api.dataset_status(ref, format='json(status,current_version_number)')`可同时读ready状态和实际版本，随后在Notebook metadata固定 `stormseye/<slug>/1`。

推荐私有dataset含单一payload zip、清单和receipt，Notebook只在workspace解压；严拒绝绝对路径/`..`/符号链接越界，逐文件SHA校验。最小依赖仅带模型需要的纯Python部分，复用目标镜像torch/RDKit/numpy/scipy；本地cp312原生扩展不能盲覆盖已有镜像。冠军metadata已固定Python3.12预期镜像、T4、offline，可见真实组件canary能验证实际ABI和PyG native torch分支。

## 独立审查边界

上述是现有机制的源码结论，不是新runtime正确、payload可移植或任何全路径运行成功的证明。runtime/payload新文件落地后仍需核白名单、score数学定义、公式slot/候选multiset不变、整题fallback、真实分数消费及父子SHA链。没有触碰produre1/2或提升账本。

## 新runtime及builder首轮独审

随后核验了 `scripts/fiora_submission_runtime_20261116.py` 与 `scripts/build_fiora_submission_20261116.py`：未发现阻断提交的代码契约错误。独立轻量核验结果存于 [submission_independent_code_review.json](submission_independent_code_review.json)，包含当时源码SHA：两文件可编译；实际 `spectral_score` AST与已测8题scorer完全相同；`compiled_mass_map` AST与原prep完全相同；12个SMILES例子（含tautomer、stereo、invalid）官方身份与本地官方metric一致；单CE边界例子通过。没有在本审查中运行模型。

builder追加一个cell，原33个cell完整deepcopy且逐cell比较；runtime CLI与builder命令、输出JSON字段兼容，现有payload `files` 为路径→SHA字符串，符合二者。可见分支保留原fast CSV，独立真实canary要求 `model_invoked` 且 `scored_queries>0`；隐藏分支读真实COMP/test八列白名单并在完整父三审计后执行。原公式slots、候选multiset、ID顺序与whole-query fallback有执行断言；没有把前7保护自动继承给新模型。

一项非阻断的报告语义限制：当前runtime在成功 `load_model` 后即写 `model_invoked=True`，不单独代表实际完成candidate forward。可见canary额外要求scored_queries>0，已避免空载被当成可见前向成功；隐藏可能出现所有候选失败后整题回退而audit通过，应以真实 `scored_candidate_rows`、`scored_queries`、`reason_counts` 和changed位置报告新模型实际参与情况，不可只用model_invoked宣称有效推理或提升。此政策属于明确的探索回退，不改变父冠军本身。

**后续修正已独审：** runtime不再在load后声称model_invoked；改为 `model_loaded=True`，真实 `model(batch)` 调用前增加 `actual_forward_calls`，最终model_invoked由次数决定，成功候选与候选失败query另外计数，zero-scored区分 `all_candidate_attempts_failed` / `no_eligible`。`load_model`变更为返回4值后，唯一调用点已同步4值解包。上段保留初审历史，不再作为当前缺陷；真实成功消费仍看scored_queries和scored_candidate_rows。

## 上传器与确定性压缩包独审

`upload_fiora_payload_20261116.py`明确 `public=False`；authenticated404确认新slug不存在，创建前独占claim并fsync，禁用API默认create重试包装，未知结果只读status。status同时记录实际ready状态、版本和is_private；调用方launch前仍需明确校验ready/private/version1，而非仅因status读成功就放行。

已独立读取确定性archive的全部762个member并校SHA，文件列表恰好等于manifest声明文件加manifest本身，无重复、越界、符号链接或`.so/.pyd/.dll`，manifest字节与本地相同。51,684,471 B单zip避免默认dir_mode skip漏目录问题；详细证据与当时3份源码SHA在 [submission_archive_independent_review.json](submission_archive_independent_review.json)。本审查没有上传、外部写操作或模型推理。

后续上传器还处理Kaggle对不存在私有slug返回403：`make_api`先强校本人stormseye，403分支枚举 `dataset_list(mine=True,page=...)` 的完整MY组（已核SDK默认20分页），只有目标缺席才claim/create；403自身不被当成不存在。该分支没有写重试。status已新增 `ready_for_notebook`，要求ready、version1、is_private真、ref精确，原“调用方需额外检查”的风险已有显式gate值。

## 最终冻结复核

最终stage [fiora_tims500_fullslots](../../submission/optimization_20261116/fiora_tims500_fullslots/notebook.ipynb)已独审，Notebook SHA `550980d58100fce62830f089848bc303e102ec0f912ffadb14e9fd2ad53d11b4`，runtime SHA `1f7dece2a4a817c54c1915dbc45ad64ebaa6e084d4646acc3f6cd7972d80e817`，recipe SHA `7dc47ef562744ee9486e52067508ff0ed03f6e5cfa84f6cf863f17d4f1594544`。原33个cell不变，新增cell嵌入runtime与实际源码字节完全相同；branch/manifest/metadata及zip/model/config绑定均通过，private/offline/GPU和新dataset `/1` 精确。全部cell可编译，隐藏原父全路径与可见独立canary边界没有混写。[完整冻结独审](submission_final_freeze_review.json)。

已只读查收runtime作者真实回执：无标签dev2共50次forward、2题评分/改序、0候选失败；既有生产2输出为1题支持、25次forward、1题改序含首选，另1题无支持原样；static无调用且CSV字节相同。与既有50候选历史谱分数最大差8.59e-9，低于1e-7且两题最终重排一致。以上属于**新runtime真实到CSV组件运行**，没有重跑冠军初始化，也没有证明排名提升、Kaggle镜像或隐藏通过。本独审没有重跑这些模型。[作者实际执行回执](../../runs/fiora_submission_canary_20261116/runtime_checks/verification.json)。
