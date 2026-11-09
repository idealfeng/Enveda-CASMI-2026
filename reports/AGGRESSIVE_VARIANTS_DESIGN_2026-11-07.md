# 11月7日批量冲分分支设计与工程核验

已知官方结果：原Flex V56为0.479；完整Gold Apex V30三模型配方为0.475。后者同时改动神经、NP/谱库先验、leader规则及LOTUS，不能把下降单独归因于三模型。

## 本次优先分支

| 分支 | 固定配方 | 目标 | 新资产 |
|---|---|---|---|
| `flex_tri_only` | 原V56全部层保持，Saner评分替换为query内z-score后的0.50public+0.25v2+0.25v4；outside候选同混合 | 测试新模型互补能否在原0.479配方上奏效，去掉V30强NP先验等混杂 | 现有公开v2/v4，共约29MB；不加LOTUS |
| `flex_dual_only` | 原V56全部层保持，0.50public+0.50v2，outside同混合 | 与tri比较，避免v4在隐藏谱条件下的潜在域偏移 | 已有v2约12MB |
| 完整Roman公开复现 | 由Root/公开调研线确定当前冻结版本；旧V17含嵌入102特征异构体GBDT及质量规则 | 验证标题0.482是否能在本账号复现；标题并非保证 | 已有publicv2可补旧deleted依赖，嵌入RR无额外大模型 |
| `flex_rr_aggressive` | 原V56+Roman V17 RR，alpha1.5、lib gate0.95、预算2700秒、MASS关闭；非训练库同式候选可动top1 | 尝试更直接改善异构体首选；原V56低NP先验保持 | RR特征/LightGBM文本已嵌入，复用原frag_rescore |

用户已明确授权积极探索，不再把所有实验限制为首选不动。这里仍保存0.479锚点，固定每条recipe，并通过完整部署核验防止静默回退或误提交占位结果。

## 两条神经分支的实现

构建器：`scripts/build_aggressive_variants_20261107.py`。输出各自独立的`submission/aggressive_20261107/flex_tri_only`与`flex_dual_only`。原Notebook不改。

- 原V56 configuration只将可见`COMMIT_MODE`改为fast。原CUSTOM(.25,.75)、offset3、物理层、m1、POP/SPEC/NP(.10,.05,.02)、gate .87、身份去重及补位保持。
- 只替换cell11神经调度。原所有后续代码在`if RUN_PIPELINE:`内保留原AST；这是避免原V56 fast模式SystemExit阻止最后观察器、并防止fast运行物理层的执行模式处理。隐藏分支原算法不变。
- 严格绑定公开模型四文件、v2/v4原生checkpoint/config。无模型回退、候选或覆盖错配即失败；共同unsupported允许保留原行为。
- 固定7/8个version-pinned数据源、private/offline GPU，无kernel依赖。最后`batch_variant_audit.json`明确`fast_static`和processed0，不冒称隐藏验证；隐藏模式核混合数值、覆盖及CSV。
- 3项离线fixture通过：精确混合含共同unsupported、coverage/key错配拒绝、完整fast调度及observer不调用模型/consensus。

## RR独立复核

Root的`build_flex_rr_aggressive_20261107.py`已生成RR分支。本线独立执行无模型fast fixture并核AST：**13/13通过**，见`reports/aggressive_variant_review_20261107/rr_independent.json`。原hidden V56调度和评分AST保留，RR在其后运行；400行fast fixture无未定义变量，无模型或consensus调用，payload/public pins和observer全通过。

实际Notebook通过原cell10写`ROOT/frag_rescore.py`，RR把ROOT/CODE加入import path，复用已有LightGBM。RR按同leader公式内的可移动候选槽位重排，允许rank1变化，训练库raw IK14成员仍冻结，candidate集合不变。可见输入来自train，因此真实RR往往全冻；fast部署成功或零改动不能证明102特征推理成功，Root另做真实CPU特征/booster fixture。

## 不优先重复的旋钮

原Flex源码已经记载：简单把w_top提到.50或1.00的公开试验分别曾降到.448/.359；Gold Apex文档也记GL_LAM1→1.5降分。直接重复这些旋钮不是本次优先项。只移除POP_W的本地EXP002也未见增益。三模型完整V30的.475进一步说明，海量先验/模型叠加不能自动提升隐藏测试。

本报告及所有准备/fixture未调用Kaggle push或competition submit；Root统一管理实际quota、云端版本与正式提交。
