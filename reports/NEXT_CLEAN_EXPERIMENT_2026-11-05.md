# CLEAN-COMP001：自训一个编码器，验证一个小型排序头

48分子全栈分数有已知预训练曝光；32分子组件实验又发现9例参与fold0监测、训练负候选可能接触留出结构。下一轮不继承这些checkpoint，先取得可审计的组件增量，暂不重训整套Flex。

**现成输入。** 官方`enveda-CASMI26-molecule-id-mass-spectra/train.parquet`；结构召回池`assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/pool_meta.parquet`；编码器源码`assets/kaggle/ahmedberatozer/casmi26-v3-models/v4/code/casmi/fpnet.py`；参考trainer `assets/kaggle/dmitriigluzdov/casmi26-fold-safe-fpnet/v5/train_fpnet.py`；现有冻结splits及`validation.metric`（RDKit2026.03.3）。不直接运行旧trainer：先修负例、监测与派生特征的隔离。

**先冻结身份与数据。** 从剩余公开NP面板及cross-development选新Eval：NP40＋跨库80；另选Monitor：NP10＋跨库20，均与已经查看的48/32身份互斥，按固定seed/来源分层选取，不按真结构能否召回筛人。最终锁定250只取已有身份列表加入denylist，不读取其查询谱、不预测或评分。训练集来自其余身份，首轮固定抽约20万谱；近似重复/完全重复谱跨分区清除。所有分组按官方去立体→互变规范化身份，覆盖同一身份的全部raw-key/SMILES变体，不能只排某条谱或某个SID。

**消除隐性训练接触。** Monitor、Eval、锁定250的身份同时从正标签、质量窗负例、随机负例及hard-negative采样池排除；保留训练否决断言和实际采样ID日志。它们可以作为各自推理时的结构候选，不能作为训练负例。Monitor只负责预先规定的checkpoint选择，永不混入报告中的Eval。权重随机初始化，不使用full1/fold0/Saner/DreaMS、教师分数或公共ranker；不复用全库筛选的`fp_bits.npy`/`pool_fp.npy`。结构特征用固定规则指纹（如固定半径/维数的Morgan＋RDKit指纹），或仅在Train重建bit选择、频率权重和归一化；所有拟合统计均记Train来源。

**固定候选对照。** A：轻量FPNet（初始建议d256、4层）从零学习谱→指纹，按观测precursor/adduct导出的中性质量±10ppm召回，再冻结A的top25。B：冻结同一A编码器，仅训练小型谱/结构匹配头，按固定RRF `1/(3+rA)+0.25/(3+rB)`重排同一top25；训练头也使用上述干净Train/负例池。两臂都不使用参考谱。不得注入Eval真结构；质量窗漏召回、top25截断分别记损失，空候选照计零。该实验检验新排序头，不宣称复现公共Saner的增量。

**启动与验收。** 顺序为身份注册表→冻结split/采样池与代码哈希→隔离断言→500训练步测速→冻结步数/配置→训A→冻结A训B→两seed模型全部冻结后一次评价Eval。保存Train/负例/Monitor/Eval集合、采样、checkpoint选择和完整依赖哈希。任何禁入身份交集、公共权重残留、非有限分数或候选集变化立即停止，修审计后再开新版本。实验完成不以正增益为条件；按两面板报告MRR@25、top1、召回/截断及分子级配对区间。仅方向跨seed一致、无明显分层退化且增量不由单例主导才考虑扩投；区间含零则保留或淘汰分支，不在Eval调参，更不查看锁定250。

**粗估资源，尚未实测。** 现有4060/8GB单作业，CPU注册/缓存约0.5–1.5小时、D盘增量约1–5GB；每seed编码器约1–3 GPU小时，小头约0.5小时，两seed合计约3–7 GPU小时。先用500步实测吞吐与峰显存，再一次性确定预算；不与大内存预检并行。本文件仅计划，未训练、联网或下载。
