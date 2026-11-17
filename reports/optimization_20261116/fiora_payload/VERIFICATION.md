# FIORA tims500私有离线包核验

状态：**本地纯Python隔离导入、真实分子图前向、导出父权重一致性和数值对照完成，无模型导出阻断**。本文件不代表Kaggle镜像运行、完整冠军初始化或隐藏评测完成。

- 固定包目录：`submission/optimization_20261116/fiora_payload/`，直接root含`params.json`、`state.pt`、`asset_manifest.json`、2个去标签canary文件；源代码在`source_checkout/`，纯Python依赖在`dependencies/`。
- 最终762文件，58,539,433字节；manifest SHA256：`113c1f1af933e1f01bcdce6cf6a0a02cd618f7594b561e3928c80ae70d0c0622`。
- 导出state SHA256：`c449c98ad0cf42e71561b8de97073986a447019c7430c82111a7eb29466c54f9`；父step500 checkpoint SHA256：`9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252`。
- 全部67张量逐元素精确等于父checkpoint的`model_state_dict`，参数13,448,861；optimizer未打包。params保持原已测SHA与19维模型，不修改其历史migration元数据。
- 仅携带PyG2.6.1、dill0.4.0、treelib1.8.0、six1.17.0等纯Python文件和许可，无`.so/.pyd/.dll`。实际隔离前向不使用原source_checkout/dependencies-linux，也不需要本机缺失的aiohttp、regex、xxhash；目标须提供常规torch/RDKit/NumPy/SciPy等环境。

## 为什么最初raw hash检查失败

最初检查要求新进程的原始FP32预测向量与历史hash逐bit相同。实际谱分数为`.0023397624482988074`，历史为`.002339762284911956`，只差`1.63e-10`；构图同为54条有向边、542个输出通道。该失败证据保存在[首次不匹配记录](isolated_forward_first_mismatch.json)，未删除或覆写。

后续保持原模型、图、精度、scoring及计算flag，以同一进程的真实前向检验：

| 对照 | 原始向量最大绝对差 | 谱分数绝对差 |
| --- | ---: | ---: |
| 相同导出模型、同图，CUDA重复3次 | 最大`5.96e-8` | 均小于`1.2e-10` |
| 导出state与父checkpoint，同CUDA | `1.49e-8` | `1.52e-10` |
| 父checkpoint CPU与导出CUDA | `1.19e-7` | `1.74e-10` |

因此真实前向本身就存在FP32数值微差，不能将跨进程raw hash不同当作权重错误。张量导出仍要求精确相等；前向对照明确使用`atol=1e-6, rtol=1e-5`，谱分数`atol=1e-7`。没有为了匹配hash改seed、线程数、TF32、模型或算法。未逐kernel定位，不能据此声称某一个具体kernel已经完成因果溯源。

完整结果、实际计算flag、导入路径与逐张量检查在[隔离前向回执](isolated_forward_verification.json)；导出证据见[export_receipt.json](export_receipt.json)，最终文件封存见[finalization_receipt.json](finalization_receipt.json)。独立runtime的50个候选谱分数与历史最大差`8.59e-9`，全部低于`1e-7`，两题最终重排CSV与历史分数重放完全一致，见[独立评分与重排对照](../../new_paradigm_20261116/runtime_canary/score_parity.json)。

## 许可与范围

原FIORA-OS预训练模型来自MSnLib v7，未采用NIST版本；MIT源码许可保留。500步迁移使用400个官方训练结构，原100个开发结构不在这些更新中，但MSnLib预训练曝光未知。官方数据与去标签canary仍遵守比赛许可，不因源代码MIT而重新授权。README明确要求私有资产。

验证程序为[scripts/build_fiora_submission_payload_20261116.py](../../../scripts/build_fiora_submission_payload_20261116.py)，没有训练、调参、标签评估或Kaggle写入。最终payload冻结后未再更改。
