# 二、身份隔离方案与泄漏审计（阶段二）

## 结论

- 统一身份采用 **`chem.score_key()`**（互变异构 canonical + 去立体 + InChIKey14），与官方评分身份一致。
- 泄漏审计通过：**48/48 身份重算一致、全部存在于候选池（每身份 1–4 个别名行）、Class-3 排除按 key 可移除全部别名**，无结构泄漏回父体池。

## 统一分子身份

- `chem.score_key(smiles)` = `TautomerEnumerator().Canonicalize` → `RemoveStereochemistry` → `MolToInchiKey` → 前 14 位。
- 因此：不同 SMILES 表示同一结构、tautomer、立体异构 → 同一身份（测试 1/12 已验证）。

## 三种配对验证场景（任务书 4.2）

| 场景 | 结构 | 参考谱 | 模拟 |
|---|---|---|---|
| A（Class 1 对照） | 保留 | 保留 | 已有参考谱 |
| B（Class 2 模拟） | 保留 | 移除 | 有结构、无参考谱 |
| C（Class 3 模拟） | 从所有候选来源移除 | 移除 | 需从头生成 |

## 本实验的隔离实现（bounded）

- 本实验聚焦**生成器能力**（`derive.py`），不依赖谱检索通道，因此：
  - **Class 3 = 把真结构身份从父体候选池中彻底移除**（`pool_key != tid`）。
  - 父体 = 候选池中质量差命中某反应模板组合的结构（bounded proxy for 谱相似母体检索）。
- 完整隔离（谱检索 + 全部候选来源 + 参考谱）已在任务书 4.2 定义为要求，本 bounded 实验只覆盖池级身份排除，已在 step3 产物 caveats 中标注。

## 泄漏审计结果（`step2_leakage.json`）

- 48 个 dev 身份：`identity_consistent = 48`（重算身份 == 冻结 truth 身份）。
- 48 个身份全部存在于候选池（`identities_present_in_pool = 48`），单个身份最多 4 个别名行。
- 因此 Class-3 排除（按 key）能移除该身份的全部别名，不会以其它 SMILES 形式泄漏回父体池。

## 产物

- `step02_isolation.md`（本文件）
- `artifacts/step2_leakage.json`
- `step2_leakage.py`
