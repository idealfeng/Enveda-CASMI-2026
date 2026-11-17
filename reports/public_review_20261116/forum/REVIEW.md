# 11/16最新讨论区复核

核查时间：2026-11-16 15:18 UTC（北京时间23:18）。本轮通过官方只读SDK取得全部 **163个主题** 的标题/时间/评论数，并读取 **15个主题及其完整分页评论**；均未触及400顶层评论上限、未截断。与11/14的160条全量快照相比，新增3帖、6个旧帖有新回复或内容计数变动。没有发帖、回复、提交或启动云端任务。所有新快照在D盘。

**在本轮新增主题与变动讨论中，未发现提供资产完整源码、且可核实超过我们.488的新整版。** 这是讨论区范围结论；独立Notebook扫描仍可能发现新公开方案，不能据此宣称全站没有更强公开代码。

## 最近新增的3个主题

| 主题 | 时间/作者 | 实际内容 | 对复现选择的意义 |
| --- | --- | --- | --- |
| [759307，SpectralHybridEncoder](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/759307) | 11/14 20:49 UTC，Arsenii Shabrov Nikolaevich | 作者自报Public .057→.089；32峰、峰差、120k同InChiKey14谱对、CLIP式对比目标、精确adduct及多谱汇总。新Div/Mul链与元数据调制结构 | 是新架构线索，分数明显低于.488，不能作为更强整版替换。目标为训练谱检索，作者本人仍在询问如何结合结构候选/指纹。提供[Notebook固定版本369654565](https://www.kaggle.com/code/arsenii228/notebook4e97b36fc1?scriptVersionId=369654565)，未核实其权重/训练工件，本次未据帖启动复现或提交 |
| [759398，Notebook队列](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/759398) | 11/15 10:53 UTC | GPU可用但Notebook排队 | 运行平台问题，无更高方案/模型 |
| [759394，提交排队6天](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/759394) | 11/15 10:22 UTC | 用户报告排队；其他用户回复称故障日请求已退还额度 | 回复不是官方对我们提交的状态/额度答复；按我们的API读回判断，不据此重复提交 |

以上分数为论坛作者自报，不是我们账号复现成绩，也未由本轮元数据绑定成正式评分。

## 旧帖的新回复

- [756893，可再生成中间产物/权重](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/756893)：**11/16 00:52 UTC，主持人David Healey** 新回复明确，公开权重需要能由公开训练代码与允许数据再生成，仅声明训练自`train.parquet`不足。11/14追问提及常见双engine的FPNet/LightGBM等具体资产，但新回复是一般原则，**不是逐个资产的违规裁决**。对于新候选，除能下载权重，还应保留训练代码/数据来源链；不据该帖自动将当前所有历史方案标为违规或停止已授权工作。原始新评论ID3555495，内容和时间见`756893.json`。
- [757307，MassSpecGym/MIST](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/757307)：**11/16 00:53 UTC，同一主持人** 新回复允许GNPS里的GNPS-NIST14-MATCHES；API原文末尾有残缺（止于`as`），不自行补全。11/11允许MSG/MIST的旧答复仍在。不能扩成NIST训练模型普遍允许，也不是MIST新权重或新榜分；我们11/15已经实测当前MIST release近恒定指纹，本帖不推翻该工程反证。
- [755039，Private类分布](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/755039)：新增一般评论，仍没有CASMI隐藏Class3比例数据或可复现高分方法。历史比赛经验与分布推测不当作本比赛事实。
- [755319，fork讨论](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/755319)：新回复讨论Class2/3难点和fork现象，没有新增具体模型/权重/高分代码链接，不作为复现来源。
- [750330，外部数据许可](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/750330)：库存显示11/15新增2条评论，但内容API只返回ID/日期和一条嵌套回复，没有可读作者/正文；可能是删除或不可读占位，**无法从其元数据推断任何新政策**。主帖10/17的旧许可说明不是本周新变化。
- [759222，未成年参赛](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/759222)：与算法/复现无关。

另重新读取743254、748524、756504、755089、758541、749217这些技术/验证锚点；未见相对11/14库存有新增评论，旧.313基线、生成动作猜想、MIST方向不包装为新发现，也不重新跑已完成produre1/2。

## 复现选择

讨论区没有提供值得取代.488的已核实新整版。下一步应把本报告与本轮**Notebook源代码及真实评分元数据扫描**合并判断：找到更强、资产完整的候选再拉取/复现和单因素优化；若只有标题目标分或缺权重，明确列出边界。不得把.089架构帖、许可新回复、Class3猜测或“有很多fork”当作更高公开基线证据。

证据：`inventory.json`全163主题；`delta.json`相对11/14差异及15个读取ID；`receipt.json`逐帖状态、文本SHA及分页未截断标志；每个主题的JSON保存完整HTML/时间/回复结构，TXT便于阅读。扫描脚本为`scripts/review_forum_latest_20261116.py`。原11/14报告及冻结资产未修改。
