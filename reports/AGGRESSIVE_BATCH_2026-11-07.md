# 11月7日：四分支正式提交

14:39更新：四条均COMPLETE。dual_only **0.480**、tri_only **0.475**、public_MASS **0.481**、RRaggressive **0.436**，旧PENDING为历史记录。保留MASS作为0.481最高分；新V35与四优化已另批提交，见 `reports/AGGRESSIVE_BATCH_2026-11-07_PM.md`。

北京时间2026-11-07 00:48记录。用户授权主动使用每日额度、复现新公开配方并同时试多个修改版本。此前原始Flex V56为 **0.479**，完整公开tri V30实际为 **0.475**；后者没有带来提升，不能用48查询的正向诊断代替榜分。

## 已正式提交

| 配方 | 具体变化 | 提交编号 | 当前结果 |
| --- | --- | --- | --- |
| Flex dual only | 原V56骨架与低NP先验；神经分数改为0.5z(public)+0.5z(v2) | 58063780 | PENDING，无新分数 |
| Flex tri only | 原V56骨架与低NP先验；神经分数改为0.5z(public)+0.25z(v2)+0.25z(v4) | 58063822 | PENDING，无新分数 |
| Public MASS复现 | popwenman V2原MASS-only配方；保留双模型、NP/LOTUS、质量先验及首选质量修正规则，RR关闭 | 58063883 | PENDING，无新分数 |
| Flex RR aggressive | 原V56/public Saner及低NP先验，加102维异构体学习重排；alpha1.5、library gate0.95、预算2700秒；允许非train同式候选改变首选，质量先验关闭 | 58063870 | PENDING，无新分数 |

全部绑定不同私有离线Notebook **V1**，通过代码提交触发隐藏测试重跑；没有上传本地48查询CSV。前三个神经/公开配方的权重均已固定，第四条直接嵌入公开模型和特征源码，没有新训练。原始0.479源码和提交58021256仍独立保存。

Kaggle API开始时显示尚可提交4次；上述4次全部被接受，结束时 `num_today=5, num_total=6, num_allowed_now=0`。因此本轮使用当前实际剩余额度4次，不按本地日历误判还能再交一次。额度证据为 `reports/aggressive_batch_20261107/submission_allowance_after.json`。

## 新公开方案与权重证据

[popwenman 0.482标题分支](https://www.kaggle.com/code/popwenman/casmi26-0482-gold-apex-v22) V2的唯一实质配置差别是相对Roman V17将 `V8='BOTH'` 改成 `'MASS'`。目前尚未独立核实标题是否对应当前版本实际Public分数，复现成绩仍须以我们自己的正式提交为准。

Gold Apex V32、popwenman V32与Roman V17的全部代码cell相同，不能拆成多条独立公开方案占额度。Flex仍V61，已核对的历史最佳仍为V56的0.479。完整研究与源码路径见 `reports/RECENT_PUBLIC_BASELINES_2026-11-07.md`。

公开MASS原训练输出 `popwenman/casmi26-scorer-train-v80` V1可公开访问。其真正OURS checkpoint已下载到D并完整哈希，SHA `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`，与已有bgun v2字节一致；原生config仅output/work路径不同。本次用已证明等价的公共dataset、已有6个资产和LOTUS，复用已跑通的Docker；省略源码未使用的catalogue/额外wheel依赖。所有原代码cell文本原样保留，追加观察器。

## 检查与边界

- 双/三模型：各12项静态检查；3项离线保护测试覆盖fast不运行模型、精确融合、覆盖/候选错配拒绝。
- RR激进版：13项独立审查；真实CPU小型推理fixture产生3×102特征、模型3个有限预测；7项检查通过，包括候选集合守恒、首选可移动与训练结构冻结。仅是可运行性证明，不是准确率测量。
- 公开MASS：11项独立静态检查；fast/hidden合成观察器分别10/17项通过，原29cell源码和代码AST保持。
- 四个Save&Run均COMPLETE且无failure，服务器回读私有/离线/GPU/源码内容/数据源绑定通过；小型CSV和运行观察报告已下载核验，官方RDKit2026.03.3及400行ID/schema通过。
- **这次可见Save&Run均是fast_static，未在可见输入上执行新变体全模型。** 快速CSV只是格式占位，正式提交交的是云端代码V1，由Kaggle隐藏重跑。隐藏模式另校验实际全量流程、模型权重/覆盖/融合、质量层或RR执行，不能把静态审核说成已经跑通隐藏集或取得高分。
- 批量工具16项防重复/未知结果/目标绑定测试通过；每条push及submit均独占回执后只调用一次，未知结果不自动重试。

首次dual创建时Kaggle实际slug为 `stormseye/casmi26-flex-dual-neural-only`，与请求的1107 slug不同。通过私有/离线/源码/来源等10项只读检查确认同一V1后，回执保留原请求并记录actual_target；未重复push。其余三条title与请求slug一致。

## 查分与后续

只读监控每45秒检查四个固定编号，最长12小时，全部COMPLETE/ERROR即停止。实际进程37680已核对（启动器39784），日志无启动错误。最新机器状态：`reports/aggressive_batch_20261107/latest_status.json`。云端评分不依赖本地开机；关闭电脑会停止本地状态刷新。

下一批依真实榜分调整：双/三模型比较决定是否使用v4；公开MASS比较整体公开配方是否值得保留；激进RR比较独立结构评分能否带来首选收益。若出现提升，先固定该版本再安排邻近设置与跨路线融合；不把单次Public结果写成保证最终银牌。EXP003逐谱支持率保留准备结果，本轮优先处理已提交的四条路线。

配方、source、metadata、原始审查和SHA见 `submission/aggressive_20261107/manifest.json` 及各分支目录；正式提交和产物回执见 `reports/aggressive_batch_20261107/<branch>/`。所有下载、缓存、临时文件及新产物均在D盘。
