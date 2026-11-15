# 11/14讨论与最新公开代码复核：下一轮优先级

结论：近期检索未核实一套资产完整、可直接复现且真实榜分已超过我们.488的新公开整版。真正值得投入的是新实测谱信息和独立指纹基座，而不是继续重排同一批旧分数。本次取回完整160条论坛标题清单、16个相关帖全文及评论，并检查6份最新公开Notebook源码。标题、作者自报、局部代理与我们正式榜分严格分开。

## 当前结果先对账

今日五版已全部正式接受：head 58334939、mean 58341597、GL 58335002、dual 58335047、library 58341606。最后两版曾排队，现在已接受。22:08北京时间官方只读清单中，head=.470、GL=.481、dual=.449，均COMPLETE无error；mean与library尚PENDING。最佳仍.488。[原始读回](latest_our_scores.json)。

这三份负向实测不支持扩大当前固定评分器的干预范围；停止当前head prefix1、GL全局标准化融合和双模型pairwise升首配方。不能据此证明全部排序学习或全部GL/ICE模型无用，也不能在尚无结果时判另外两份失败。11/13整体生成扩展.473、其余四版.488也仍是已确认反证，不猜三位小数之外的微小提升。

## 具体发现

| 来源 | 核实到什么 | 与当前.488的区别 | 决策 |
| --- | --- | --- | --- |
| [ozertuu最新V45](https://www.kaggle.com/code/ozertuu/0-500-casmi26-dual-neural-physical-isomer) | 源码标题区把0.500+称目标，Verified Baseline=.487；最新名已变，旧slug404不是新方案消失 | 仍是原同系评分/先验、MASS和旧RR8接法；没有确认新的可读第三权重。公开V80 final与当前v2相同 | 不能宣称公开已达.500，暂不把该标题当升级基座 |
| [Helios 0.489 V2](https://www.kaggle.com/code/heliosli/casmi26-0-489) | 有FRIGID解码器/E1预测/rr3碎片模块，但附件有空数据源，所需runner、checkpoint及配置未齐 | 存在不同组件；暂不能完整复现，标题不是我们的已验证分数 | 保留源码，只有附件可追踪后再排整版 |
| [WSP V5](https://www.kaggle.com/code/kingdamon/casmi26-wsp-dual-encoder-inference) | 新Conv1D谱编码器＋指纹编码器；训练Notebook403、注册模型搜索未找到可用权重；原推理候选列/分隔符/多谱索引不符CASMI，并允许缺权重时不生效 | 架构不同但当前资产/接口不完整 | 不把“代码运行了但模型没用上”当新基座复现，低于MIST优先级 |
| [extlib2 v1](https://www.kaggle.com/datasets/nakhun/casmi26-extlib2)，由[zz3 V55](https://www.kaggle.com/code/zz3t3rn41/casmi26-peaks-to-structures-v2)挂载 | 7文件共128,947,012B；提供者汇总490,840谱、62,782结构，GNPS2/MassBank/MSnLib，含123,995条[M-H]-和1,430条Na谱 | 可能提供当前AB与训练谱未覆盖的实测参考，是真实新增资产候选；重叠率尚未算 | 近期首选受控实验。先下载与谱级/结构级去重、来源核对、再评新增命中；作者offline_eval不当榜分证据 |
| [MIST许可讨论757307](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/757307) | 11/11主持人明确MassSpecGym和MIST可以使用；指向MSG real-only checkpoint | 新72.3M参数化学分子式Transformer、4096位Morgan指纹，当前public/v2未接入 | 中期主线，先做输入适配及固定候选真实推理，不先盲目全量训练 |

上述.500/.489标题都未被本次公开API元数据转化成可核实的更高正式分数。新谱库约49万行也不等于49万条相对当前系统的新增谱：GNPS、MassBank、MSnLib与官方train很可能部分重叠。必须衡量去重后的实际净增，避免再次把覆盖数字当分数。

## 讨论里真正有用的机制证据

- [758541，11/12](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/758541)：作者报告库加分在有真结构参考的面板很强，去掉真结构参考后明显负向，高余弦错误异构体会让固定bonus误升首。这是作者单管线结果，能解释风险，不能把其幅度套给我们。
- [748524验证讨论](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748524)：区分参考真正存在与缺失、仪器/多谱分布、MSG预训练曝光。我们复用现有validation与已完成produre基础，不重跑两套任务；新模型的开发集需排除其预训练结构曝光。
- [743254经验帖](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743254)：候选中有答案时，同式异构体是作者的主要排错难点；结构相关碎片证据可取，但并非所有碎片特征都新。E006已有碎片相关特征，不能把公开“1–2键切割”本身称我们尚无的独立信号。
- [755089，11/13新回复](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/755089)：作者从随机图枚举转到生物合成动作X+M→Y，但没有公布新LB数字或可复现代码。不据此重启已经.473的盲目扩大母体/产物预算。

完整日期、作者、原文SHA及已删除话题状态在[论坛报告](forum_review.md)；749217官方DreaMS/GLACIER/ICEBERG说明是10月旧回复，不能写成本周刚出台的新政策。

## 接下来按此推进

1. **保留.488冠军。先检查extlib2实测增量。** 固定原控制，核来源及结构/谱级重复，记录新增可匹配谱、正确身份与错误异构体两类行为；使用既有验证框架，不在官方可见测试上估计涨分。只在实测确有新增证据时接到原管线，避免覆盖已有强命中。库包公开下载不等于已完成运行或被正式采用。
2. **接MIST，初始只用MSG real-only。** 第一方[源码](https://github.com/coleygroup/MIST)已固定commit到D盘；[Zenodo](https://zenodo.org/records/23303289)该checkpoint约289MB，尚未下载或运行。它需要候选分子式条件输入，而隐藏test没有分子式；必须按当前候选的分子式组生成特征，不使用目标标签。初始只适配支持的正离子，负离子回退原控制，重新生成4096位候选指纹，不混用旧2048维。先两query实际输入到输出，再查与原分数是否互补。[详细可行性](mist_feasibility.md)。
3. **训练目标转为同式困难负例排序及证据适用性。** 固定候选、用真实top错误异构体作hard negatives，学习MIST/原神经/碎片/实测谱何时可信；区分参考存在与缺失。候选新特征先证明能纠错，再做新训练，若需微调仍先500步测速；不继续任意z-score加权或同系checkpoint扫比例。

这是后续优化路线，不是涨分承诺。当前已完成的是讨论/源码/来源可行性核查；没有把新模型实际推理、干净验证、完整隐藏运行或新高榜分写成已完成。所有资料、源码和新下载均在D盘，旧冻结产物和produre原件未改动。

资产交付更新：extlib2 v1已完整下载到`assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2/`，7文件合计128,947,012B，逐文件大小和SHA记录在[下载回执](notebooks/extlib2_download_receipt.json)。压缩包85,758,662B，SHA `4c250e691c06ed72bd22eadeec449279ebf89f933f82e67125d0ed96fe68401c`。没有加载数组、模型或运行库代码；下载完整不等于净增覆盖已成立或已用于提交。MIST源代码49文件约365KB固定commit `48e339be6535546c87ba4f6b81a0f787c2e4ac40`，约289MB模型仅记录官方制品信息，未下载/推理。下一轮可以从这些已到位的资产继续，不需用户手动搬库。
