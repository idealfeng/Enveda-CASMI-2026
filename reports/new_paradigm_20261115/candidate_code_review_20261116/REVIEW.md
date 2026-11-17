# FIORA 固定八题候选排序：独立源码审查与 evaluator 修复

2026-11-16。审查只读取源码、既有路线结论和模型参数配置；没有打开 `evaluation_truth_metadata.json`、coverage 逐例、任何真实 candidate score 行或模型权重，没有运行预测或计算实际排名指标。根代理负责真实推理和独立评价。本报告只放行评价程序的源码契约，不代表完整运行成功或榜分提升。

## 结论与修复

发现原 evaluator 在同一个 `dict(...)` 中两次使用 `top25=`，语法检查实际返回 `SyntaxError: keyword argument repeated: top25`。原 SHA 为 `2cca287bf0d2c3a5f9bef5af5a8036407b9a570fb67e31ec7c571023df7b923f`。根代理随后授权仅修改这个尚未执行的新 evaluator。

修复将命中布尔值命名为 `top25_hit`，保留 `top25` 为实际输出名单，并同步修改 Recall@25 汇总。构造输出后再调用 `validation.metric.first_correct_rank` 和 `reciprocal_rank`，要求实际前 25 个输出的官方 rank/RR 与内部结果一致。若没有任何有效官方身份可构造非空输出，程序失败，不把非法空输出当零分。

同时把固定 manifest SHA、模型/参数 SHA、推理源码 SHA、8 题和 785 行总数显式写入 evaluator；核对预推理 configuration 与 source bindings 的 SHA、其与最终 receipt 的内容一致性，以及保存的 executed scorer 副本。所有原候选 payload、顺序、索引和两个模型的有限有效分数仍逐行核对。缺分拒绝的 gate 状态也改为明确的 refused。

- 最终 evaluator SHA256：`79c409cd568fc7ae1571bb4d856cee831d48e5b38f65c83f92ea9576606ca261`。
- scorer SHA256：`a87b089cad27507161a6f4fe592e0e17c1f618ed44f27b1a65678cda6a93eae7`，本代理没有修改。
- 已修复的语法和字段混用为真实阻塞项；没有发现其他必须阻止本次固定组件评价的源码缺陷。实际成功仍取决于根代理获得完整真实 receipt 并运行 evaluator。

## 冻结、无标签边界和缺分策略

scorer 输入白名单函数只打开 `candidate_freeze.json`、`queries.json`、`candidates.json`；manifest 内其他文件名和 SHA 只是已冻结元数据，并不读取 selection 或评价真值。模型 verification 和 migration receipt 用于确认固定 500 步权重与迁移来源，不用于重新选择查询、模型或系数。候选的公式、分子量和元素组成由当前候选结构本身产生，不是查询真结构标签。

scorer 用同一个候选循环和同一个构图结果分别运行 step0 与 step500。每行保留原 payload；构图或任一模型失败保留 null/status，绝不补入候选或删除原行。其缺分 receipt 状态是 `completed_candidate_traversal_with_missing_predictions`，该分支进程可能仍 exit0。因此不能仅看进程退出码宣称完整推理成功；必须检查成功状态和所有行的双模型分数。

evaluator 仅接受 `completed_dual_checkpoint_candidate_spectrum_scoring`、`all_candidates_scored=true`、`all_scores_finite=true`。在第一次读取评价 metadata 前，核对所有 8 题、全部 785 个候选的原始集合与顺序、每行 step0/step500 均为 scored 且是有限数。任一缺失即拒绝整次评价，保留 failure、不开 truth、不生成成绩、也不计为 0 分。即使 receipt 虚称成功，逐行检查仍会拒绝。

完成 gate 后，才读与固定 manifest/window/selection SHA 绑定的评价 metadata，并独立重算全窗与 cap 后官方身份覆盖。cap 排除真值的题目仍保留在 8 题分母，候选可用性原因与排序差别分别记录；不按结果补入、放宽 cap 或重选。

## 质量、CE、图和真实谱分数

候选准备脚本使用观测 precursor 减原 `casmi.chem.PROTON`，在按质量排序的固定池中查询 10 ppm；仅空窗用 30 ppm，超过 128 按绝对观测质量误差/pid 截取后恢复原池顺序。没有真公式、真质量或真结构注入。evaluator 绑定原准备源码和原池 SHA，再核对冻结窗口选择列表。

scorer 对每个候选原 SMILES 建立原生分子图，使用与训练准备相同的 atom/bond features、depth=1 片段图、`with_labels=False`。通过编译出的原生 `compiled_mass_map` 将模型向量还原为 m/z，并检查单图 segment pointer 和完整长度。只保留 forward directed edge 的原生片段，NaN/ring-no-fragment channel 不参与谱分数；两个前体 channel 显式排除。

查询始终是原生 `timsTOF/[M+H]+` 与冻结的单一实测 CE eV。迁移参数确有 instrument `['HCD','timsTOF']`，静态输入为 19、RT 输入为 18。原 encoder 对 CE 做 0–100 线性归一化；没有把 timsTOF 重命名为 HCD，也没有用真值选择 CE。两模型的 metadata 和构图完全相同。

谱分数使用固定 `raw>.001` 和原生 sqrt cosine，0.01 Da。实测与预测共同按同一个观测 precursor 的 `max(.01Da,100ppm)` 窗去前体；候选理论 precursor 仅作记录。重复 m/z 强度在 native `spectral_cosine` 中累计后再开方。其合并方法为相邻 bin 链式合并，可能把链两端相距超过 tolerance 的峰合并；已明确标注，不能解释为严格一对一峰匹配。无剩余真实/预测碎片时得到 0 分是可计算的空谱匹配结果，与缺失预测 null 不同。

## 排名和官方身份

按分数降序、原 candidate_index 升序断平手；先按官方身份移除重复，invalid 官方身份从构造的输出列表排除并记录，再截取前 25。这是预先声明的输出列表构造策略，官方 metric 自身并不删除重复或 invalid 位置。最终 evaluator 对构造出的实际输出字符串调用官方 local helper 核验 rank/RR，避免混淆这两层语义。

`validation.metric` 强制 RDKit `2026.03.3`，身份规则为 remove stereo、canonical tautomer、InChIKey14；其归档官方源码 SHA 为 `bf8535f01bf73268a52819b38e7f6b205e37ec127c268e48081b780a10b609dd`。evaluator 另记录实际 local metric 源码 SHA 并在结束前复核所有绑定文件未变。

## 验证证据与限制

`validation.json` 记录两个当前脚本均通过 `compile`，并保存原语法失败证据。三个独立微型结构夹具分别缺失 receipt、返回缺分状态、返回非有限分数声明，均在真值读取前拒绝、写 failure 且不生成评价成绩。夹具只能读取各自的伪 receipt；读取 truth、真实 score 或 query/candidate 输入会直接触发断言。所有产物写在本目录的 D 盘子目录，没有修改推理脚本、模型、既有实验、全局文档或索引。

本审查没有运行模型、读取实际 score rows、实际 truth 或算任何真实排名指标；不证明 785 候选全部可构图、全部 GPU 推理成功、整个 evaluator 已在真实文件上通过，亦未单独验证二进制依赖指纹。原生源码与模型有前后 SHA 绑定，第三方运行时的数值行为仍由真实执行环境决定。评价脚本读取 Linux 版 RDKit/Arrow 资产，实际应在本项目固定 WSL 环境运行。8 题来自既用 development100、从 98 graph-ready 查询中固定抽取，MSnLib 曝光未知，仍然只是组件开发证据。
