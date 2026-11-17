# Helios“0.494 public demo”：源码公开，历史得分权重未公开

2026-11-16，只读源码和Kaggle数据集元数据/文件表；未执行外来源码、未下载大权重、未提交。**不把此demo作为0.494强基线复现或占用正式名额。** 这不是笼统认为Helios方法无效，而是作者已明确当前公开包不包含历史比赛参数。

## 当前证据

- Notebook：[heliosli/casmi26-0-494-public-demo](https://www.kaggle.com/code/heliosli/casmi26-0-494-public-demo)，当前V4，源码775,152字节，SHA `5f09d769677e2d50caf3806f4e64d45fcc82b6785ed228d40e53648a45e36b0d`。标题不是本版本官方提交读回；首段仍保留旧`.477 / 57722897 / 10月29日`记录，不能据首段或排序位置验证.494。
- 作者公开清单确实含rr-v3、FRIGID-E1、RT-NP、joint-ranker、PXv2及新M5/J2/MEGx。先前GetDatasetStatus返回404是接口层错误证据，**不能据此判为私有或不存在**；已用实际view/file-list和作者公开清单推翻该判断，原证据保留。
- 但rr-v3 V2、FRIGID-E1 V2、RT-NP V2、joint-ranker V2、PXv2 V2、M5-v2d V2、J2-judge V4在11/16的新说明中都明确：当前是执行接口演示，原比赛训练权重不包含；私有参数换成初始化demo参数，joint ranker为合成拟合，self-test仅验证demo。**可下载、文件名相同和self-test通过均不能恢复原得分能力。**
- 新MEGx V2更明确是3,683条生成的分子样例，COCONUT ID是DEMO编号，`in_train/in_panel`是假fixture值，与原目录membership无key重叠。不能把该表当真正新增天然产物目录。
- denovo-v3 V1说明为空，不能据一个旧附件反证其他七包的明确demo声明，也未核其训练来源/单组件效益。

当前公开demo包的声明体积合计超过2GB；**本次没有下载它们**。尤其FRIGID约1.76GB的当前包虽然仍含DLM/E1同名checkpoint，但作者明确不是历史0.494所用原参数。

## 源码中的真实新机制与复现边界

1. cell24 RR3：图网络+Transformer处理候选1–2断键碎片；冻结训练结构的原slots，仅重排其他候选，强库匹配整题保护。缺`rr3_config.json`或self-test失败则静默跳过。
2. cell11/28 FRIGID：第二GPU依据E1指纹和原首选分子式生成；相似度≥.7且≤30重原子才插到第2。隐藏截止8.2小时，可见截止.4小时；依赖`wheels313`中cp313二进制，而Notebook固定旧镜像注释期望Python3.12，需另核实际ABI，不能凭源码算可运行。
3. cell25/26 P1+CV-JOINT：先预测首选可信度，仅在低可信题中用对比谱/结构编码器、NP特征、LightGBM联合排序和PX证据重新选择候选；不只是老权重变化。对应训练参数现被替换为demo。
4. cell27/29 M5：MAGMa depth4 + 1–2断键、ICE-T及五折M3偏好模型判断同式近邻，再选challenger。当前`M5_MODE`和`M5_MODE_B`都是`swap`，不是把答案换成甲烷的probe模式。源码要求`m5_manifest.json`，但Notebook metadata未挂目前公开的新`casmi26-m5-v2d`和J2/MEGx包；即使补挂也只有demo参数/表。

所有新增阶段都大量使用catch/skip保原CSV。因此“Notebook成功跑完”可能只是旧基线加若干跳过项，不能称完整复现。部分新gate使用未经官方tautomer规范化的raw InChIKey14；将来若自行实现应沿现有官方身份契约，不直接照搬到候选去重/归因。

## 可复用的研发启发

可以借鉴**训练时要求真结构胜过真实同式近邻**、以及**在首选不确定时让独立证据参与早位判断**，这与当前FIORA错误分解提出的困难负例目标一致。但该架构的收益还需用我们自己的训练数据、固定划分和原冠军完整候选验证；不能将.494标题当作这些组件的单独贡献。完整原参数与可再生成的训练来源若真正公开，才重新审视直接复现。

## 证据索引

- [最终结构化审计](audit.json)，保留全部source/metadata SHA和当前各包的description及证据路径。
- [被后续证据修正的初始判断](initial_hypothesis_superseded.json)。
- [M5-v2d当前view/file-list](heliosli__casmi26-m5-v2d.json)、[J2当前view/file-list](heliosli__casmi26-j2-judge.json)、[MEGx当前view/file-list](heliosli__casmi26-analyticon-megx.json)。
- [原Notebook完整metadata](../notebooks/heliosli__casmi26-0-494-public-demo/api_metadata_full.json)。
- rr/FRIGID/RT/joint/PX当前说明及文件表在 `../notebooks/dependency_inventory_v2/`，逐项原始路径与SHA见audit.json；大包文件表限首100项并保留分页标志，未声称完成全量文件盘点。
