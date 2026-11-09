# 首个候选条件多谱训练头：真实训练与提交资产

2026-11-08（北京时间）。本次已实际准备数据、冻结v2导出表示和真实困难负例、完成500步测速以及两seed各2500步训练。没有使用旧48作为训练集，没有访问锁定250查询或对其预测/评分。否决成员仅取既有冻结清单的身份与关联raw-key字段。

## 算法与原方案的差别

原v2先计算每谱cos/temperature与fp项，再等权平均。新模型固定原编码器，在逐谱层输入谱表示与候选表示的逐维乘积、绝对差、原cos/fp/base分、原metadata、adduct及峰数；小MLP同时输出候选条件残差和逐谱注意力，直接在实际候选列表上训练cross-entropy。

模型25986参数，隐藏64，残差限幅`4*tanh`，attention按真实谱维归一化。输出层零初始化，在真实训练数据第一query上与旧均值最大差0；另8项契约检查包含mask、候选置换、增加候选不改原候选评分、有限非零梯度，全过。它不会因增加候选改变原列表的归一化统计。

代码：`scripts/candidate_multispectrum_head.py`；训练/缓存脚本：`scripts/train_candidate_multispectrum_head.py`。

## 数据与曝光边界

- 1024个Train身份、128 Monitor、128 Eval按官方RDKit2026.03.3评分身份划分，互不重叠；所有旧冻结面板的700身份及其关联raw-key作为否决成员，训练负例也排除Monitor/Eval身份。
- 从当前官方train全部2539608行流式筛取4801张真实谱，每身份最多4张、原Saner预处理，原始峰值与metadata输入完全复用上游features.py；不是借用经过其他清洗的shared CSR。
- 工程集合按固定hash顺序选择，原catalog需>=3谱，质量150–700、10–60重原子、真质量附近原catalog候选17–96；此选择影响难度分布，不能当隐藏分布代表。实际候选由观测precursor/adduct中性质量中位数±10ppm召回。
- 59901个候选SMILES重新canonical并生成固定Morgan2048；v2对完整实际质量窗排序，挖出30991个高分错误负例，15445个同formula。原训练已有随机同式hard pool，本次新增是实际v2错误排名，不是完整Flex错误。
- Train有15个正例未在实际窗中召回，仅训练时添加；Eval没有注入正例，召回126/128。没有把候选外答案从Eval分母删去。
- 公共v2是官方train full-refit，编码器可能见过全部这些身份；新head split不能消除这一曝光。因此全部指标是**known-pretrained-exposure组件工程诊断**，不是干净全栈CV，也不能直接加到0.481榜分。

独立数据21项检查全过，无跨split精确预处理重复谱；约68%的谱来源为enveda-180，其余主要是pluskal_ms2、GNPS等。这仍不能替代真正未见身份与天然产物迁移评价。

## 测速与固定训练

| 阶段 | 实测 |
| --- | --- |
| 原始数据扫描、canonical/Morgan与缓存 | 465.32秒 |
| 冻结encoder导出与实际负例挖掘 | 20.83秒，峰显存0.077GB |
| seed20261108的500优化步 | 3.434秒，loss前100均值1.29555→末100均值0.99081 |
| seed20261109的500优化步 | 3.555秒，loss1.27923→1.01833 |
| seed20261108完整2500优化步 | 12.30秒 |
| seed20261109完整2500优化步 | 12.72秒 |

两seed loss/gradient全部finite，峰训练显存0.0239GB。小头测速不代表完整编码器微调耗时。固定预算与seed在结果前已确定，保存step500和step2500，不按Monitor挑最优步数；本次提交资产固定step2500。

## 结果：Monitor和Eval方向相反

| 组件 | Monitor MRR@25 | Eval MRR@25 | Eval top1 |
| --- | ---: | ---: | ---: |
| 原v2逐谱均值 | 0.786099 | 0.829744 | 0.734375 |
| 新头seed20261108、2500步 | 0.765281 | 0.844922 | 0.757813 |
| 新头seed20261109、2500步 | 0.757922 | 0.831022 | 0.734375 |

初始Monitor/Eval列表为保持目标边界还删除了其他独立面板身份；独审指出后，固定模型另重建128 Eval原目录候选，加回7 query中7个被删候选，不改训练/权重/原cache。两个seed在补评中的MRR、top1和逐例增损均与上表完全一致。Monitor仍标受限候选诊断，未用于选择2500预算。

两seed均Monitor退步、Eval改善，第二seed改善很小。**不能称稳定提升**。本轮可作为用户授权的进取实榜新组件与独立seed复验，但部署最好0.481继续保留。指标区间和逐例详情见`runs/candidate_head_20261108/summary.json`、`full_catalog_eval.json`；没有新Kaggle分数。

## 固定模型资产

- seed20261108：`runs/candidate_head_20261108/head_seed20261108_step2500.pt`，107291字节，SHA256 `99e63aedb420217c817aeaaebd3d09ffa9620824a8d8833dcf55fd90ae903a53`。
- seed20261109：`runs/candidate_head_20261108/head_seed20261109_step2500.pt`，107291字节，SHA256 `f29077ca350e48705cec93ed7a9716b2b718e965ba56cec859bb829bf4b7ba75`。
- frozen v2 encoder SHA256 `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`。
- head源码SHA256 `6dc38d9d9dd59bff0ed791045573638c5566b2e1f84c0336c1b1bff383f886f0`。

checkpoint仅含小头state_dict、config、seed/step及来源SHA，可base64嵌入私有Notebook，使用时仍须核验实际v2权重、保持主/outsider一致处理。所有新下载、缓存、checkpoint、日志都在D盘；本子任务没有云端push或提交权限调用。
