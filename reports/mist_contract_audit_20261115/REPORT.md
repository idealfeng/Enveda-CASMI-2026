# MIST常量输出：输入合同与层内定位

结论：没有发现导致本次灾难性排序结果的CASMI张量接线错误。固定发布checkpoint配合当前固定官方源码，在官方原生MSG验证输入上也输出几乎相同的指纹。跨样本差异在encoder最后两层消失，末端相似度公式不是该现象的起因。

## 原始CASMI张量逐项复核

使用现有17题实际推理的103个已表示条件输入，重新调用原始`merge_ms_spectrum`和`assign_subformulae`，把完全相同的重建JSON树交给未经修改的官方`PeakFormula`类。适配器与原类的以下结果逐条精确一致：元素公式向量、离子类别、强度、peak type、有效长度、仪器类别和零padding。每行恰有一个type=3的CLS，位于最后一个有效token。

训练compact缓存将强度存float16；与适配器float32的最大差异为0.0002411。它是明确的数值精度差，不足以解释原生MSG输入也常量输出。仪器映射有未知类别，但当前checkpoint的`embed_instrument=False`，该类别不会进入有效仪器嵌入，因此不是本次现象的主因。

原生MSG全部19429条验证cache与CASMI103行的长度中位数均11；碎片强度中位数分别.3662和.3213。两者的碎片公式均为root公式元素子集，碎片ion均与root ion相同。未发现离子类别、CLS位置或明显数量级错误。

边界：MSG训练读取预先分配的JSON树，CASMI使用重新分配的子公式。上述精确一致是在相同JSON树条件下的合同证明，不证明历史MSG原始预处理完全等同CASMI。适配器还会跳过无可分配碎片谱，而原类可保留只有CLS的输入；实际17题中此类跳过2个事件。这些差异需保留，但不能解释独立的原生cache常量结果。

证据：[逐行合同](feature_tensor_parity.json)、[两种输入分布](native_casmi_feature_statistics.json)、[实际重建CASMI特征](actual_casmi_features.npz)。没有读取结构真值或执行模型前向来挑预处理参数。

## 单次原生小批的层内变化

在指纹审计代理抽取的官方MSG val缓存上，固定等距16条输入，使用实际SHA为`6f8df582df36aa4a984f120efee14ee0a62f3a7723caa770b856a6e704236727`、step=30000的发布权重，严格加载同一官方`ScaledMIST`。未改源码、参数或训练，CUDA单批前向约2.26秒。

| 位置 | 跨样本逐维标准差的均值 |
| --- | ---: |
| 输入CLS公式 | 2.4430 |
| 输入强度 | .29158 |
| Encoder stem CLS | .02258 |
| Attention层0 CLS | .16169 |
| Attention层1 CLS | .01302 |
| Attention层2 CLS | .00005690 |
| Attention层3 CLS | .00000000303 |
| Encoder pool | .00000000303 |
| 最终4096维指纹 | .000000000551 |

Decoder的初始预测、全部gate和predict砖块接收到的encoder已几乎相同，最终概率差异只是数值噪声。不能通过给同一常量指纹换相似度或融合权重，让它重新获得谱依赖信息。

实际层hooks、数值范围、饱和比例、checkpoint来源哈希和输入索引见[layer_contraction.json](layer_contraction.json)。没有再跑CASMI指标、换精度扫描、训练或上传。

## 解释范围和决策

这是对**该发布权重＋该固定官方源码组合**的实测representation collapse。张量不全零，官方输出层也没有重复sigmoid；不能仅据此指责下载损坏、反推原作者训练细节，或认定所有MIST模型无效。

当前这份checkpoint不能被当成已接入的新谱信息。保留原.488，不把它直接部署、不继续在17题上调分数或融合系数。后续需要取得能在原生输入上区分样本的可追踪权重，或明确重新训练并先做500步测速；当前未开始这些工作。指纹代理的独立原生cache与FP定义审计在[另一份报告](../mist_fingerprint_audit_20261115/REPORT.md)。

本次新增脚本只读固定源与checkpoint，输出均在D盘；历史输入、模型、适配器运行快照及原17题负向结果保留。
