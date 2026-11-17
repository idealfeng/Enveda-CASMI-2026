# 本轮正式探索：FIORA tims500 接入冠军最终候选

**后续正式结果（2026-11-17）：58435031已COMPLETE，Public=.285，无错误；停止当前接法。** 下文保留提交时的PENDING快照；最新结果和处置见[正式结果](../optimization_20261116_fiora/ROUND_RESULT_20261117.md)，不能继续按旧PENDING判断。

2026-11-16。用户明确要求「先提交本轮的，明天看结果开始下一轮」，中断后再次要求「继续提交」。本轮固定一版，不补齐五个近似配方；下一轮困难负例训练尚未开始。

- 状态：**正式提交已接受，编号58435031；2026-11-16 23:13北京时间官方读回PENDING、无分数/无报错。** 私有资产V1 ready；Kaggle可见运行COMPLETE，新FIORA两题50次实际forward/评分/CSV与原父版fast输出审计均通过。首次隐藏完整生产重跑尚未确认成功，未取得新榜分。最终以 `reports/optimization_20261116_fiora/` 的提交和评分读回为准。
- 假设：独立正向谱模型可能补充原指纹、碎片和实测库证据，尤其区分最终名单中的同分子式异构体。既有主92题组件MRR仅 +.009997，配对区间跨零，不能声称已证明稳定收益。用户授权在此不确定性下做一次正式探索。
- 父版本：正式58156482 / .488，`submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb`，SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。
- 唯一新增组件：完整父版AB输出之后，使用本轮FIORA step500谱分数，在候选自身同分子式分组的原slots中重排，含rank1。不新增候选、不混合系数、不扫描阈值、不额外增加AB保护；原父版各步骤保持。
- 模型：`runs/fiora_tims_model_20261115/pilot500/last_checkpoint.pt`，SHA `9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252`；纯state导出SHA `c449c98ad0cf42e71561b8de97073986a447019c7430c82111a7eb29466c54f9`，67tensor逐项与父checkpoint相等。params SHA `1f189efe9fb64f43406bce409b825870655f8b83765c5ee77d3e208e2cbc2418`。
- 输入：真实timsTOF、[M+H]+、单有限CE20–60eV，按spectrum_id字典序固定选择一条合格谱；仅读8列查询观测，绝不读取真结构/真分子式。
- 支持范围：提交硬预算64重原子/160有向边；训练只覆盖32/74，故明确为大图外推实验，不能冒充已验证训练域。无合格谱、候选超预算或单候选推理失败时整题保留父版，不只删除失败候选。全局源码/资产校验失败则终止。
- 评分：保持已测native depth1质量映射、去观测前体、预测强度>.001、sqrt谱cos .01Da；同分按原位次稳定排序。官方身份和公式用RDKit2026.03.3。
- 离线资产：新私有dataset `stormseye/casmi26-fiora-tims500-1116/1`；仅纯Python依赖和实际权重，无不匹配cp312二进制。逐文件SHA、模型父SHA与包SHA绑定。
- 可见运行：原冠军fast路径保持；另在Kaggle目标镜像跑真实2题FIORA模型→分数→CSV canary，至少一题真实评分成功后才准许正式请求。该canary不是新冠军完整推理。正式评分重跑才执行原完整生产初始化→AB→FIORA→最终CSV。
- 预算：一个新Notebook版本、最多一次正式请求；先落claim、未知写结果只读核对，不自动重试。FIORA子进程上限3600秒，原父版预算不改。
- 保留：父冠军、失败/浮点差异证据、导出清单、组件日志、包和Notebook固定SHA、Kaggle回执均保留在D。produre1/2不重跑、不移动。PENDING不写成新高，真实新高后才更新提升账本。

本地组件证据、目标环境实际canary、云端接受请求、隐藏完整运行与正式榜分分别报告。完整冠军本地P0此前OOM/r2中断仍未完成，本次不将其改称成功。

## 实际执行回执

- 本地75次真实forward与CSV绑定：[runtime报告](runtime_canary/REPORT.md)、[原始回执](../../runs/fiora_submission_canary_20261116/runtime_checks/verification.json)。隔离包验证与浮点微差：[payload报告](../optimization_20261116/fiora_payload/VERIFICATION.md)。
- 模型纯state、参数、762文件asset_manifest、包与Notebook固定SHA：[独立冻结核验](submission_final_freeze_review.json)。
- 私有dataset ready/private/V1：[状态读回](../optimization_20261116_fiora/dataset/status.json)。SDK返回带`/datasets/`前缀，最初本地字符串检查误标需审查；随后只读核对后归档，未重试创建，原回执保留。
- 冻结Notebook V1请求：[cloud.json](../optimization_20261116_fiora/fiora_tims500_fullslots/cloud.json)；源码、私有、离线与依赖读回：[binding.json](../optimization_20261116_fiora/fiora_tims500_fullslots/binding.json)。
- 一次提交调度状态：[ready_dispatch_status.json](../optimization_20261116_fiora/fiora_tims500_fullslots/ready_dispatch_status.json)。`waiting_cloud`不是比赛已接受；正式接受后以同目录`submission.json`的ref为准。
- **正式接受**：[submission.json](../optimization_20261116_fiora/fiora_tims500_fullslots/submission.json)，ref58435031，Notebook V1 `stormseye/casmi26-fiora-tims500-isomers-1116`，北京时间23:12:59接受，本轮仅使用1次请求。
- **最新官方状态**：[score.json](../optimization_20261116_fiora/fiora_tims500_fullslots/score.json)，PENDING不是新成绩；原.488冠军及提升账本保持。
- **目标环境实际组件验证**：[target_component_verification.json](../optimization_20261116_fiora/fiora_tims500_fullslots/target_component_verification.json)，50/50候选真实评分、2题重排、0候选错误，用时56.1秒；[原始FIORA观察器](../optimization_20261116_fiora/fiora_tims500_fullslots/outputs/fiora_submission_audit.json)。通用batch审计的fast_static说明只涵盖父版可见fast路径，新增组件的真实前向由此独立观察器明确记录，不能混称完整父版或隐藏成功。

## 明天的第一步

先只读拉取58435031的正式状态/分数；若失败先查看隐藏执行日志，若有成绩先记录与.488的实际变化及完整pipeline资产绑定，再决定下一轮。**不重提本次Notebook，不先启动新训练，也不把PENDING记成降分或提升。**

读取命令：`.venv\Scripts\python.exe scripts/kaggle_batch.py --manifest submission/optimization_20261116/manifest.json --branch fiora_tims500_fullslots --poll`。正式读回后按项目规则刷新索引；只有真实新高才改提升账本。
