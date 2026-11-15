# 2026-11-12 五版执行记录

22:29状态更正：生成r3 **58271324隐藏重跑异常、无有效分，已经消耗正式额度**；Saner best-validation58263831=.478，新外库58263553=.488，另两条仍待评分。下文19:33“五条正式接受”仅指服务器接受请求，不能读作五条完整推理成功。排查发现生成补丁未考虑FROZEN运行前对engine的源码修改，修复候选与路线取舍见[本轮复核](ROUND_REVIEW_2026-11-12.md)。

父版本：58156482 / 已确认Public .488。用户授权本日五次正式提交，继续冲排名；produre1/2保持已完成诊断的定位，本轮没有重做两组任务书或48查询面板。

北京时间19:33最终回执：五条全部正式接受，官方确认今日已用5次、剩0次。19:35只读查分已取得首条真分：新外库匹配58263553 COMPLETE/.488，未超过冠军；其余四条仍PENDING，最佳仍.488。

| 方案 | 正式编号 |
| --- | ---: |
| 新版AB质量/adduct匹配 | 58263553 |
| popwenman best-validation集成 | 58270931 |
| Saner best-validation集成 | 58263831 |
| 生成预算与模板策略revision3 | 58271324 |
| popwenman best-validation＋新匹配组合 | 58271026 |

五份云端可见产物核验均passed，提交源码/metadata/recipe及固定编号已绑定。最终机器摘要为 [execution_status.json](optimization_20261112/execution_status.json)。

## 实际五版

| 分支 | 新改动 | 保持部分 |
| --- | --- | --- |
| adduct_extlib | 已下载V18的中性质量索引、adduct兼容、15ppm结构质量门槛及native身份提升，外加原官方身份guard | 原前32cell完全保留；不用Enveda |
| bestval_v80_tri | .50 Saner final＋.25原v2＋.25 popwenman best-validation | outsider仍原v2，原晚接入head、生成与AB保留 |
| bestval_saner_tri | .375 Saner final＋.375原v2＋.25 Saner best-validation | 同上 |
| generation_expand_r3 | 12谱母体、每母体最多60、总计300、双步保留、关闭额外同分异构化 | 原神经、physical/MASS、晚接入head及AB；最终使用revision3 |
| bestval_v80_adduct | 第一份独立checkpoint集成＋新版AB匹配组合 | 原生成、outsider及晚接入head |

组合位最终选为固定组合，取得同批单组件与组合的真实成绩；不假设两条分数可相加。当前完整冻结清单：[manifest_recovered](../submission/optimization_20261112/manifest_recovered.json)，SHA `08f87e64eca0894d1a3c6a0a4b4c0ec3c3652fdef540871acf402318a1355d24`。初版manifest及失败生成stage保留，不能再按初版重新调度失败分支。

## 权重纠错与指纹

原计划把公开V80 final当作新信息是错误的：其SHA与现用v2同为 `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`，原tri/dual两条配方因此取消，未消耗额度。

实际采用的独立权重：

- popwenman验证阶段best checkpoint：`f7e2383fe5fc0cc85e7333d308bc7201144574f2eef6b59000570d171e0758a7`。
- Saner验证阶段best checkpoint：`969d13443fcf168eae1e00e56a8e0ae87dcb16f337cb6dbac959e7cd218f089c`。

它们不是新训练结果，也不是作者完整三模型复现。popwenman模型来自显式kernel source `/1`；Saner模型来自原数据v1；均使用固定文件SHA、公共模型实现及兼容配置，不扫描并混用整个资产目录。作者声明的第三权重本轮读取仍403。

## 必要运行检查与边界

- 外库：真实完整AB共324884参考谱；模块16项、冻结入口20项通过，包含实际score消费、质量门槛、native候选提升、官方身份及坏payload保护。
- 新checkpoint：原scorer实际CPU处理3query/26谱/15候选；四个checkpoint均载入并产出finite分数，新权重与现用v2分数不同。冻结cell14/29/33的fast/hidden接口检查30项，独立源码核对60项通过。
- 生成：真实加载2,539,608谱及710,701结构池，对两个无truth/无排除的查询做部署小试。两查询均真实使用12母体；新增原生候选5/264，新生成数8/300，Engine前25中生成结构8/7。原始252特征按真实RK_FEATS选160列，投影及实际rank_score消费绑定；耗时2.46/8.50秒，不含初始化。
- 生成小试仅验证生成到实际ranker的通路，未重跑整套后处理；后续生产消费由原未变cell和最终审计绑定。它不构成Recall/MRR提升声明。
- 生成revision2真实检查7项、路由9项、独立源码检查38项通过。原始draft1错把V1FE原矩阵宽度要求为160，已保留失败原件，修正为选列投影检查；draft1未提交。
- revision2云端可见运行在最终audit报FileNotFound：本地夹具用`code`，真实Kaggle为`p2s_code`，38项检查未覆盖该布局差异。可见失败没有正式提交、没有消耗第五次额度。revision3仅修audit为实际`__file__`和同目录runner，并核launch路径；推理函数与runner均不变。真实`p2s_code`路径12项通过，复用既有实际运行产物检查hidden audit，不重新加载模型。新target、新branch和新manifest保留旧失败现场，见[修复记录](optimization_20261112/generation_r3_recovery.md)。
- 组合：原30个cell保持，另外三个改动位置与两单组件一致；独立26项、实际fast跨组件21项通过，坏audit/最终CSV不一致会拒绝产物。

证据位于本批目录的 `adduct_stage_canary.json`、`v80_bestval_frozen_entry.json`、`bestval_independent_review.json`、`generation_independent_review.json`、`combo_stage_canary.json`；详细运行产物路径见各报告。

## 正式提交与监控

精确编号以各分支submission.json为准，状态见 [执行回执](optimization_20261112/batch_dispatcher_status.json) 和 [最新榜分](optimization_20261112/latest_status.json)。可见运行明确是fast_static，正式code submission才触发隐藏完整推理；本地小试不等于已有榜分。

一条checkpoint版曾在云端产物读取阶段ReadTimeout；当时无submission claim、无output目录，根代理只读重做源/产物核验并通过后首次正式提交，没有重复push或重提未知结果。

控制器至多两个待完成Notebook，跨本批全部分支累计至多五个提交claim；21项离线状态机检查通过。提升记账只认固定源码/recipe、已接受编号、COMPLETE且无错误并严格超过当前最佳的官方分数；33项隔离检查通过。无新分前仍保留.488，Private收益不推断。
