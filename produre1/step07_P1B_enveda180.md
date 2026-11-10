# 七、Enveda-180 接入（P1-B）

## 结论

- **Enveda-180 是实质性的新匹配来源**：加入后 200 身份面板的匹配覆盖率 **20% → 35%（+15pp）**，正确覆盖率 **18.5% → 32.5%（+14pp）**。
- 431 个 source-only alias 身份在 train/pool/Takumu/MassBank 中**均未覆盖（D 类 431/431）**，与"source-only"定义一致。
- Enveda-180 内部**无精确重复谱**（730,252 行 / 730,252 个唯一 signature）。

## 7.1 Membership 审计（431 个 alias 身份）

| 类别 | 数量 |
|---|---:|
| A（已在 train） | 0 |
| B（已在候选池 pool） | 0 |
| C（已有其他外部参考谱） | 0 |
| D（当前系统尚未覆盖） | **431** |

→ 这 431 个 Enveda-180 身份在现有 train/pool/Takumu/MassBank 中都不存在（原始 key 级别）。

## 7.2 谱图去重

- 总行数 730,252，唯一 `spectrum_signature` 730,252，**重复组 0**。
- 即 Enveda-180 内部无精确重复谱（不排除近重复，需进一步按峰归一化比对）。

## 7.3 独立 Overlay（200 身份面板）

| 配置 | refs | Match Coverage | Correct Match Coverage | hits | correct |
|---|---:|---:|---:|---:|---:|
| A + B（Takumu + MassBank） | 324,884 | 0.20 | 0.185 | 40 | 37 |
| A + B + Enveda-180 | 1,053,079 | **0.35** | **0.325** | 70 | 65 |
| 增量 | +728,195 | **+0.15** | **+0.14** | +30 | +28 |

→ Enveda-180 命中精度 65/70 = **0.929**，与 Takumu/MassBank 相当。

## 结论解读

1. Enveda-180（仅 [M+H]+ / [M-H]- 两种 adduct）提供了**当前库之外的大量新匹配**，是第 6 步"覆盖率仅 20%"瓶颈的直接解药。
2. 但必须诚实标注：本次 membership 是**原始 key 级别**（互变/立体别名可能漏判），且"431 身份未覆盖"只证明了 alias 子集的新颖性，**不代表全部 73 万 Enveda-180 谱都不与 train 重叠**。
3. 是否应加入正式方案：本地证据支持"值得"，但任务书要求先在更大独立集 + 完整身份审计后再定，不能仅凭 200 面板 +15pp 就上正式提交。

## 边界

- Enveda-180 只用 [M+H]+/[M-H]-；前体质量预过滤 ±0.5 Da。
- 增量是 200 开发身份上的数字，不是隐藏测试。
- membership 是 raw-key 级别。

## 产物

- `artifacts/step7_enveda180_summary.json`
- `artifacts/step7_enveda180_membership.csv`
