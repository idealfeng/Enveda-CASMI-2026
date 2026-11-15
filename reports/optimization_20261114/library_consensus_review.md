# 11/14：实测外库多谱支持的早位排序

状态：已放行供主控探索提交；本代理未进行云端写入。只取 `submission/optimization_20261114/library_consensus_early/revision3/branch_spec.json`。初版、revision2及原检查失败均保留，不能将它们误当正式部署版本。

## 改动及固定对照

父版本为精确冠军58156482，Public MRR@25 .488，Notebook SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。原33个cell逐对象不变，原模型、双神经、MASS、head和AB全保留；只追加新证据排序，不增加候选或训练。

原AB通过所有谱和参考中的单个最大余弦选择首选，并跳过原流程library_max≥.9的整行。本版再次运行同一原Alex V12参考加载、模式约束、前体窗和余弦公式，用AST观察每个真实query谱/参考配对得分；这一私有证据pass关闭原整行library_max≥.9跳过条件，其全局最大值生成的私有CSV绝不应用。

对已有25个候选按官方身份匹配参考，收集每个独立query谱上的最大合格余弦；完全相同的mode/precursor/mz/intensity谱只计一次。固定要求余弦≥.60且≥4峰，至少2个不同真实谱支持才允许其所在同式组重排。

候选支持分为 `.5×平均谱余弦 + .5×支持谱比例`，固定排序分为 `-log(原名次) + 支持分`，同分保持原次序。只在同分子式原槽位内重排，实际被原AB接受的命中整行保护。revision3不保护普通原rank1，因此多谱证据可以挑战一个原库高置信首选；原AB真正接受的匹配仍保留。本轮未用标签调整系数、阈值或评分目标。

## 组件证据与版本演进

1. revision2真实追加cell在已有两题/20谱生产输出上执行，官方12谱列投影，无标签字段。参考实际加载A=200724、B=124160，观察691个谱对、60个合格候选谱对。两题中一题原rank2获8/8独立谱支持，支持分.960852；其原rank1只有2/8谱支持、支持分.2135。另一题主要支持原rank1。
2. revision2保留rank1，故实际名单0变化，不能声称收益。最初纯排序消费fixture选了第一个弱支持候选，不能跨过原名次差，断言失败；算法和真实追加cell本身已通过。失败原文件保留，后续仅选择已有最强支持候选测试消费，不改变系数。`verification_completed.json`记录实际追加cell通过、输出hash篡改拒绝，以及fixture不是预测收益。
3. 主控选择更能检验机制的revision3：只将protected_prefix 1→0，同时将观察器改为核对配置要求的保护前缀；其他源字节与revision2一致。固定系数未变，使用同一已产生的真实多谱分数回放，不重复加载谱库。两题里1条名单、1条top1改变；所有候选multiset、官方身份合法性及每槽分子式保留。此数字只证明预测变化，未计算正确率或MRR。
4. revision3冻结追加cell的实际fast_static路径也在原生产输出及固定源文件上执行通过，`kaggle_batch.local_preflight`实际通过。这里没有声称重新初始化基座、跑过四百题或完成隐藏推理。

生产中强AB保护的观测输入也有明确边界：这两题原AB实际0命中，所以真实AB保护命中分支未被覆盖；另用同一已观测候选分数进行显式保护gate夹具验证，夹具不算真实命中或收益。先前成功两题生产输入曾含未消费标签元数据，本次独立query投影只保留官方12谱列，来源及SHA可追溯，但仍不是清洁CV；候选来自已保存的扩生成生产中间产物，不是精确冠军候选集。

## 定位与指纹

- 最终stage：`submission/optimization_20261114/library_consensus_early/revision3/`。
- Notebook SHA：`1a6b341fe9b62f23d0a0db1a3513f624f29faa260f31f4b145e282f621ab689b`。
- recipe SHA：`3bc44dc8ce443dad75c5b73b601f6bdb9b9ac114558acef02c90aa767832bee0`。
- 入口：`scripts/build_library_consensus_early_20261114_v3.py`及其recipe绑定的模块文件。
- 放行：[library_consensus_release.json](library_consensus_release.json)。
- 实际配对证据：[revision2完整真实追加cell及检查更正](../../runs/library_consensus_early_20261114_r2/verification_completed.json)，原`failure.json`保留。
- 最终固定策略：[revision3真实分数回放及fast追加cell](../../runs/library_consensus_early_20261114_r3_replay/verification.json)。

## 决策

按用户要求作为五条探索之一提交；不是谱库扩容、先前无效质量索引修复、同系checkpoint集成或produre任务重做。若正式涨分，暂归因于固定多谱支持及放开早位保护的整体接法，不归因于新增数据或训练；若同分或下降，保留真实结果与适用边界。隐藏全集运行时间、完整推理成功和正式Public分均待主控读取，不由本组件报告推定。
