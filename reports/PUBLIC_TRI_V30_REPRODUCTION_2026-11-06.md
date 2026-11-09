# 公开三模型V30完整配方：部署复验

2026-11-07更新：正式提交58051406已 **COMPLETE / Public 0.475**，低于原始Flex V56的0.479；本分支未带来榜分提升。下文PENDING为当时记录。新的四分支提交见 `reports/AGGRESSIVE_BATCH_2026-11-07.md`，不能把本地固定候选正收益直接映射到榜分。

2026-11-06，北京时间。目标：独立保存新公开方案的复现分支，与原始Flex V56 Public 0.479及固定候选EXP004分开记账。

## 已完成

- 上游 `zz3t3rn41/casmi26-peaks-to-structures-v2` V30源码冻结，SHA `73c8bdc7799ffdad7ef756015c74c90365ee060122f2567f8a3c061ff42cc0df`。作者个人best 0.4810不等于本次V30已核实分数。
- 创建[私有离线GPU Notebook](https://www.kaggle.com/code/stormseye/casmi26-public-tri-v30) V1，15:53发起；16:17查询确认COMPLETE、failure_message为空。
- 部署修改仅涉及可见输入smoke模式和运行前后观察器；原排序代码保持。新增观察器验证实际权重/配置/特征代码SHA、三模型覆盖与逐query z-score组合值，未修改分数或CSV。
- 服务器将两处cell.source行列表转为字符串。全部cell内容、代码AST及其余Notebook JSON字段一致。保存本地源码SHA `1d5e50cdd139353074f022f1d3a280fbfb688ca27da92610eee72dcdd7d19b33` 和服务器SHA `60b45e331d6f04e34ce779f35421cd09915256f56a85d2ef1a6da9e3757d5748`，不把表示变化误判为算法变更。
- 小型产物下载115,899字节，全部保存D盘；没有下载完整输出ZIP或重复大模型。
- 离线核验 **41/41通过**。public/v2/v4各300个有效候选、12个可见分子，缺失0；三checkpoint不同，组合分数最大绝对误差0；outsider三模型组合也精确复现。
- 最终CSV400行、ID及顺序与官方sample一致，每行1–25个合法评分身份，无重复评分身份。SHA `5803d3bdf65908d656672f0796305fd9d72cd56f9d1d90f7beff7d5f59847c0d`；观察器/核验器前后字节不变。

## 范围与后续

此次可见运行只实际计算12个分子，其余388行属于可见输入占位范围；不能称隐藏400全量推理或已取得新榜分。正式代码提交将绑定云端Notebook V1及其 `submission.csv`，由Kaggle替换隐藏输入重跑。

V30整套配方除三神经模型外，还改变NP先验、leader规则和LOTUS membership/回填。它是完整公开配方复现，不是EXP004的单因素延伸。三模型有官方train full-refit曝光，48分子诊断也不是干净CV。权重数据集标注Unknown许可，公开可访问及运行成功不能替代最终参赛资产资格复核。

16:21正式提交已被接受，编号 **58051406**，绑定云端V1，当前 **PENDING、无新Public分数**。仅调用一次code-submit，未上传本地诊断CSV，旧提交58021256及其0.479成绩保持独立。

只读后台监控已启动：实际进程17756（启动器21868），每45秒查询固定58051406，最长12小时，COMPLETE/ERROR即停止。进程身份已核对；后续启动记录不能代替实时存活核查。正式提交状态见 `reports/public_tri_v30_submission_20261106.json` 和 `reports/public_tri_v30_submission_status_20261106.json`。关机不停止Kaggle隐藏重跑，只停止本地监控。

## 证据

- `reports/public_tri_v30_cloud_run_20261106.json`
- `reports/public_tri_v30_cloud_status_20261106.json`
- `reports/public_tri_v30_server_binding_20261106.json`
- `runs/public_tri_cloud_v1_outputs_20261106/download_receipt.json`
- `runs/public_tri_cloud_v1_outputs_20261106/public_neural_input_audit.json`
- `runs/public_tri_cloud_v1_outputs_20261106/public_neural_execution_audit.json`
- `reports/public_tri_v30_output_verification_20261106.json`
- `reports/EXP004_PUBLIC_NEURAL_2026-11-06.md`
