# 公开方案本地复现

工作日期：2026-11-04。所有原始 Notebook 保留不改；本地兼容改动、输入版本和运行结果分别留有回执。本地可见测试是占位数据，运行成功不代表重现隐藏测试榜分。

## 当前状态：三套 12 分子全流程均已跑通

2026-11-04 用户已明确要求继续。上次暂停时已停止全部后台任务；本轮从保留的 D 盘文件和缓存恢复。

- 三套原始源码、适配入口、必要权重/候选文件和共享谱缓存保留在 D 盘。
- 最后一个 5.52GB PubChem SMILES 数组已完成并通过固定 SHA-256 校验；Flexonafft 下载清单 444 项全部完成。三份共享 PubChem 硬链接已完成，prvsiyan 最小依赖 197 项复核通过。
- CPU 与 CUDA 指纹组件实谱检查均已通过。V43、E006、Flex V56 的 `b` 轮均完整运行成功，最终 CSV 已与准确版本的上游输出对照；首选均为 12/12 一致，部分后续候选及顺序有差异。
- 最新汇总见 `reports/reproduction_status.json`。`reports/smoke_batch_status.json` 保留首轮 `a` 的失败，不能用它代表修复后的最终状态；详细结果以各 `b` 轮 receipt 和 SHA-256 绑定的 comparison 为准。
- Linux 科学计算与 CUDA PyTorch 环境已补完；4060 实际 GPU kernel 检查通过。精确版本见 `reports/reproduction_environment.json` 和 `reports/reproduction_linux_freeze.txt`。
- 后续下载、缓存、模型、环境及临时目录均固定在 `D:\Paper\casmi`。Linux 先 `source scripts/linux_env.sh`；Windows 进程显式设置 `TEMP/TMP/PIP_CACHE_DIR` 到项目 `.cache`。不要更改全局环境或执行策略。
- 暂停前曾使用 Linux 默认 `/tmp` 的安装已中止；已观察的本任务临时目录全部消失，检查回执 `reports/linux_temp_audit.json`。不删除用户其它缓存。

本轮已完成：补齐 CUDA 环境并做 GPU 检查、校验共享输入、顺序跑三套原始 smoke、核验模型/模拟器与最终重排阶段、比较上游输出。PubChem 三数组的固定哈希已校验，约 7.21GB 的共享硬链接已建立；prvsiyan 197 项最小输入与 Flexonafft 444 项下载清单均已完成。

## 已固定的源码

| 方案 | 上游公开记录 | 本地源码与入口 |
| --- | --- | --- |
| Flexonafft Evidence Gap | Best 0.479 / V56；另保存 V61 | [源码与说明](third_party/flexonafft_evidence_gap/README.md)，`run_local.py` |
| prvsiyan Analog Propagation | 0.456 / V43 | [源码与说明](third_party/prvsiyan_analog/README.md)，`run_local_linux.py` |
| Canqiang E006 | 上游正式复现记录 0.440 / V1 | [源码与说明](third_party/canqiang_e006/README.md)，`run_local_linux.py` |

源码、API 元数据和原始 SHA-256 在各方案目录。Kaggle API 没有为所有方案暴露历史输入版本；实际下载的版本在依赖清单中单独记录，不能把当前输入搭配精确源码称为完整历史复现。

## 环境与本地适配

- Windows 本地 Python 原环境保留；`.venv` 只用于下载和 Kaggle CLI。
- `.venv-linux` 是工作目录内独立的 Ubuntu WSL / Python 3.12 环境。科学计算依赖见 `requirements-reproduction-linux.txt`。
- CUDA PyTorch 采用官方 cu126 wheel，与本机 NVIDIA 驱动 566.07 配合；实际 GPU kernel 检查由 `scripts/environment_probe.py` 记录。
- 原 Notebook 的 `/kaggle/input` 和 `/kaggle/working` 映射到项目内版本固定的输入视图和独立运行目录。T4 限制按需改为记录实际 4060，模型与排序参数保留。
- 神经模型直接加载公开权重，Engine 2 启动时仍会按原脚本从现成特征拟合树排序器。因此初始化包含真实 CPU 训练成本，不能把整条管线称为纯粹加载权重推断。
- 原版会整载入大数组。`scripts/build_shared_spec_cache.py` 调用原始清洗函数分批构建共享缓存，`scripts/reproduction_io.py` 提供定点 copy-on-write 内存映射。一个完整小 row group 已与原版的三个峰数组、offset 和 metadata 精确比对。Engine 2 使用原始峰缓存，不能拿清洗缓存替代。

## 文件与依赖下载

`assets/kaggle/<owner>/<slug>/v<version>/` 保存公共输入，下载生成独立 SHA-256 receipt。不会把凭证写入项目。

```powershell
$env:TEMP = 'D:\Paper\casmi\.cache\tmp-windows'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'D:\Paper\casmi\.cache\pip-windows'
New-Item -ItemType Directory -Force -Path $env:TEMP,$env:PIP_CACHE_DIR | Out-Null
.\.venv\Scripts\python.exe scripts\download_public_assets.py third_party\prvsiyan_analog\minimum_inputs.json --workers 4 --report reports\prvsiyan_asset_downloads.json
.\.venv\Scripts\python.exe scripts\download_public_assets.py reports\flexonafft_download_manifest.json --workers 6 --report reports\flexonafft_asset_downloads.json
.\.venv\Scripts\python.exe scripts\link_shared_assets.py
```

最后一条命令在三个 PubChem 数组下载完成后执行：校验上游固定 SHA-256，再用硬链接复用约 7.21GB，避免重复下载。完整的 popularity dataset 约 80GB，但本次仅按源码下载实际引用的文件。

## 已完成的真实检查

- Canqiang FPNet 的真实权重已下载并校验：198,791,233 字节。
- Windows CPU 实谱推断通过：3 个分子、12 张谱、输出 10,226 位指纹 logits，数值有限且非恒定。模型加载与推断阶段约 1.47 秒。这只是组件检查，不含候选检索、排序及 E006 merged-view 分支。
- 组件输出：[summary.json](runs/fpnet_cpu_smoke/summary.json)、`runs/fpnet_cpu_smoke/logits.npz`。
- Linux CUDA 实谱组件检查通过：同样 3 个分子、12 张谱，首次权重加载与推断约 9.64 秒，峰值显存分配约 317MiB。首次 CUDA 初始化包含额外开销，不能直接据此比较 CPU/GPU 吞吐；输出见 `runs/fpnet_cuda_smoke/summary.json`。
- 共享训练谱缓存已完成：2,539,608 张谱、133,228,108 个清洗后峰，约 150 秒完成扫描与构建。该耗时不包含后续模型推断。
- 端到端管线的真实完成状态请看下方各 run receipt；原始 Notebook 自带的历史输出不当作本次运行证据。

首轮 `a` 的失败记录保留在 `reports/smoke_batch_status.json`。恢复运行采用新的 `runs/{prvsiyan,canqiang,flexonafft}_smoke_20261104b` 目录。三套准确版本的上游原始 CSV 和 active12 子集保存在对应 `third_party/.../upstream_output/`；最终输出用官方 RDKit 环境中的 `scripts/compare_smoke_output.py` 比较。

首轮修复三项本地兼容问题：补齐 `PyYAML==6.0.2`；给普通 Python 执行器注入 Notebook 的 `display`；Flex 的 Saner bundle 改用真实父目录与叶子文件软链接，兼容 Python 3.12 的递归查找。原始 Notebook、模型和排序规则未改。

### 恢复运行实测

| 方案 | 实际状态 | 与准确版本上游 active12 比较 |
| --- | --- | --- |
| prvsiyan V43 | 完整通过，恢复耗时 575.604 秒；复用此前耗时 525.789 秒的 Engine 2 输出 | top1 12/12、前6名 12/12 一致；候选集合 9/12、完整顺序 3/12 一致 |
| Canqiang E006 V1 | 完整通过，恢复耗时 532.866 秒；复用首轮耗时 418.919 秒的 Engine 2 输出 | top1 12/12、前4名 12/12、候选集合 12/12 一致；完整顺序 2/12 一致 |
| Flex V56 | 完整通过，1597.724 秒（26分38秒）；未复用 Engine 2，使用已建共享谱缓存 | top1 12/12、候选集合 10/12、完整顺序 4/12 一致 |

V43 的 ICE、GL、N1 均正常，无预测失败。部分尾部排名与上游不同，根因尚未隔离，不能称为逐项完全复现；也不能直接归因于 GPU 浮点误差。这 12 个占位例子未覆盖 N1 的关键盲区分支。详细证据见 `reports/prvsiyan_smoke_comparison.json`、`reports/prvsiyan_smoke_diagnosis.json`。

E006 的 ICE、GL 均正常，无预测失败，尾部 27/28/29/31 单元全部完成。与上游的排序差异始于第5名、位移最多2名，原因仍待隔离；这些例子没有覆盖成功的有限 ICE 回退分支。最终文件绑定、对照和诊断见 `reports/canqiang_smoke_comparison.json`、`reports/canqiang_smoke_diagnosis.json`。

Flex 的 ICE、GL、N1、Saner 神经评分及最终层均实际执行。神经模型处理基础候选 688 行和外候选 240 行，无输入失败；外部参考谱扩展增加 751 张谱、469 个结构，使用独立文件，未覆盖共享 CSR。物理层未超时，merge/final layer 均为 `applied`。执行审核为 `passed_with_allowed_skips`，没有失败或必需的未知项；唯一跳过项是原配置关闭的 PROVENANCE。两例候选集合差异在冻结基线阶段已经存在，各换一个候选，原因尚未隔离。证据见 `reports/flexonafft_smoke_audit.json`、`reports/flexonafft_smoke_comparison.json`、`reports/flexonafft_smoke_set_differences.json`。

以上全部只实际处理 12 个占位分子，CSV 中另有 388 个上游填充行。不是 400 分子完整推断，也没有复现 0.456 / 0.440 / 0.479 的隐藏榜分。耗时不含下载、安装和先前约150秒的共享谱缓存构建；也不能按分子数简单外推隐藏测试耗时。

恢复耗时不是冷启动耗时。Engine 2 复用先核对源码、生成脚本、查询内容、输入绑定与先前成功记录，后续模型与重排仍实际执行。旧运行没有在检索结束时对全部输入重新哈希，复用证据的边界保留在 binding receipt 中。

## Linux 运行命令

在 Ubuntu WSL 中，工作目录为 `/mnt/d/Paper/casmi`。

```bash
source scripts/linux_env.sh
.venv-linux/bin/python scripts/environment_probe.py
.venv-linux/bin/python third_party/canqiang_e006/fpnet_smoke.py --molecules 3 --device cuda --output-dir runs/fpnet_cuda_smoke

.venv-linux/bin/python scripts/prepare_prvsiyan_inputs.py
.venv-linux/bin/python third_party/prvsiyan_analog/run_local_linux.py \
  --input-root runs/inputs/prvsiyan_v43 --work-root runs/prvsiyan_v43_smoke \
  --competition-root enveda-CASMI26-molecule-id-mass-spectra \
  --shared-spec-cache runs/shared_spec_cache --mmap-pool

.venv-linux/bin/python third_party/canqiang_e006/run_local_linux.py \
  --input-root assets/kaggle --input-mode exact --work-root runs/canqiang_e006_smoke \
  --competition-root enveda-CASMI26-molecule-id-mass-spectra \
  --shared-spec-cache runs/shared_spec_cache

.venv-linux/bin/python third_party/flexonafft_evidence_gap/run_local.py \
  --input-root assets/kaggle --work-root runs/flexonafft_v56_smoke \
  --shared-spec-cache runs/shared_spec_cache
```

前述 Notebook 默认保留上游 12 分子 smoke。其余占位行可能由上游填充，不应把生成了 400 行文件误当成处理了 400 个分子。Flexonafft 的 `--full` 才会启用全可见测试和较长模拟器预算，仍然不是隐藏测试。

对照及汇总命令（已成功执行）：

```bash
.venv-linux/bin/python third_party/flexonafft_evidence_gap/audit_local_run.py \
  --work-root runs/flexonafft_smoke_20261104b --output reports/flexonafft_smoke_audit.json
.venv-linux/bin/python scripts/compare_smoke_output.py \
  --reference third_party/flexonafft_evidence_gap/upstream_output/flexonafft_v56_active12.csv \
  --actual runs/flexonafft_smoke_20261104b/submission.csv \
  --output reports/flexonafft_smoke_comparison.json --metric-identity
.venv-linux/bin/python scripts/summarize_reproduction.py
```

下一步按 [组件对照与首个验证实验](reports/public_pipeline_components.md) 建立结构级验证，固定候选集测试 Saner 神经排序增量，再考虑其他层和集成。三套管线高度共享骨干，不能用占位例子选冠军或直接等权投票。

## 许可证的实际发现

部分高分管线核心输入的当前数据卡标注 **CC BY-NC-SA 4.0**；代码 Apache-2.0 不会覆盖这些权重或数据。当前工作用于本地研究复现，尚未提交或发布方案。冲银管线采用哪些资产，需要按主办要求逐项核验或替换；不能仅凭公开可下载推断可获奖。
