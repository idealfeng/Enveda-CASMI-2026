# 全100开发查询候选评价：源码契约与验证

2026-11-16。本代理新建 `scripts/evaluate_fiora_candidate_validation_20261116.py`，没有修改原8题的源码、输入或结果。此前固定8题已完成后，根代理预先要求保留全部原100开发查询，固定现有 step0/500 权重与谱分数，并把未参与8题候选排名的92题声明为本轮主检验；原8题只作复现，全100仍作整体汇总。模型、分数、mass window、cap和分组不按全100结果调整。

最终 evaluator SHA256：`25e6abd25c81e5d8f1e09e6b1936af6066c9acea4263ff68e87dfff08f3839b9`。

## 封存输入和接口对齐

- 候选 freeze SHA：`4f4fedc2660096ff8de6e4bd3e1099c421c61189304614d6fb8b1fbfc29016cf`。
- 新准备脚本 SHA：`f1db3f6bba57c8ff414da332e3d412629811a577820a01a2688e9bde3bac5274`。
- 新推理脚本 SHA：`312c86fc40f2a71fa9c231438e1f747023efe7923adf0bce2946c28ae3bc4853`。
- step0 SHA：`38d3208f4c78a4db935b8d4b58cae643def77b050488d5d7191cf845af114048`。
- step500 SHA：`9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252`。
- 旧8题查询输入 SHA：`d4a7a4de2d7cec6e84d70e963fdced73b76e7a67a0d2f33393e4aeb7e1e84098`。

新准备和新推理源码已逐段读取核对；scorer 的成功/缺分状态、配置文件名、源码快照、source_pins、实际模型路径、query_count、expected_queries、expected/processed_candidates和行字段均与新 evaluator 相容。总候选数从已固定 freeze 读取，不沿用8题的785；实际准备代理封存100题/9402行，当前没有空窗。evaluator 仍支持合法空窗并保持原查询分母。

准备源码保留全部原 development100、原顺序以及两题没有匹配真实fragment监督的查询；新推理按候选结构构图，不依赖真结构fragment标签。evaluator 要求 freeze/config/receipt 声明全部100保留且未按 cache_ready 筛选，并核对原准备源码及实际执行副本。100与9402完整性仍须由根代理的真实执行检查确认，本审查没有打开真实预测行。

## 完整预测 gate 与标签边界

在第一次评价 metadata 读取前，程序必须绑定固定 manifest、query/candidate/window文件、准备源码、原池、两个模型及参数、推理源码、其执行副本、预推理配置和source bindings。所有 source/model/config 还会在评价结束前核对未变。scorer 原生 m/z谱分数、单图推理和同一候选集的策略延续旧8题；分数数学没有在 evaluator 重定义。

只有 `completed_dual_checkpoint_candidate_spectrum_scoring` 且全部候选两个模型均有有限 scored 结果才能评价。候选集合、原payload、行顺序、query绑定、候选连续索引、窗口与cap列表逐行核对。任一图或推理缺分即整次拒绝，写failure、不开真值、不补零分、不删除查询。exit0但receipt是缺分遍历状态时仍被拒绝。

“空的冻结质量窗口”与“有候选但预测缺失”分别处理：前者是召回上限问题，在原查询分母按候选排名RR=0记录，且明确没有可用提交名单；后者永远触发完整性失败。当前封存100题没有空窗，该路径只是防止未来误删查询。

## 主92、原8复现与100汇总

分组仅根据 SHA 固定的原8题 `queries.json` 中 `molecule_id` 集合。代码要求旧8题全部包含在新100中，固定得到三个命名组：

| 分组 | 分母 | 用途 |
| --- | ---: | --- |
| `remaining92_not_in_pilot8` | 92 | 本轮预声明主检验 |
| `pilot8_reproduction_only` | 8 | 既有8题复现 |
| `all_original100` | 100 | 原开发面板整体汇总 |

该分组计划在新预测分数行打开前写入 `evaluation_plan.json`，并绑定来源输入SHA，先于标签读取。程序没有按新分数、模型优劣、真值召回或监督可用性选择group。每组独立报告 MRR@25、Top1计数/比例、Recall@25、配对改善/下降/不变、完整窗口召回、cap后召回与cap损失查询数。两个无真fragment监督查询保留在100及各自所属组中。

固定全部100分母不会掩盖已有8题的使用：结果JSON同时提供 `primary_group_*` 和 `groups`，报告先呈现主92，其次8题复现与全100。92只是此前未检查候选排名的子集；同一development面板已被用于谱预测监测，不能包装为新独立holdout。

## 官方身份、输出25和配对区间

排名按分数降序、原 candidate_index 升序破平手。在构造输出名单时保留每个有效官方身份的首次出现，再取前25；invalid身份逐例记录。官方 metric 本身保留提交位置，并不自动去重，因此 evaluator 对实际生成的前25字符串调用官方 `first_correct_rank` 与 `reciprocal_rank` 核验 rank/RR一致性。

官方 helper 强制RDKit `2026.03.3`，身份为去stereo、canonical tautomer后InChIKey14；实际 local helper源码SHA写入绑定。完整质量窗口和cap后身份覆盖均在真实预测成功后独立复算，真值被cap排除仍保持原查询分母，并单独记录候选可用性原因。

三个预声明组都使用固定 `PCG64(seed=20261116)`、10000次有放回查询重采样，重采样单元为同一query的 step500−step0 RR差，按线性quantile取2.5%/97.5%区间。样本量始终为该组原查询数，不按真值是否在候选内过滤；模型、候选、参数与分组不由CI选择。CI仅描述固定既用开发面板内的查询变动，不能作为独立泛化或Kaggle置信区间。

## 验证范围

`validation.json`保存新准备、推理、评价三个源码的语法检查与SHA。四种微型结构夹具分别为无receipt、缺分receipt、非finite声明、原100被过滤声明，全部在真值读取前拒绝，写failure且没有评价成绩或零分填补。另用旧8真实查询ID与92个人造新ID验证预声明100/8/92分组完全覆盖且8与92互斥，没有读取新100真实标签或预测。

本代理没有打开新 `evaluation_truth_metadata.json`、coverage真实逐例或任何真实分数行，没有加载权重、运行模型、执行实际排名或bootstrap数值。准备阶段的实际候选数量来自封存代理回执；不把该回执或源码检查当作9402行真实推理成功。原8题素材、现有模型、全局文档与索引均未修改。根代理负责真实推理、官方评价与实验结论记账。

源码层面没有发现剩余接口阻塞。结果仍是固定候选上的组件证据，不是完整冠军生产管线、新榜分或clean CV；MSnLib预训练曝光仍未知。

新scorer作者随后对最终SHA的 evaluator做只读交叉审查，确认所有完整gate字段都由已封存scorer实际写出，100查询/动态manifest候选计数、source/config/input绑定、92/8分组时序和官方helper签名相容，未发现阻塞。该复核同样没有打开新真实truth/score、运行模型或修改文件。
