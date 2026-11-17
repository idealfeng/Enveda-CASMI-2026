# FIORA正式探索接入：真实runtime到CSV小试

2026-11-16。用户要求先提交本轮，明天依据正式榜分规划下一轮。本报告只记录新增FIORA组件的实际离线执行，不把现有开发面板效应当成冠军收益。原冠军58156482/.488的固定源码未改；新增overlay消费其AB后的最终候选。

## 冻结实现

- Runtime：[fiora_submission_runtime_20261116.py](../../../scripts/fiora_submission_runtime_20261116.py)，SHA `1f7dece2a4a817c54c1915dbc45ad64ebaa6e084d4646acc3f6cd7972d80e817`。
- Payload manifest SHA `113c1f1af933e1f01bcdce6cf6a0a02cd618f7594b561e3928c80ae70d0c0622`；部署state SHA `c449c98ad0cf42e71561b8de97073986a447019c7430c82111a7eb29466c54f9`，父500步checkpoint SHA `9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252`。
- 读取CSV候选和parquet八列白名单；仅真实timsTOF、[M+H]+、单CE20–60eV。每分子按spectrum_id字典序固定选首条合格谱，不看任何目标/分数选谱。
- 同式组保留原公式slots，允许rank1参与；相同分数按原位次稳定排序。没有新增AB保护或融合系数搜索。
- 为可执行天然产物候选，提交上限固定64 heavy atoms/160 directed edges；明确超出训练32/74范围，不称已验证泛化。待竞争候选任一超限或推理失败整题保持原输出；全局资产或初始化不合法直接失败。
- `compiled_mass_map`和`spectral_score`的AST与已测准备/评分函数完全一致。独立审查和小试没有修改已冻结payload。

## 真实执行

| 路径 | 谱支持查询 | 实际forward/成功评分 | 整题评分 | 实际重排 | 首选变化 | 候选错误 | 总耗时 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 固定开发前2题，各pool前25 | 2/2 | 50/50 | 2/2 | 2 | 0 | 0 | 122.39秒 |
| 既有生产两题最终候选 | 1/2 | 25/25 | 1/2 | 1 | 1 | 0 | 53.43秒 |

开发小试输入按原100题molecule_id字典序头2选取、各原pool前25，未读truth或预测效果选样，50候选均为不同官方身份。生产小试复用旧生成版本已经落盘的真实两题输出，**不是本次重新完整初始化冠军**：`cross_VXVNYCRICCVPTD`没有支持谱而原样；`np_DUXQKCCELUKXOE`的25个候选均超训练图范围但在固定提交预算内，实际forward并消费至CSV，rank1发生变化。这不证明首选改变是正确的。

两例均验证ID顺序、raw候选multiset、官方身份multiset、每位公式、失败回退、CSV roundtrip、输入和全部payload SHA。host峰分别1393.70/1500.26MiB，GPU分配峰71.75/135.02MiB。另走static路径，模型未调用且输出与原CSV逐字节相同。

总回执：[verification.json](../../../runs/fiora_submission_canary_20261116/runtime_checks/verification.json)。逐题及实际分数位于同目录`label_free_dev2/`和`existing_production2/`；复核入口为[check_fiora_submission_runtime_20261116.py](../../../scripts/check_fiora_submission_runtime_20261116.py)。

## 与既有固定评分数值一致性

50个开发候选与已封存full100评分逐(molecule_id,smiles)比较，最大谱分数绝对差为**8.59e-9**，全部低于核验容差1e-7。跨CUDA进程raw概率字节不完全相同；使用旧封存分数执行相同公式slots排序，得到的两题CSV与新runtime完全一致。[完整差值](score_parity.json)。未因raw hash差异重训模型、调阈值或换候选。

此处已通过的是新增组件真实构图→严格模型加载→实际forward→谱评分→重排→CSV。Kaggle目标镜像可见canary、代码提交接受、隐藏完整重跑和榜分都由后续官方回执分别确认；本报告不作这些尚未发生的声明。
