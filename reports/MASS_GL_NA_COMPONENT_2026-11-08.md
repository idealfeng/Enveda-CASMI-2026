# 0.481 MASS + 真实Na GLACIER分支

本轮仅准备本地源码、运行一次完整GL覆盖诊断及验证实际逐谱加权组件。没有创建云端Notebook、提交比赛或读取锁定250真值。

## 最终提交接口

- Builder：`scripts/build_mass_na_variant_20261108.py`。
- 最终helper：`scripts/mass_gl_na_counted_hook.py`；云端写为`gl_na_hook.py`。
- GL worker：`scripts/gl_counted_runner.py`，复用已通过观察等价检查的`forward_trace_runner.score_code`，只观察每candidate的finite谱数。移除观察器后评分AST与原runner完全一致。
- Stage：`submission/optimization_20261108/mass_gl_na/`。`branch_manifest.json`可供根批次合并。
- 最终冻结Notebook SHA256：`6e86ab7b93fdfa537c2cd0624e664691ccf6096b7696c4f84e2f8c2703f49605`。Metadata SHA256：`fa1265a10b3c6d0dca9ec6260ca337bdc607a6957f7cd3134c8f965fafc82003`。

底座是我们已获0.481的旧MASS源码，保留其final质量首选规则、physical代码、先验、public/v2双模型和LOTUS。frozen notebook字节及原始SHA不变；仅在runner实际执行cell41时显式适配GL调用，receipt记录source_adaptations。原observer的400条隐藏规模断言改成sampleIDs动态范围。

## 为什么没有采用完整H+Na联合重跑

实际联合GPU运行完成46query、163谱、3774原候选、13698逐谱评分，无缺失/非有限，均值重构最大差1.11e-16。用时189.43秒，峰显存0.45GB，产物`runs/gl_hna_full_20261108/`。

但34个无Na且输入逐字段相同的query，与旧H-only缓存的分数最大差0.013479600835407335。原因未确定，不能把它称为普通浮点误差或已证明的随机/eigenbasis原因。`verification.json`保留这个未通过的控制检查。该联合配方未云端发布/提交，初稿保存在`mass_gl_na_joint_draft/`。

## 最终行为

1. H-only输入、预测顺序和原聚合保持原路径；使用exact-AST只读观察器记录每candidate实际finite观测数。
2. Na谱保留真实adduct、precursor、仪器和CE字段，单独GL推理，原候选列表不变。Na预算1800秒，H预算保留4000秒。
3. 对同一个candidate，组合分为`(H均值*H实际finite数 + Na均值*Na实际finite数)/(finite数总和)`。缺失一条路径时直接保留另一条原始值，无Na query值精确保留，不重新计算。
4. 原`gl_work/gl_out.json`保留，组合另写`gl_na_combined.json`。frozen导出通过GL_SCORES消费组合值，末尾observer逐值核对导出的gl列与组合JSON，防止算出新信号却未参与排序。
5. 真实Na覆盖了原H-blind query时，N1 proxy重叠按照原hidden策略丢弃，优先保留真实adduct评分；同样处理visible完整模式以免旧断言误判，但只允许真实Na造成这种clash。NH4/WL原策略未扩展。

GL支持Na token及碎片质量路径不证明预训练中Na覆盖/准确率；本分支是实际新信息实验，没有涨分结论。

上游H-only筛选旁注有`v29: GLACIER on [M+H]+ only (v27: +0.006)`，N1代码里也保留HNa诊断arm，说明社区并非从未试过H+Na；该注释没有提供可独立归因当前0.481底座的完整对照。本次只作为明确隔离Na增量的机制探索，不称全新算法或稳定收益。

## 本地验证

`runs/gl_na_counted_merge_20261108/verification.json`：9/9检查通过。读原H-only逐谱trace和已完成真实Na-only trace，按实际finite count组合得到46query/3774原候选，逐谱均值重构最大差1.11e-16；无Na值精确保留。另合成fixture覆盖同query的不同candidate具有不同finite数、Na缺失保留H、Na-only新query、非法count拒绝、AST观察等价、actual count installer记录变长计数。

旧H输出fresh SHA仍`424ffecab17f571a858da452c27a6f1ce2dda64d01549b0854d1ce1c0b0c62d9`，加权组件结果SHA`c0ff4030f11c7a57ae479cf05f8086ea1556fca391a79ee30d4e77fab0c92807`。未对该组合评价MRR，没有新训练或新榜分。

云端fast_static只验证部署和占位CSV，隐藏正式重跑才执行H/Na实际模型、有限观测数和消费审计。所有来源/模型/适配脚本有明确pin，失败时拒绝静默宣称新组件成功。
