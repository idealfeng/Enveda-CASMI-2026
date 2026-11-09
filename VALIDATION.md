# 本地验证与诊断

工作日期：2026-11-05。代码、查询、日志、环境、缓存全部在 `D:\Paper\casmi`。

## 已经固定的口径

`validation/metric.py` 根据归档的官方CASMI metric V14核对：主RDKit固定2026.03.3；先去立体信息，再互变异构规范化，匹配InChIKey14。空的分号字段按官方规则处理，无效SMILES及重复身份仍占原排名。边界测试包含直接调用官方源码的对照、互变/立体耦合、无效候选、重复候选、25候选上限、ID与真值保护、候选集合一致性及配对bootstrap。

`validation/evaluate.py` 计算分子级MRR@25、top1/top5/top25，按panel/source分层，比较同查询的分子级paired bootstrap。候选生成阶段没有审计证据时，召回率为未知，不能拿top25命中率代替召回率。使用真分子式的子集是诊断用oracle信息，不作为可部署指标。

## 第一批查询

冻结清单在 `runs/validation_pilot_v2_20261104/manifest.json`：24个同仪器NP + 24个跨库开发身份，共240谱。查询仅允许官方10种adduct，当前批次实际覆盖8种；原始谱、能量、离子模式等已按原train的source_row逐项核对。每分子最多12谱只是本轮开发cap，不是隐藏测试限制，采样损失会单列。

Class2采用整个当前队列的global leave-cohort-identity-out：51个相关raw-key家族、5,725条参考谱从直接检索、analog及代表谱排除，候选结构真值不删除。与逐分子leave-one-out的结果不能混为一谈。Class1模式只删除查询自身及精确重复谱，保留同结构的独立参考谱。Flex扩展的751张外部谱也必须通过同样屏蔽检查。

另有冻结的跨库开发200、最终锁定250身份。最终锁定身份不在当前active查询中，未提取用于推断、未运行预测和指标；不能反复使用它选参。

源码审查另发现evgendvorkin V27采用五折模型平均。对本地训练身份做OOF时，不能把该平均直接当作未见预测：对应一折的目标可能已被另外四折模型训练过。本轮未加入该集成，也未下载缺少的四个权重。

## 已知训练曝光

当前全栈结果标为 **reference-isolated diagnostic with known pretrained exposure**。

- FPNet full1明确使用全部训练折，包括NP样本。
- Saner final_model明确在全部数据上refit，包括原验证身份。
- 参考谱排除不能消除这些权重中的已知曝光；其他组件的训练身份还需分别审计。
- Saner best_validation_model和fold0可组成谱图/正标签身份排除更严格的组件实验，但还必须检查训练负候选，以及checkpoint选择时query和decoy身份的接触。不能仅凭文件名best_validation就称独立留出。

证据见 `reports/pretrained_exposure_audit.json`、`reports/pretrained_exposure_audit.md`，及后续补充 [fold0负候选与监测接触](reports/fold0_training_exposure_addendum_20261105.md)。早期审计按谱图/正标签身份定义排除；补充记录说明其不能证明结构从未作为负候选出现。完整Flex/V43诊断仍有价值：验证参考隔离和输出行为、拆解候选丢失、查明有无静默跳过；不据此承诺榜分。

## 运行

在WSL项目根先 `source scripts/linux_env.sh`。准备检查只加载索引，不初始化模型：

```bash
.venv-linux/bin/python scripts/run_validation_pipeline.py \
  --manifest runs/validation_pilot_v2_20261104/manifest.json \
  --pipeline flex --reference-mode class2 \
  --work-root runs/validation_flex_prepare_only --prepare-only
```

实际运行需新目录；Flex首轮失败现场位于 `runs/validation_flex_c2_20261105b`；c轮在会话中断后未完成、进程已不存在，具体退出原因未知，另存 `operator_stop.json`。当前恢复位于新d目录，以b为已验证来源，2026-11-05北京时间13:27:58启动。独立后台启动器 `scripts/run_logged_validation.sh` 将PID、启动/结束UTC和退出码写在外部console.log旁；仅凭旧receipt的running字段不能判断存活。V43的b轮在E2阶段被WSL内存不足终止，缺失输出继而被原源码误报为FileNotFound；`operator_*`保存了终止和内核证据，不能将该轮当作完整对照。下一轮V43使用新c目录和显式进程数限制。GPU推理与大型CPU预检均顺序执行。

首轮48例的ICE预算636秒不足：46个可覆盖分子仅32个完成，最终检查已拒绝这次运行。失败现场保存在上述Flex目录，不把已写出的CSV当作完整基线。后续48例显式使用 `--ice-budget 2400 --n1-budget 2400`，GL保留4000秒；覆盖、失败和预算状态独立审核。单个查询没有候选属于召回失败，要记录；未处理的分子、模型错误或整阶段被吞掉不当作成功。

`validation_run_receipt.json` 记录逐单元状态。Flex的详细基线日志位于 `submission_pipeline.log`。候选阶段证据写为 `validation_e1_candidates.jsonl`、`validation_e2_candidates.jsonl`、`validation_candidate_stages.parquet`，最终指标由冻结truth在推断后评估，标签不写入模型test输入。

## 第一个消融

实验定义在 `experiments/VAL001_NEURAL_INCREMENT.json`。Flex V0对V1/CUSTOM，采用预先固定的神经RRF权重，必须逐分子验证官方identity候选集合完全相同。physical、外候选救援、最终先验和V43完整架构差异不混入这个单因素比较。

通用评分：

```bash
.venv-linux/bin/python -m validation.evaluate \
  --truth runs/validation_pilot_v2_20261104/truth.csv \
  --predictions PATH_TO_VARIANT.csv --baseline PATH_TO_V0.csv \
  --require-fixed-candidates --output reports/VAL001_comparison.json
```

JSON中的运行状态和指标文件是实际进度依据；本文的运行命令和计划项不表示已经完成模型推断或获得正式榜分。

## 48分子全栈诊断结果

Flex d轮于2026-11-05北京时间13:50正常退出，48个查询全部处理、无padding；运行时审计通过，独立执行审计无失败或必须项未知，仅允许跳过原配置关闭的provenance overlay。旧32个完整ICE组与新14组逐项对齐，46个可覆盖分子完整评分，2个不支持分子明确保留为未覆盖。GL/N1精确输入复用检查通过。这是恢复耗时，不能证明相同预算的冷启动；[完整评价证据](reports/validation_flex_c2_20261105d/evaluation_report.json)。

| 配置 | NP MRR（24） | 跨库MRR（24） | 合计MRR（48） | 首选命中 | top25命中 |
| --- | ---: | ---: | ---: | ---: | ---: |
| V43完整对照 | 0.9201 | 0.7212 | 0.8207 | 36/48 | 46/48 |
| 基础排序V0 | 0.9792 | 0.7217 | 0.8504 | 38/48 | 46/48 |
| 固定候选轻量Saner V1 | 0.9792 | 0.7354 | 0.8573 | 38/48 | 46/48 |
| 固定候选CUSTOM | 0.9722 | 0.7180 | 0.8451 | 38/48 | 46/48 |
| V56完整最终输出 | 0.9792 | 0.6987 | 0.8389 | 37/48 | 46/48 |

V1相对V0增量0.006845，paired bootstrap95%区间[-0.000198, 0.017361]，仍包含零；NP不变，增量来自跨库面板。V0/V1/CUSTOM最终评分身份集合逐分子完全相同。完整最终输出含额外后处理，不是神经评分单因素结果。所有48例结果仍有已知模型训练曝光，尤其高NP分数不能作为真实泛化或奖牌证据。

V43 c轮于北京时间14:34:37完整正常退出，约39分钟；4进程下完整候选池和E2的1,597条候选顺序与Flex完全一致，ICE46、GL45、N146组均按支持范围完成，独立执行审计14/14通过。两完整方案首选44/48相同、共同漏掉同两例，首选错误phi相关0.8299。Flex final相对V43整体增量0.018244，但跨库为-0.022540，配对区间含零；不能据总体分盲目集成或选权重。详见 [完整架构对照](reports/VALIDATION_COMPARISON_2026-11-05.md)。

## 已完成的组件实验

`runs/component_neural_pilot_20261105` 已完成32分子、139谱的fold0指纹基线与Saner best-validation固定候选比较。排除两模型的查询谱/正标签训练身份及Saner checkpoint选择的query/decoy后，保留29个跨库身份和3个公开NP开发身份。fold0负候选池并未排除heldout结构，历史实际是否抽到这些身份未知；按公开源码重建，32例中9例属于训练监测组。公开脚本仅保存last/final，无按该指标选best的分支，但仍不能证明无开发接触。本轮应称谱图/正标签身份排除的组件诊断，不能称结构完全未见或独立留出。

| 面板 | 数量 | 基线MRR@25 | 加Saner | 首选命中变化 |
| --- | ---: | ---: | ---: | --- |
| 跨库组件 | 29 | 0.8046 | 0.8239 | 21/29 → 22/29 |
| 公开NP开发 | 3 | 0.5667 | 0.5667 | 1/3 → 1/3 |
| 合计（只作汇总） | 32 | 0.7823 | 0.7998 | 22/32 → 23/32 |

所有分子的最终候选身份集合完全相同；top25均为30/32。总体MRR增量为0.01749，分子级paired bootstrap 95%区间为[0, 0.04874]，仍包含零。一次运行101.08秒（含资产/数据校验和模型加载），Saner评分11.01秒。小样本正向信号保留为实验分支，不据此改主线权重或预测正式榜分。详细解释见 [组件实验报告](reports/COMPONENT_NEURAL_PILOT_2026-11-05.md)，原始证据为运行目录的 `evaluation.json`、`run_receipt.json`。
