# MIST msg-noaug：新基座可行性与输入边界

状态：已固定官方源码和制品清单；未下载权重、未安装、未执行新源码、未训练、未推理、未提交。所有产物在D盘。它提供与现有公共/v2编码器不同的公式Transformer信号，值得下一步小样本接入，但不是可直接照搬的完整高分方案，亦无本队榜分。

## 来源与指纹

- 主办方对具体MIST/MassSpecGym问题的答复见[讨论757307](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/757307)。该批准针对该讨论中的公开来源，不应扩为任意第三方微调都已获批。
- 官方代码：[coleygroup/MIST](https://github.com/coleygroup/MIST)，已固定commit `48e339be6535546c87ba4f6b81a0f787c2e4ac40`。本地[源码](../../assets/research/mist_msg_20261114/source/README.md)、MIT [LICENSE](../../assets/research/mist_msg_20261114/source/LICENSE.md)及[上游NOTICE](../../assets/research/mist_msg_20261114/source/NOTICE.md)已保存。
- 下载49个相关源码/配置/文档共364,746字节，另补1,071字节上游MIT许可；没有运行任何源码。[逐文件SHA回执](mist/download_receipt.json)、[附加许可回执](mist/license_notice_receipt.json)。
- [Zenodo23303289](https://zenodo.org/records/23303289)制品清单已保存：[API元数据](mist/zenodo_record.json)。`mist_msg_noaug.ckpt`为289,222,619字节，Zenodo MD5 `80594e4dfd82d15fb32a3b186e686b6b`；官方代码catalog给出的预期SHA256为`6f8df582df36aa4a984f120efee14ee0a62f3a7723caa770b856a6e704236727`。尚未下载，不能把预期SHA当成本地核验SHA。
- `msg_compact.tar.gz`约15.7MB；完整合集16GB并非推理必需。首轮无需下载合成12.1GB数据或其他模型。

## 实际不同的模型和训练

[msg-noaug配置](../../assets/research/mist_msg_20261114/source/configs/noaug/msg.yaml)明确从头训练、只读MSG真实训练cache，验证选模，无合成谱；72,296,996参数，1024隐藏宽度、4层峰注意力、16头、4层迭代修正，输出4096位Morgan radius2、无手性指纹。`noaug`仅表示没有合成谱，不表示取消峰丢弃/强度扰动。此处只核源码配置，尚未核实checkpoint内部张量和配置。

它不是Saner/v2同系checkpoint替换，也不是GL/ICE聚合分数再调权；先用现成预训练推理，无须先训练500步。

## 接入必须解决的问题

1. **先验分子式是必需输入。** 文档与`assign_subformulae`都要求precursor formula，输入token是碎片元素计数、adduct、强度及仪器类别。隐藏test没有分子式，不能从真结构取公式。可对固定候选集合中的每个不同公式单独构造同一query的输入，使用候选公式条件化推理，并且只比较该公式组中的候选。它是显式候选条件信号，不能伪称完全无条件谱编码；不能先用真值公式只保留正确组。
2. **当前词表只有正离子。** `chem_utils.ION_LST`支持H、Na、K、一次/两次失水H、NH4和裸正离子。CASMI `[M+NH4]+`需明确映射到上游`[M+H3N+H]+`，`[M-2H2O+H]+`需映射到`[M-H4O2+H]+`，另外四种CASMI正adduct可直接对应。没有任何负离子词项；负离子query必须保留原基线，不能假装映射成H+。
3. **timsTOF类别未直接列出。** 上游仪器映射中的未知名称默认unknown，Bruker Q-ToF映射qtof。先保留模型支持的unknown或明确比较后冻结QTOF映射，不能悄悄假设同一类别。此为分布兼容问题，不代表代码不能运行。
4. **不能复用现有2048位候选缓存。** 应按官方定义生成4096位Morgan2、无手性指纹；如果使用打包cache，bitorder为little。谱概率与候选指纹的相似度/损失也需明确，先固定一个规则，不能混用原embedding cosine与指纹Tanimoto。
5. **官方CLI不是任意CASMI输入入口。** `input_signal.py`要求canonical MSG/CANOPUS真实cache且检查checkpoint数据集名。应写诚实的CASMI薄适配器复用模型/张量契约，并分别记录训练源MSG和实际输入CASMI；不能把CASMI缓存冒称MSG以绕检查。预测路径不需读取target fingerprint或结构标签。
6. **CPU特征构造需测速和限制。** `_heavy_formula_space`枚举根公式重元素计数组合，随后做ppm子公式分配；大公式可能使CPU时间/内存增长。先限制候选公式组数量，记录分配失败和无信息输入，不能默默给失败query有效神经分数。

## 最小可执行下一步（尚未执行）

1. 只下载官方`msg-noaug`289MB并核上述双校验；不训练、不拉全数据集，固定checkpoint/config及源码commit。按新文件内容SHA登记模型，而非仅按名字判新模型。
2. 从已有生产小样本选择两条具正离子谱的query，输入白名单仅官方谱列；冻结原候选列表和所有候选公式。逐公式构造子公式/CLS/adduct张量，记录所用候选公式和失败原因，先不读真结构或算MRR。
3. 小批前向输出有限4096概率，记录CPU特征耗时、GPU峰值、score覆盖；按既定规则对同式候选打分，检查官方身份、多重集合和fallback行为。负离子或无支持输入精确保留原列表。
4. 上述只证明部署/信号变化。有效性需复用已有validation基础，在固定候选的同式hard-negative上评估；对MSG预训练数据的曝光作独立排除，不重做produre1/2。MSG训练/选模身份未排除之前，旧面板收益不能宣称泛化。保留“真结构有参考”和“真结构无参考”的对照，防止仅改善已公开谱查询。

预计需要编写输入适配、候选指纹、评分/聚合和审计四部分；具体耗时应由首次两query测速决定，当前没有推理或训练实测时间。是否值得融入.488由独立成对收益决定，不因模型新或有官方许可就直接期待涨分。
