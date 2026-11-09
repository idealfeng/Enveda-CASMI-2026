# 新训练目标的最小实施入口

这是源码核查和可实施协议，没有启动训练，没有计算锁定250的预测或读取其查询真值。

## 建议先做的组件

冻结现有 public/v2 编码器，训练**候选条件的多谱匹配头**。当前神经路径先对每谱打分，再无条件取均值；新增组件保留逐谱表示，让候选结构参与每谱证据的聚合。这样改变的是表示交互和训练目标，不只是 public/v2 的固定混合权重。

首轮仅加载 v2 一个编码器开发；public 留为后续对照。只训练小头，先不更新编码器。

输入是每个谱的归一化表示 `Z_s`、每个候选的归一化表示 `M_i`、原始 cos/temperature 与 fp 项、可观测采集元数据、峰数。小头可用 `[Z_s * M_i, abs(Z_s - M_i), cos, fp, metadata]` 输出候选—谱交互残差及有限幅度的证据权重，再沿真实独立谱组聚合。初始残差为零以复现原均值对照；不伪造缺失的CE或仪器字段。

按查询列表训练 softmax/listwise 损失，训练列表使用当前组件检索的最高分错误结构，加少量随机负例防止只适应一种错误。每个官方身份只出现一次。训练时正例可以加入；独立 Eval 的候选生成不能注入答案，漏召回照计零。

## 可以复用的实际代码

以 `assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1/` 为源码根：

- `model.py:17` 的 `encode_spectra(x,lengths,meta,adduct)` 返回归一化的192维谱表示及2048维指纹 logits；`model.py:26` 的 `encode_molecules(fp)` 返回192维结构表示。
- `features.py:12` 按原始谱选最多96峰并构造4通道输入；`:23` 返回4维metadata和adduct索引；`:30` 去立体、互变规范化后生成官方身份及固定Morgan2048。
- `train.py:16` 已经有 same-formula 优先、近质量128候选池。`:109` 在池里随机取16个负例，`:126` 使用跨批正例和负例的交叉熵。不能把再加同式负例称为新方法。
- `prepare.py:17` 维护的是可复用的二进制spool格式，但完整原训练缓存未下载；不能直接用已有权重目录当训练缓存。

实际可复用推理装载器是 `runs/validation_flex_c2_20261105d/p2s_code/neural_scores.py:6` 的 `load_model`，严格加载state_dict；`:55–61` 显示原始逐谱表示、候选分数及无条件均值的完整位置。新组件应在均值之前导出，而不是只拿均值后的CSV训练。

## 数据格式和缓存边界

Saner原训练缓存：

- `peaks.bin`: float16，形状 `[N,96,4]`。
- `metadata.bin`: float32，形状 `[N,4]`。
- `fingerprints.npy`: uint8，形状 `[M,2048]`，固定规则Morgan指纹。
- `molecules.parquet`: `key,smiles,formula,mass,split`。
- `spectra.parquet`: `key,length,adduct_id,source,original_molecule_id,original_spectrum_id,mol_idx,split`。

本地另有可mmap的 `runs/shared_spec_cache/spec_{mz,it,off}.npy` 和63MB `spec_meta.parquet`；它们经过公开引擎 `clean_block(0.001,512,2.0)`，**不是原始Saner输入的等价缓存**。若首版复用它，必须把预处理改变写成实验条件。更稳妥的小试是按原始train parquet流式筛选少量结构和谱，用 `features.peaks` 重新准备小缓存。

`runs/validation_flex_c2_20261105d/work` 下的一批0字节文件是历史部署占位，不可作为训练缓存。候选目录使用 `assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/pool_meta.parquet` 的真实文件；模型特征首版重算固定Morgan，不继承全库拟合的特征选择统计。

## 实际困难负例的取得方式

1. 按观测 precursor/adduct 算中性质量，先召回原候选目录的质量窗；按官方评分身份去重。
2. 用冻结 v2 组件对所有召回候选评分，保存完整排序和实际截断位置。
3. 对Train查询，保存得分最高的错误身份 top32 作为首轮困难池，保留错误排名、模型SHA、检索代码SHA及候选目录SHA。根据训练推进再重新挖掘。
4. 这只是**v2组件的实际检索负例**，没有跑完整Flex时不能称为完整Flex错误。若要融合ICE/GL，另导出完整检索器/碎裂引擎的错误列表和逐谱证据。
5. 训练的正例、负例、monitor及拟合统计都排除Eval和锁定250的官方身份。所有候选ID唯一；互变异构等价结构不能标成负例。

已有48查询的 `frozen_candidate_evidence.parquet`、`effective_query_spectra.parquet`、`neural_candidate_features.parquet` 及 `outsider_neural_features.parquet` 足够验证导出器、输入对齐和原均值的数值复现，**不足以训练并宣称稳定收益**。另有 `validation_candidate_stages.parquet` 和两个 `validation_e*_candidates.jsonl` 可核查截断前的候选。只在这个面板训练融合器会继续过拟合已查看且有预训练曝光的小样本。

## 最快的可信评价入口

公共 v2 config 的 `external_paths=[]`，但 `final_model.pt` 是full refit，官方train里的目标都可能被见过。给新head重新切Train/Eval不能洗掉编码器曝光。

优先等待Enveda-180增量审计，取**按当前官方评分身份确认不在官方train的外部目标**，作为未见身份组件的Monitor/Eval（还需排除同次采集和重复谱、避免选中已锁定身份）。是否有足够新结构必须由真实扫描决定。这个结论只适用于已审计训练来源的Saner组件，不扩展成整套ICE/GL的clean CV。

若外部真实未见身份不足，首轮训练先标注为known-exposure工程诊断；之后用随机初始化小编码器获得目标隔离组件对照。不能为了今天出一个数字，把人工truth-plus-decoys诊断标成竞赛候选召回。

## 500步测速的实际含义

先冻结一个真实的小型训练表，例如至少1024个Train身份、每个身份若干有效谱、32个真实高分错误候选。具体数量由合法可用数据决定，不能拿48个已看过的诊断身份冒充训练集。

分开记录：数据扫描/原始预处理、冻结encoder特征导出/困难负例挖掘、**小头500优化步**、Monitor推理。小头500步只证明梯度/损失/吞吐和显存正常，不能当完整encoder微调耗时，也不产生正式提交。保存实际更新次数、NaN/Inf数量、梯度范数、初末损失、峰显存和每步耗时；再冻结完整训练预算。

先用零残差头复现原逐谱均值，之后才启用可训练残差；这是实现正确性检查，不是提升证据。训练完成后比较原组件、固定均值新头、候选条件聚合头；候选集和编码器相同。两seed分开报告同式排序、MRR@25、top1、候选池召回及top25截断，不能只展示整体最优数值。

目前未有新的测速或训练结果。所有新增文件、cache和checkpoint继续留D盘。
