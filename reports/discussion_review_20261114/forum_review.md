# 11/14讨论区实读：没有发现可直接替换.488的新完整高分方案

范围：官方只读SDK取全160个比赛主题，读取16个相关主题及其完整分页评论（每帖最多400个顶层评论，均未截断），并核对MIST和公开干净基线的第一方仓库。没有发帖、没有运行外部代码、没有提交、没有下载新模型。所有证据在本目录`forum/`。

11/9旧清单154条，本次160条；新增7个ID，旧757152已删除，净增6。新增主题主要是验证、数据卡、许可和可复现性问题；未找到近五天发布、给出可复现代码且已验证超过我们.488的完整公开方案。此判断只限已读取讨论，不等于所有Notebook或私有方案都没有进展。论坛作者的LB数字均属作者自报，不是我们账号的正式成绩。

## 最值得采取的三个方向

| 优先级 | 论坛证据 | 与当前做法的区别 | 建议动作及边界 |
| --- | --- | --- | --- |
| 1 | [MIST/MSG允许使用](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/757307)：David Healey在11/11明确答复；[模型源](https://zenodo.org/records/23303289)、[代码](https://github.com/coleygroup/MIST)可核验 | Formula Transformer预测结构指纹，是不同的信息通道；不是重新加权现用Saner/v2或再次加同系checkpoint | 先只取`mist_msg_noaug.ckpt`，289.2MB，MSG真实谱训练；先SHA与现有模型去重，再看能否纠正固定候选内的同式错误。没有证据保证加到.488会涨分；不要顺手下载16GB全包或把CANOPUS/aug权重视为相同许可来源 |
| 2 | [验证策略](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748524)及[30次提交经验](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743254)：已召回错误多为同式结构区别，碎裂证据有效但组合后收益会缩小 | 当前固定GL/ICE分数融合改变早位，尚未学习何时信任或忽略某项证据；同式困难负例训练比继续全局固定权重更贴问题 | 保留.488召回与候选，复用现有验证框架建立结构隔离的困难同式组，训练分组ranker/小校准层，按分子配对比较；不是重跑produre1/2。作者报告的S2局部提升与LB增量不能当作我们基座的预期增益 |
| 3 | [可复现开源pipeline](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/756504)指出Class1应跨仪器模拟；[11/12本地验证新贴](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/758541)指出错异构体也可有高cosine | 原库cosine高不必然应保护整行；但取消保护、固定提高GL/库权重也可能伤害。需要对证据的适用条件建模 | 训练/验证时隔离整结构和仪器族，加入真结构不在参考库的对照，校准“有真实参考”和“只有相似异构体”两类证据。0.313开源基线适合借验证/训练设计，不能当更强基线整体替换.488 |

## 新评论实际说了什么

- **758541，11/12**：作者Sophie自报基线.367。加库在公开NP面板很好，但删掉真结构后会伤排序；她报告一部分NP能找到高cosine错误异构体。增大模拟谱权重、库bonus和固定PubChem插槽均未提升该作者LB。这是解释“本地有信号却无法直接堆到榜上”的反例，不是GL或外库信息全无用的证明。
- **755089，11/13新回复**：作者从随机保持分子式的MC重接键，转向羟化、甲基化、糖基化/水解等生物合成动作，使用查询谱、母体参考谱及分子式判断`X+M→Y`。作者称比MC更好，但未给新LB数字、训练代码或可复现模型。保留为独立生成研发线索，不据此再次扩母体或马上重跑produre实验。主帖的随机生成和量子稳定性筛选尚无可见LB收益。
- **756504，11/12新回复**：Yohann Roux明确其已公开.313方案不处理Class3；只删除目标分子不足以模拟真库外，邻近结构也应隔离。这套干净基线更适合作参考训练/验证工具。[仓库](https://github.com/Majyles/kaggle-casmi-2026)公开，但不是更强整版。
- **757307**：11/11主持人明确允许MassSpecGym和MIST；11/13后续只是追问GNPS-NIST14谱是否在比赛GNPS中，不能把它写成新模型的实榜验证。
- **756893**：11/11主持人强调不可复现的中间产物不算可复现；11/14新评论询问常用两个engine的FPNet/LightGBM权重是否有训练代码，未获针对这些具体权重的答复。此处只是记录事实，不把未回答扩成已判违规，也不据此打断当前任务。
- **749217**：DreaMS官方base及官方MSG版GLACIER/ICEBERG的允许答复实际在10/14–10/16，不是本周新政策。第三方无训练配方微调不自动继承base的允许结论。现有未经说明FRNet/第三方微调不能因名称或title视作新强基座。

## MIST第一方核验

[Zenodo记录23303289](https://zenodo.org/records/23303289)发布于2026-10-20，作者Hongxuan Liu，是MIST更新实现的资源包。描述明确区分MSG/CANOPUS与synthetic augmented/noaug；`mist_msg_noaug.ckpt`为289.2MB，MD5 `80594e4dfd82d15fb32a3b186e686b6b`，MSG compact特征15.7MB。`noaug`指不用合成谱，不代表完全不用随机正则。模型是推理checkpoint，不是完整训练恢复状态。

[代码仓库](https://github.com/coleygroup/MIST)明示72.3M参数、4096-bit Morgan(radius2，无手性)、formula-aware attention，提供训练、DDP、BF16、EMA及下载校验入口。它是一个具体可试的独立基座方向，不是已确认能超过.488的方案；真实部署前仍须检查模型/特征兼容与同结构曝光边界。第一方描述没有给CASMI LB成绩。

## 本次未发现的东西

- 没有从最近新增主题中找到可直接拉取、官方证明超过.488的完整方案。
- 没有找到“再加GL/ICE权重”“扩母体”“多加库”在同等.488父版本上稳定提升的证据。
- 没有看到可靠的微小LB小数改善解释；公开数据相关数量、类别比例与LB大小均可能是作者推测，不作为主办方公开事实。

结论：主线应从继续手调冻结分数，转向**独立MIST指纹信息＋针对同式困难负例的学习排序/证据校准**；生成改动只保留有机制的新生物合成动作研究。五次名额仍可探索，但模型训练和新信息应是主要投入。所有建议都是从论坛证据做出的工程判断，尚未在我们的固定.488父版本证实。

证据索引：`forum/inventory.json`为160条全量清单；`forum/receipt.json`、`forum/additional_receipt.json`绑定本次已读取主题，原始JSON保留发布时间、评论时间及回复结构，TXT为便于阅读的去HTML文本。`forum_delta.json`列出与11/9的差别。
