# 11月7日下午：V35公开基线与四项优化

11/8最终结果更新：五条均COMPLETE且无error，原V35 **0.469**、弱先验 **0.476**、v2加权 **0.458**、稳健质量 **0.469**、取消outside强插 **0.469**。本批全部低于旧MASS **0.481**，停止将V35作为研发默认底座。以下PENDING为提交当时历史状态；只读监控已在11/7 19:56北京时间全部终态后退出。新的讨论与机制结论见[11/8研究](DISCUSSION_RESEARCH_2026-11-08.md)。

北京时间2026-11-07 14:58记录。用户要求继续搜索更高公开方案，分析真实提升来源，并使用每日5次额度同时提交基线和优化版本。本轮五条正式提交已全部被接受，当前PENDING、没有新分数；旧最高0.481独立保留。

## 先确认已有结果

| 已完成配方 | 提交编号 | API确认Public |
| --- | --- | ---: |
| 原始Flex V56 | 58021256 | 0.479 |
| V56双神经 | 58063780 | 0.480 |
| V56三神经 | 58063822 | 0.475 |
| 公开MASS整套配方 | 58063883 | **0.481** |
| V56激进学习RR | 58063870 | 0.436 |

用户截图显示0.481/第131名，API独立确认了分数；名次属于截图时刻的观察。本地旧watcher停留在PENDING已更正为正式读回结果，不能拿旧状态文件当最新线上结果。

可识别的正增益是原V56换用public/v2双模型后显示增加0.001；三模型使用v4替掉一半v2份额后减少0.005，强RR相对V56减少0.043，均暂停投入该具体配方。0.481相对dual-only多出的0.001还混有质量项、NP/SPEC/LOTUS、library gate与outsider差异，不能全归因于质量校准。详见 `reports/ROUND2_ATTRIBUTION_2026-11-07.md`。

## 最新公开代码

下午再次查询官方scoreDescending/dateRun各100条并拉取17份候选源码快照。没有找到可独立核实当前版本真实分数高于0.481的新公开页面，但找到实质更新的[Gold Apex V35](https://www.kaggle.com/code/zz3t3rn41/casmi26-peaks-to-structures-v2)。其SHA为`759067bc1449427089e95b811ee49f866580590905484577fe09a143740a2842`。新Alex V11及多个克隆代码与已得0.481的MASS配方相同，未重复占额度。

V35改变了逐谱物理投票与首选判据、outsider双模型融合、质量惩罚接入位置，增加弱库NP首选promotion，以及把4个outside候选强行插入rank8/14/20/24。最后一项会改变top25候选集合，可能提高召回，也可能挤走正确答案。V35并非旧0.481配方的别名，必须重新取得自己的分数。完整搜索见 `reports/RECENT_PUBLIC_BASELINES_2026-11-07_PM.md`。

## 本轮实际提交

| 分支 | 相对V35的变化 | 正式提交 | 当前状态 |
| --- | --- | --- | --- |
| v35_baseline | 公开V35原评分代码与配置不变 | **58082815** | PENDING |
| v35_weak_prior | SPEC .10→.05、NP .12→.02、library gate .78→.87 | **58082822** | PENDING |
| v35_v2_emphasis | public/v2改为.25/.75；主候选与outsider四个分值列一致修改 | **58082871** | PENDING |
| v35_robust_mass | 从每分子首张谱nm改为全部effective谱nm中位数；raw10adduct仅补缺失 | **58082895** | PENDING |
| v35_no_interleave | 仅关闭4个outside强插槽；保留原空槽补位与LOTUS补位 | **58082938** | PENDING |

五条均为不同私有离线Notebook **V1**，原public/v2权重与LOTUS继续固定。原0.481提交58063883与代码未改动。每条只发送一次code-submit，不上传本地48查询CSV；网络结果未知时禁止自动重试。

弱先验版同时改变library gate，故不仅影响NP/SPEC数值，也会改变promotion和outside强插的适用范围；它是一个先验配方对照，不能称单独NP消融。稳健质量版保持原每谱中性质量常数，仅改变主聚合；原V35已覆盖10种adduct，没有把“补脱水”空改算作优化。相同分子式的异构体exact mass相同，质量项主要作用于不同式近质量候选，不宣称它能独立区分同式连接结构。

## 已完成的部署检查

- 五版只修改计划内的cell；baseline所有原评分cell文本保持。全部代码编译及原权重/配置/LOTUS、私有离线、版本源绑定通过。
- 独立审查：baseline13/13、弱先验14/14、最终v2版15/15、质量中位数13/13、关闭强插15/15；全部实际observer的fast/hidden合成场景通过，主分数错误会被拒绝。
- 质量聚合代码另6/6边界检查：保留effective优先、偶数中位数、行顺序不变、raw只补缺、脱水加合物、无效值排除。
- 五个云端Save&Run均COMPLETE无failure，服务器源码内容/来源和小型CSV/观察器报告均已回读核验。
- **可见运行是fast_static，没有对新变体执行完整模型推理。** CSV为格式占位；正式提交绑定云V1后，Kaggle在隐藏输入上执行完整流程。隐藏观察器校验400查询范围、真实主模型覆盖和融合、最终merge与稳健质量分支执行。outsider保留原作者可选time guard/fallback，仅记录可选回退，不假称每个可选阶段都已执行。

审查报告：`reports/round2_independent_review_20261107_pm_final.json`。原始配方/source/metadata/hash：`submission/aggressive_20261107_pm/manifest.json`及五个分支目录。原先两个未部署草稿保留作历史，不在五条manifest中，未被提交。

## 额度与监控

开始官方API为num_today0/num_total6/num_allowed_now5；结束为 **5/11/0**，本轮5次全部使用。额度证据：`reports/aggressive_batch_20261107_pm/submission_allowance_after.json`。

只读监控已启动并核对实际进程 **24376**（启动器23264），每45秒查询五个固定正整数编号，最长12小时，全部COMPLETE/ERROR即停；stderr无启动错误。最新状态：`reports/aggressive_batch_20261107_pm/latest_status.json`。监控以旧0.481为保留基线，显示本批最高分和总体最高分；不自动推送新Notebook或提交。关机只停止本地状态刷新，不影响Kaggle已接受的云端评分。

## 后续不同增益来源

合法通用外部参考增量值得单独试验：[主办讨论745148](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/745148)允许使用Enveda-180；公开mirror `egehseyinca/enveda180-casmi26-reference-ccby4/1`可直接挂载，约218MB、730252张H+/H−参考谱。已用小文件和55KB footer核查来源/许可/schema，但大部分可能与train重合；3717个source-only结构目录也不代表3717个可匹配新谱身份或隐藏命中。

下一步先审计官方评分身份、结构池覆盖和精确/近重复，再以same-adduct、质量窗和参考相似度做独立overlay；参考包没有CE字段，不能直接用于跨CE一致性投票。尚未下载完整谱库、实现matching overlay或声称涨分。详见 `reports/EXTERNAL_REFERENCE_INCREMENT_2026-11-07_PM.md`。本轮所有新增下载、缓存、临时文件和产物均在D盘。
