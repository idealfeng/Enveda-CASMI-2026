# 讨论区复查与下一实验

北京时间2026-11-08。由官方Kaggle SDK只读接口获取全部151个主题目录，选读21篇正文和全部返回评论（各篇最多4页×100评论，无篇触及截断）。采集时刻为2026-11-07 16:01–16:02 UTC，原文和SHA见`discussion_review_20261108/receipt.json`。网页工具对多数具体帖子仍返回空页/不可访问；本报告的主体依据是成功的官方API响应，不是第三方转述或仅凭标题。

## 已确认的失败结果

| 分支 | 实际Public | 处置 |
| --- | --- | --- |
| 旧公开MASS复现 | 0.481 | 保留完整部署源码与输入 |
| V35原版 | 0.469 | 不升级主线 |
| V35弱先验组 | 0.476 | 对V35有改善，未胜旧MASS；三项机制耦合 |
| V35加重v2 | 0.458 | 停止这组固定配比 |
| V35稳健质量 | 0.469 | 无显示分收益，不据此断言输出相同 |
| V35取消outside强插 | 0.469 | 无显示分收益，不据此断言输出相同 |

本次API重新逐ref读回，均COMPLETE且无error。V35修改了完整首选链：删去旧MASS最后的质量首选纠偏，放宽physical升首并新增NP升首，还改outside。不能将整套−0.012归到其中一项。保存旧0.481可避免后续实验同时更换未经支持的底座。

## 帖子里真正有用的内容

| 讨论 | 帖子内容及证据边界 | 对本项目的决定 |
| --- | --- | --- |
| [756504，新开源流水线，11/6](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/756504) | 作者自报Public 0.313；提供完整identity/analog/LambdaRank代码，提出同结构参考的跨仪器Class1模拟 | 学习验证接口，成绩不足以替换0.481；不机械采用其固定类别权重 |
| [752356，0.464基座三项对照](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/752356) | 作者自报depth7到0.456，gate+冻结生成到0.465，两项同交未分因；指出扩大forward覆盖比许多阈值更有价值 | 先审计实际有分候选，而非只看配置开关；扩池保持原候选统计稳定，并检验与排序的交互 |
| [743254，30次提交经验及追评](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743254) | 作者主要错误为同式异构体；评论者将同面板选出的+0.065重测为四库留出+0.023，均为他人实验 | 用真实第一阶段高分错误构建困难候选训练，按独立身份/来源评价；我们已有其四项MetFrag配置，不能再照抄当新增 |
| [748524，验证设计](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748524)及[748068，public谱丰富验证的偏差](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748068) | 评论者自报250NP与490无公开谱Enveda身份上的先验表现差异很大；类别配比与Public数量属于估计 | 未见身份/无公开谱层单列；已曝光48不再承担选融合器的主要依据；不按Public反推标签/类别比例训练 |
| [753400，反应规则生成负结果](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/753400)、[755089，图生成及能量实验](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/755089) | 他人本地生成命中与最终MRR差距大；图生成局部+0.006–.011但榜上无可见变化，气相能量未有效区分 | 不把MC枚举、手写反应或量子稳定性作为本月主攻；生成、过滤、排序要分开量 |
| [755965，五套公开镜像，11/5](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/755965) | 作者公开Enveda180、COCONUT、LOTUS、MassBank、GNPS S3；我们独立成功读取5份MIRROR.md，但未下载或复核全部镜像文件 | 有新的天然产物参考谱线索；先测相对现有库的新增身份/谱条件再选小增量，不全盘下载 |
| [753724，18M候选目录](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/753724) | 名称称预训练数据，正文实际是PubChem/COCONUT结构候选；未提供新增实验谱—结构对 | 对召回或许有用，不能当18M监督训练样本；当前已有大结构池，不优先重复扩库 |
| [756741，GNN正向预测，11/7](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/756741) | 作者自报true胜decoy约35%、主峰相似度约0.85，没有可归因的榜分增益 | 可研究结构条件，但“谱图看起来很像”不足以证明异构体排序能力，不据此更换基座 |

本次21篇中没有取得一个公开且被独立验证高于我们0.481的完整新配方。这个结论仅限定本次检索与可读帖子，不代表不存在更高私有方案。

## 已下载的有用源码与数据

- 新仓库[Majyles/kaggle-casmi-2026](https://github.com/Majyles/kaggle-casmi-2026)：`third_party/majyles_casmi_20261108/`，固定commit `26aa5c6097922fd3fade397ea9d011f909dcb4cc`，28个小源码/文档110995字节，逐Git blob及SHA256核对；没有执行或训练。其validation.py的参考屏蔽与分组接口可借鉴；身份语义仍需与本项目官方metric核对，不能直接信任字段名key。
- 五镜像小元数据：`discussion_review_20261108/s3_mirror_metadata/`，五个公开MIRROR.md均HTTP200。MD5 manifest是发布者的完整性声明，不自动证明我们已复核数据来源/逐记录许可/与train差异。
- Enveda180另一个已知Kaggle参考mirror：218514313字节谱parquet和116885字节aliases已实际下载D、完整SHA验证。它用于小增量与Saner未见身份候选审计；不能混同755965的另一Zenodo版本。全部730252谱不是新增。3720 aliases复算为3717官方身份，其中只有431身份关联1600张H+/H−参考谱，key错配0；这431是否真正不在官方train仍未独立证明。全表445722独特SMILES按实测吞吐约需58分钟，已停止本轮长作业，保存8192身份可续跑缓存。详见[实测与边界](external_reference_pilot_20261107/README.md)。

## 现在推进的实作

1. **固定0.481，查清forward实际覆盖。** 已对原Flex48诊断逐query核验：主25共1200行，按官方身份已有GL分1100行、ICE1125行；没有“送入且适用但运行漏分”。GL缺口中50行属2个adduct不适用query、25行属1个Na-only未送query、25行属后续才进入主榜的候选。更关键的是9个“真结构已召回但首选错误”的query，真结构全部已有GL和ICE分。因此现有证据不支持把补覆盖当作主要涨分来源，主投入仍是利用结构证据改善难例排序。此审计来自有模型曝光的旧Flex48，不是0.481隐藏MASS逐例输出。
   Na-only补评分输入另冻结12query/17谱和原ICE候选，11个原首选已正确、1个原rank8。GL实际加载代码接受Na，checkpoint可表示该adduct；其adduct行是固定编码，不能据此证明Na预训练数量/质量。一次本地推理已完成：1030原候选、1511逐谱分数全部finite，缺失/非有限0，1030均值重构最大误差5.55e−17，独立14/14检查通过。耗时102.74秒（加载75.22、预测21.23）、峰显存0.44GB，旧H+输入/输出SHA未改。只检验新信号可用性，没有重排、MRR评价、训练或正式提交。覆盖审计见`forward_coverage_20261108/summary.json`；推理和独立复核见`../runs/gl_na_probe_20261108/verification.json`。
2. **候选条件的多谱匹配头。** 原Saner已有同formula hard pool；新增训练从真实检索器top32错误候选挖负例，保留逐谱谱embedding×结构embedding交互和真实CE差异，按列表目标学习。冻结encoder先做500步吞吐/显存/梯度检查，再决定完整训练预算。当前未训练，不声称500步已有收益。
3. **有真实增量的参考谱。** 先完成官方train外身份核验，再按same-adduct/质量窗匹配并保持可追溯来源。未见身份可帮助Saner组件验证，但不能据此宣称ICE/GL整栈未见或天然产物泛化已被证明。

每日5次是可用提交上限。成果可以研发数天后再提交；已确认基线无需每天重复交，同一方法也无需拆成五个微小参数变体。下一次提交应带来新的结构证据、训练目标或独立错误来源，并保留可解释对照。
