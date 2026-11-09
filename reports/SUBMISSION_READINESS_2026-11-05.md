# 首次提交状态

更新：2026-11-06 10:10（北京时间）。**首次正式提交58021256已由官方API确认为COMPLETE，Public Score 0.479。** 使用[私有 Notebook](https://www.kaggle.com/code/stormseye/casmi26-flex-v56-baseline) V2，源配方为原始Flex V56。最新读取状态与分数见[kaggle_first_submission_status.json](kaggle_first_submission_status.json)。下文试跑与提交前审计记录保留其当时边界。

## 已完成

- Flex V56、V43、E006 原始源码和必要输入已固定，12分子原始运行检查通过，输出与上游的差异有单独报告。
- Flex V56 提交审查目录：`submission/flex_v56_review`，原Notebook逐字节副本、离线GPU元数据模板、本地447个必要文件均存在且记录尺寸匹配；444项目标旁回执和3项真实同文件hardlink来源链补齐447项记录SHA，本轮未全量重哈希。
- [已安装Kaggle SDK元数据复核](submission_metadata_sdk_review_20261105.md)已完成。`stormseye`账号已认证，V1快速保存后独立回读：代码与原始源码相同、私有、关闭互联网、六项必需附件均出现。服务器只返回附件slug，实际挂载版本仍需指纹补证。
- V2 Save & Run已成功。19:09按明确版本`/2`读取状态为COMPLETE；云端日志约1263秒，神经评分输入失败0，merge和final layer均applied。请求与状态见`kaggle_baseline_run_20261105.json`、`kaggle_baseline_v2_status.json`。
- 可见运行只计算12个示例，其余388行占位。这条证据是部署检查；正式代码提交后已由Kaggle替换隐藏输入重跑，取得0.479真实榜分。
- 产物小文件24项合计273097字节，全部保存在D盘`runs/kaggle_baseline_v2_outputs_20261105b`，没有全量下载模型或输出缓存。29项提交门检查、19项独立复核均通过，官方RDKit2026.03.3复核400个ID/顺序/候选合法性/评分身份去重/最多25及最终SHA。
- 云端实际Python3.13.15、T4×2；主评分RDKit2026.03.3，正向模型独立RDKit2025.03.6。ICE/GL的11个可覆盖分子均评分完成、错误0；N1为11个合成执行检查，真实适用查询0。`run_manifest`里旧的NOT RUN字符串不代表实际未执行，按stage meta与分数计数判定。
- 19:30通过代码提交接口指定V2，服务器返回编号58021256。未上传本地验证CSV。提交前当日次数0，可提交5次；这些是当时API回执，不是长期不变的限制。
- 原始源码没有混入验证查询标签或本地参考谱排除代码；验证器生成独立运行副本。
- 官方CASMI metric V14源码已归档，评分模块固定RDKit2026.03.3，检查去立体信息与互变异构规范化顺序、无效/重复候选的排名行为。
- 48分子诊断队列和250身份最终锁定队列已分开冻结；前者用于验证工程及单因素诊断，后者没有模型预测/选参结果。

## 必须区分的两种污染

参考谱隔离不等于模型未见过：FPNet full1的公开卡明确用全部train folds，Saner final_model的training_result明确包含原验证身份的full-data refit。这是已知训练曝光；不能把当前全栈诊断称为独立泛化CV。fold0单个组件的排除记录也不能替整条管线担保。后续独立组件实验需使用可审计的排除身份和适当checkpoint。

## 发布前尚需落实

| 项目 | 当前边界 |
| --- | --- |
| 实际基线/消融指标 | 两套48分子运行和审计已完成：V43最终0.8207，Flex V0 0.8504、V1 0.8573、最终0.8389；V1配对区间含零，全栈有已知模型曝光，仅作诊断。32分子组件实验单独记录，不混作全栈成绩 |
| 完整输入路径 | 48分子验证已全部处理；云端V2可见运行完成。隐藏全量路径需正式重跑确认 |
| CSV与回执 | 已通过，输出SHA `d2027d8918d15b27fa271ba4961faa63c28fa7f4efbea0dd8069ecbfe6a5060b`；此处指可见试跑，不是隐藏结果 |
| 云端输入版本 | 数字版本未独立回读。400项小文件完整SHA与本地历史回执一致、42项大文件大小及首尾指纹一致；Saner四项模型/代码/config由必经完整SHA匹配门保证，README未纳入该运行指纹。64项主模型manifest检查通过 |
| 环境与时限 | 云端T4×2可见运行约21分钟；正式提交已COMPLETE并出分，证明完成有效输出。隐藏阶段具体耗时及可选模型覆盖未暴露，不能补猜 |
| 许可与署名 | [逐项核对已完成](flex_asset_license_review_20261105.md)：8个附加输入中6个实际需要，按官方train派生、外部NC及第三方权重分别列明。745072原文经多种公开读取仍不可得，无法确认例外范围，不将模型卡转述当作主办原文 |
| Kaggle账号与动作 | 私有V2已正式提交一次。`kaggle_first_submission.py`绑定该版本，提交前排他记录、结果不明禁止自动重试；6项无网络防护测试通过。后台监控只读、每45秒查询、出分/失败即停，最长12小时，不允许新运行或新提交 |

首次榜分锚点为原始V56的0.479。后续新公开模型和自主改动分别验证，不重复提交同一锚点；按[干净组件实验计划](NEXT_CLEAN_EXPERIMENT_2026-11-05.md)补强不依赖曝光权重的验证，不把本地高分当作银牌证据。

提交回执：`kaggle_first_submission_20261105.json`；监控回执：`kaggle_first_submission_watcher.json`；门检查：`kaggle_baseline_v2_output_verification_20261105.json`；独立复核：`kaggle_baseline_v2_output_independent_recheck_20261105.json`；资产对照：`kaggle_baseline_v2_asset_alignment_20261105.json`。提交门报告冻结，SHA与正式提交回执一致；其中“尚未提交”字段描述的是检查发生时刻。

本轮不重新下载已有大资产。新增evgendvorkin V27仅保存源码，其缺失的fold1–4权重不作为当前验证或提交的隐式依赖。
