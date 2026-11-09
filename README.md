# Enveda-CASMI-2026

针对 Kaggle 竞赛 **Enveda CASMI 2026 — Molecule Identification from Mass Spectra**（从质谱鉴定分子结构）的研究与实验仓库。当前公开榜（Public LB）最佳 **0.482**（正式提交 58129661，COMPLETE）。

## 项目概况

目标是给定质谱（支持 10 种加合物、质量范围可变、可能存在空候选）与候选分子池，输出按相似度排序的候选结构（MRR@25 评估）。本项目围绕三套公开高分方案做本地复现，并在此基础上做受控消融与优化，通过 Kaggle 每日 5 次提交额度验证真实榜分。

## 目录结构

| 目录 | 说明 |
| --- | --- |
| `scripts/` | 复现、验证、变体构建、Kaggle 提交/监控等工具脚本 |
| `validation/` | 本地验证与诊断管线（官方 metric 对齐、分子级 MRR、paired bootstrap、恢复与证据） |
| `tests/` | 针对脚本与提交守卫的测试 |
| `experiments/` | 实验定义（EXP001–004、VAL001、COMP001 等） |
| `submission/` | 各批次的提交 manifest、Notebook 与配方 |
| `third_party/` | 已归档的公开方案源码（Flexonafft、prvsiyan、canqiang、shiferaxa、majyles、evgendvorkin 等） |
| `reports/` | 各批次状态、审计、复现与诊断的 JSON/Markdown 记录 |
| `assets/`、`runs/`、`enveda-CASMI26-molecule-id-mass-spectra/` | 数据/模型/运行产物（已在 `.gitignore` 中忽略） |

## 关键文档

- [CASMI26_PLAN.md](CASMI26_PLAN.md) — 冲银牌作战计划与逐日执行状态
- [experience.md](experience.md) — 实战经验记录（按日期归因与决策）
- [REPRODUCTION.md](REPRODUCTION.md) — 公开方案本地复现
- [VALIDATION.md](VALIDATION.md) — 本地验证与诊断

## 环境

- Windows + WSL（Ubuntu，Python 3.12）；主流程 RDKit 2026.03.3
- GPU：RTX 4060 Laptop（约 8GB 显存），PyTorch 2.9.1+cu126
- 环境初始化：`scripts/linux_env.sh`（WSL）/ `scripts/windows_env.ps1`（Windows）
- 依赖：`requirements-reproduction-linux.txt`

## 说明

`assets/`（约 27GB）、`runs/`（约 7GB）、`enveda-CASMI26-molecule-id-mass-spectra/`（约 2.9GB train.parquet）为大型数据/权重/运行产物，未纳入版本控制。公开方案的部分权重/数据卡标注 CC BY-NC-SA 4.0，正式冲奖前需按主办要求逐项核验许可证。
