# ozertuu V18 与本地 0.488 的源码比较（2026-11-11）

已下载并比较用户给定精确地址 `ozertuu/casmi26-dual-neural-physical-isomer` 的 V18：813,013 bytes，SHA256 `54ad16b546964a1044f07aa5229cd7ee81145882d73a83fda061923e9254adcd`。源文件在 `ozertuu_refresh_20261111T030240Z/0/source.ipynb`。旧的带 `0-500-` 前缀地址目前无法作为最新地址使用。API 的 public_score / best_score 均为 null；本文不把早先标题“0.500+”当作我们核实的提交成绩。

## 判断

值得保存和完整复现一版，但不宜直接替换当前0.488。它与我们的底层基座非常接近，主要新增价值是另一训练权重的互补可能、外库中性质量与adduct条件、已有候选身份别名升首，以及不同先验升首规则。并非换了一个新的大模型或新的分子生成器。它是否超过0.488需要我们自己的同资产复现榜分。

## 精确相同的基座

- 两份Notebook解码后的 FROZEN.ipynb 完全相同：373,731 bytes，SHA256 `d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88`。其E006入口均是 `EngineCfg(generate=True)`；没有把6母体改成12母体的新生成实验。
- `_physical`（12,857字节）、`_post`（13,264字节）、`_PUBLIC_RERANKER`（10,952字节）、`_RR8_FEATURES`（9,453字节）源码字符串逐字节相同。即物理碎裂打分本身并非V18新增。
- 两者均 `CUSTOM(w_top=.25,w_mid=.75,rescue=0)`，RRF offset=3；V18与我们都是 `V8='MASS'`，因此V18中内嵌的RR8模型没有执行。V18虽保留alpha=.25和额外冻结首选的RR源码，其当前效果为关闭。

## 神经集成算式和实际顺序

两者先在相同的frozen候选上神经打分，再按每个查询的候选分数做z标准化。我们固定且审计公开v1与v2：`S=.5*z(v1)+.5*z(v2)`。

V18扫描 `/kaggle/input/**/final_model.pt`，按路径排序，排除公共v1和kit目录。一个额外bundle时使用 `.5*z(public)+.5*z(extra0)`；至少两个时使用 `.5*z(public)+.25*z(extra0)+.25*z(extra1)`。它先运行所有额外bundle，但第三个之后的分数不进入最终算式，所以并非“所有可用模型等权集成”。metadata有 `popwenman/casmi26-scorer-train-v80`，另有两个空来源名；单靠此metadata不能确定实际extra0/extra1身份。

神经分数随后转为候选名次n：第一名由 `1/(3+b)+.25/(3+n)` 选择，余下由 `1/(3+b)+.75/(3+n)` 排序；再接物理碎裂、先验和质量规则。最后名单的分数不是简单的三个概率平均。

`run_public_pipeline()`不读取BUNDLE，底层生成器不因extra改变。`OURS_BUNDLE`取第一个extra，用于outside候选神经评分；outside分数不是上述多模型集成。这意味着新checkpoint还可能通过outside补位产生影响，不能仅改变最终神经均值就声称完整复现。

V18的额外bundle没有按SHA去重或明确固定身份；拷贝 `config_used.json` 后并不让scorer读取它，实际仍使用公共 `model.py/features.py/config.json`。因此要复现必须固定具体权重、确认架构和预处理兼容，并核对有没有重复权重；多挂几个文件本身不保证增益。

## 排序和末端差异

| 部分 | 我们已得0.488 | ozertuu V18 |
| --- | --- | --- |
| Documentation / spectral / NP先验 | .10 / .10 / .12 | .12 / .12 / .12 |
| spectral先验gate | .78 | .75 |
| 额外先验升首 | 无V18新增的两条条件 | 库命中+主神经前3支持升首；低库分时NP候选按margin升首 |
| learned RR8 | 关闭 | 关闭 |
| 自训练晚接入head | 固定前7，仅尾部同式槽位重排 | 没有我们的晚接入head |
| 外部实测谱 | Takumu + MassBank | 同样两库，未引入Enveda |
| 外库质量索引 | precursor，10ppm+.002 Da | neutral mass，12ppm+.002 Da |
| 外库结构质量门槛 | 旧函数未加新15ppm门槛 | 结构exact mass距query neutral mass≤15ppm |
| SMILES别名 | 旧0.488若提议产生官方身份重复则回退整条 | 可按身份提升已存在的原生候选 |

V18的外库cosine最低.80、至少4匹配峰、原库≥.90保护、fragment tolerance .015 Da，与我们旧AB机制相同；sqrt强度和贪心一对一峰匹配也相同。新处主要在匹配允许条件和输出身份处理，而不是新的谱相似网络。

我们今天第五条 `58222489` 已独立实现一个更窄的身份别名修复：仅旧AB guard拒绝且官方身份唯一已在候选时提升原生候选，保留全部0.488原33cell。它覆盖V18的一部分机制，尚未包含新中性质量/adduct匹配、15ppm门槛或额外checkpoint。

## 不能照着注释作结论的地方

- V18代码的formate兼容只接受formate别名之间；并未像注释所说允许formate与 `[M-H]-` 直接匹配。
- MassBank仍把所有exact_mass合成±H precursor，并没有使用真实Na等adduct逐谱纠偏，因此不能称已解决所有跨adduct问题。
- 通用extra发现、未知来源、宽松fallback与我们固定SHA的部署契约不同，应在复现中变为可审计的固定资产，不能默默少模型运行却仍叫同一配方。

## V13→V18的重要变化

不是仅补了安全断言：先验 `.10/.05/.02→.12/.12/.12`，gate `.87→.75`，NP margin `.040→.048`，`BOTH→MASS`（关闭RR8），最后加submission存在断言。多模型集成和adduct-aware外库代码未变。早先针对V13“弱先验+RR8”的结论不能套给最新V18。

## 后续复现顺序

1. 保存V18源码、固定全部附件/权重身份，检查额外权重兼容；代码已下载，无需用户手动搬库。
2. 额度恢复后保留一条完整V18复现，以获取我们自己的真实分数。
3. 在相同候选/当前0.488控制下分别检查新权重集成、外库质量/adduct过滤和先验升首；今天的A/B、Enveda和别名修复分数会帮助决定优先级。
4. 完整V18复现与“0.488接新组件”分开记账。只有真实超过当前最佳才登记新提升；标题或库内诊断不作榜分加法。

本报告只做源码、嵌入资产指纹与配置比较，没有新增GPU推理、训练或Kaggle提交。
