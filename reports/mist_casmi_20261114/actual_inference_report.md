# MIST CASMI适配：真实预训练推理已完成

状态：完成官方权重双校验、原模型严格加载、两题组件推理及17条冻结候选推理。没有新训练、没有Kaggle提交。本报告只说明执行和覆盖，效益由主控另行读取标签评价，不在本组件内计算。

## 模型与输入

官方`mist_msg_noaug.ckpt`下载至`assets/research/mist_msg_20261114/checkpoints/`，289,222,619字节，SHA256 `6f8df582df36aa4a984f120efee14ee0a62f3a7723caa770b856a6e704236727`、MD5 `80594e4dfd82d15fb32a3b186e686b6b`均匹配，下载179秒。[下载回执](checkpoint_download_receipt.json)。

固定原源码commit `48e339be6535546c87ba4f6b81a0f787c2e4ac40`未改动。实际checkpoint用`weights_only=True`加载，85个EMA张量键、72,296,996参数，`strict=True`无missing/unexpected key；内部配置确认`msg_all`和`synthetic_training=false`。[实际checkpoint元数据](../../runs/mist_casmi_20261114/actual_checkpoint_metadata.json)。

新增[CASMI适配器](../../scripts/mist_casmi_adapter_20261114.py)独立于上游CLI，明确区分模型训练源MSG与实际输入CASMI。每个不同候选公式构造谱条件输入，最多取原列表首现的三个公式组，不用真值公式；匹配precursor、原始20ppm子公式分配和10个碎片+CLS，4096位无手性Morgan2候选指纹，逐谱模型概率均值后固定soft Tanimoto评分。仅同式有分候选原槽位排序，原始候选多重集合不变。负离子和无支持输入保留原列表，不伪造神经分数。

输入仅官方12列，未打开标签列或truth指纹。两种拼写alias明确映射NH4与双失水正离子，仪器保留上游unknown默认；不将负离子冒充H+。现有环境缺h5py，适配器从已锁SHA的上游featurizers只取三个不依赖HDF5的原始函数，未改函数体、未安装新依赖，模型本体仍直接导入冻结源码。

## 两query真实组件

[完整verification](../../runs/mist_casmi_20261114/verification.json)：20谱、4个候选公式组、22个实际正离子谱/公式输入；14个负离子/unsupported事件被排除。44/50候选有分，概率全部有限且维度4096，2条首选均变化。不计算准确率/MRR，此输入来自旧生成扩展版的两题中间产物，不能当精确.488验证。

| 实测阶段/资源 | 数值 |
| --- | --- |
| CPU候选公式/子公式准备 | 0.29秒 |
| 严格EMA加载及设备移入 | 4.15秒 |
| CUDA前向 | 4.37秒 |
| 候选指纹及soft Tanimoto | 0.03秒 |
| 进程内总耗时（含torch初始化等） | 49.03秒 |
| CPU峰RSS | 1217MB |
| GPU峰allocated / reserved | 293MB / 300MB |

PyTorch2.9.1+cu126、RDKit2026.03.3，批4、无训练。运行时原适配器SHA `57687d1fc2e219e1d8b7cefaa60580ad012f2459a98522732f933ee15f8ab7bf`，源码快照保存在同一运行目录`adapter_executed.py`。

## 17条冻结候选真实推理

主控给定的17条旧Flex-stage候选CSV共425候选，身份排除规则与范围由主控冻结；适配器未读取其真值或决定入选者。[输入准备](../../runs/mist_active_evaluation_20261114/preparation.json)及候选SHA由主控维护，推理输入只根据该CSV的IDs筛出官方谱列。

[实际verification](../../runs/mist_active_evaluation_20261114/inference/verification.json)：17query、73谱、33公式组、103实际条件输入，387/425候选有分。17条首选都有变化；这只是行为变化，不是收益。CPU特征0.32秒、EMA加载4.68秒、CUDA前向4.83秒、评分0.10秒、总50.40秒；CPU峰1227MB、GPU峰293MB。

- 冻结分数：`runs/mist_active_evaluation_20261114/inference/candidate_scores.parquet`，SHA `dd7b88afb7d1cac52bed0ec1c1b799ae0490540b8af3a95a269d5be9fafffbfd`。
- 冻结输出：`submission_mist_component.csv`，SHA `a7701029560178c12c716314c044b8a914ca752a3fc78a5de35c0d2ba2cc7d0b`。
- 原执行源码快照SHA `c8b958ea6f129ccca7c8bbdc8ead34fdc989e92b7a4cf8a4f1ed68e934581626`在运行目录`adapter_executed.py`。
- 元数据说明：17条运行中的旧通用文案误写two-query/generated-variant，真实字段、路径及SHA均为17条旧stage。原文件未覆盖，以[scope更正](../../runs/mist_active_evaluation_20261114/inference/scope_disclosure.json)为准，预测和分数未变。之后适配器仅将该文案泛化，见[修订回执](adapter_revision_receipt.json)。

## 负离子fallback边界

用原两题的8条真实负离子谱单独跑适配器，[检查通过](negative_fallback_verification.json)：没有加载任何模型张量，没有虚构候选分数，输出CSV字节与原候选CSV完全一致。这个边界补丁在17条运行前加入；两题首次运行的原源码仍保存，未冒充为同一个已执行版本。

## 决策边界

现已取得独立新模型的真实推理和资源证据，首次测速不支持“需要大算力才能开始”的判断；不意味着现成soft Tanimoto排序能胜过.488。负离子覆盖、公式组上限、未知仪器域和MSG预训练曝光仍限制适用范围。主控应先评价冻结17条及后续真实holdout，再决定保留评分特征、训练hard-negative ranker或停止，不能根据17条结果回头挑公式/阈值。尚未运行完整冠军400题、没有隐藏榜分。
