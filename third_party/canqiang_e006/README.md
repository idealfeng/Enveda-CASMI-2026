# Canqiang E006 V1 本地复现材料

原方案：[CASMI26 E006 Window 40 ICE Fallback True](https://www.kaggle.com/code/canqiang/casmi26-e006-window-40-ice-fallback-true)。

2026-11-04 已直接从 Kaggle API 拉到 V1 原始 notebook，SHA256 为 `ee55b55c7f5bdb08f1a8154396b18fdb0203fb7178b3a52429e0999e69ad7e53`。与独立复现仓库固定 commit `b4da1be06973a19c3db0ed94d9dda14416def023` 中的原版文件逐字节一致，30 个代码单元未改动。所有代码单元通过静态语法解析，尚未执行完整 notebook。

## 文件

- `original/canqiang_e006_v1.ipynb`：Kaggle 直接下载的原始文件。
- `original/canqiang_e006_v1.py`：原版代码单元的顺序导出，便于阅读。
- `original/api_metadata.json`：本次直接拉取的公开元数据，记录 V1、镜像和输入引用。
- `upstream_mirror/`：固定 GitHub commit 的原版、复现版及成绩证据；这些证据属于原复现者，不是本机成绩。
- `dependency_sources.json`：16 个固定输入版本、历史许可标签、完整文件清单和本地状态。
- `dataset_file_inventory.json`：本次通过 API 分页读取的 16 个版本的全部文件名和大小。
- `minimal_fpnet_source/`：从 `ahmedberatozer/casmi26-v3-models/4` 取得的最小 FPNet 源码，逐文件哈希见其中的 manifest。
- `engine_source_v4b/`：从 `ahmedberatozer/casmi26-v4b-models/4` 取得的引擎 Python 源码、清单和许可说明；大型资源和权重未在本目录完整下载。
- `fpnet_smoke.py`：独立组件运行入口，见下文。
- `run_local_linux.py`：完整 30 单元的 Linux 执行入口，保留原版排序逻辑和所有模型/阶段断言，仅记录路径与 GPU 观察适配。

## 当前可进行的组件检查

真实权重已下载到工作区的 `assets/kaggle/ahmedberatozer/casmi26-fpnet-full1/v1/fpnet_full1.pt`，198,791,233 字节，SHA256 为 `d13a3611e499d7783c4a6fce5b04363eb297dcf70f2d7d00bb66f9ff1f547123`。下载回执在该目录。

在已有 numpy、pandas、pyarrow、torch 的 Linux 环境中运行：

```bash
.venv-linux/bin/python third_party/canqiang_e006/fpnet_smoke.py --molecules 3 --device cuda
```

也可以给 `--python /path/to/python`，或用 `--checkpoint`、`--test`、`--output-dir` 指定路径。Windows 上同样可以直接运行此组件脚本。它保留原始模块不变，用 `weights_only=True` 读取张量检查点，计算前三个分子的全部实测谱的指纹 logits 和元素预测，输出 `runs/fpnet_smoke/logits.npz` 及 `summary.json`。

该脚本仅验证 FPNet 权重与真实谱输入的兼容性。分子 logits 是单谱 logits 平均，不含 E006 的合并谱分支、候选召回、排序、双引擎融合和谱模拟。因此即使运行成功，也不能称为完整 E006 复现，更不能据占位测试推断榜分。

本机 CPU 已完成真实权重组件检查：3 个分子、12 张谱、10,226 维 logits，输出全部有限，模型加载与推断阶段 1.469 秒。实测回执在工作区 `runs/fpnet_cpu_smoke/summary.json`，不属于完整排序或榜分复现。

## 完整 Linux runner

先准备，不执行模型：

```bash
.venv-linux/bin/python third_party/canqiang_e006/run_local_linux.py \
  --input-root assets/kaggle \
  --work-root third_party/canqiang_e006/runs/linux_exact \
  --competition-root enveda-CASMI26-molecule-id-mass-spectra \
  --shared-spec-cache runs/shared_spec_cache \
  --prepare-only
```

去掉 `--prepare-only` 后才会执行原始代码单元。运行前会写 `local_run_receipt.json`，列出 16 个历史附加输入、实际选中版本、运行必需文件、文件大小差异和阻塞项；同目录保留每个适配单元及修改哈希。仅将 T4 身份检查改为记录本机 GPU，并将 Kaggle 路径映射到独立输入视图和输出目录；Python、RDKit、数据、模型清单、排序和模拟器健康断言均保留。

默认 `--input-mode exact` 使用历史固定运行输入。显式 `--input-mode available` 可选择本地已有较新版本，但回执会标记版本替换及文件差异，该模式不能声称复现历史成绩。输入视图仅附加已选版本，避免不同版本被原始 `glob()` 混用。

运行必需输入与仅附加输入分开处理：历史 hengck23 V2 不含原代码可选分支查找的 `dreams_np_mass.npy`；其 6.86GB embedding 不会因此被强制下载。历史 eveliaveldrine V3 是 cp313 wheel，Python 3.12 优先使用 ICEBERG 自带的兼容 wheel。它们缺失仍会记录，但不会单独阻止运行。源代码的可选分支及兼容性检查保持原样。

`--shared-spec-cache` 使用工作区 `scripts/reproduction_io.py` 验证共享谱库的源清洗代码、训练数据和结构顺序，再将四个已完成缓存链接到本次 `work/`，避免主 Engine 1 重建。大谱数组、候选指纹/碎片数组和外层训练指纹改用 copy-on-write 内存映射；原始数据和模型排序不变，改动及 helper 哈希写入回执。Engine 2 的原始 CSR 是不同格式，不能直接复用这个清洗缓存。

2026-11-04 已完成 Linux `--prepare-only`：30 个代码单元成功准备；当时尚缺的实际运行文件在 `runs/linux_prepare_exact/local_run_receipt.json`，下载继续后应重新准备。该次检查未执行 notebook。

额外已下载 popularity-prior 历史 V4 的四个必需数组到 `assets/kaggle/dmitriigluzdov/casmi26-pubchem-popularity-prior/v4/`，总计约 426.35MB；全部匹配上游 MANIFEST 的 SHA256，NPY 形状与 float16 类型也通过检查，见该目录 `e006_array_audit.json`。

也已下载 `prvsiyan/chebi-lipidmaps-casmi26/1` 的全部三个 bio 文件到共享 assets（60,447,249 字节）。质量数组和指纹数组均为 62,744 行，指纹为 867 字节打包表示；形状、有限正质量及排序检查通过。Kaggle API 当前 V1 元数据明确标注 **CC BY-NC-SA 4.0**，该数据未列出额外 LICENSE/MANIFEST 文件，回执保留了实际 API 许可元数据。

## 完整方案和较轻切入点

完整 E006 引用的 16 个版本，文件大小合计 **22,298,955,942 字节（约 22.30 GB）**，不含比赛原始数据、缓存和环境。原始 notebook 会在可见占位数据上只预测 12 个分子，其余行为是提交预览占位，不能直接拿预览 CSV 当完整预测。

完整 notebook 强制检查 T4、Python 3.12、RDKit 2026.03.3 和 `/kaggle/input` 路径；ICEBERG/GLACIER 另依赖隔离的 RDKit 2025.03.6。因此原版不能在本机 4060 的 Windows 环境原样跑通，所有本地适配必须单独保存。

不运行模拟器的主 Engine 1 可从以下依赖切入：

1. `ahmedberatozer/casmi26-v4b-models/4`：Python 包、`MANIFEST.json`、所列 FE 模型及 ranker、`code/fe_v4/res/` 资源。
2. `ahmedberatozer/casmi26-v2-pool/1` 的全部七个文件：`pool_meta.parquet`、`pool_fp.npy`、`pool_frag_off.npy`、`pool_frag_mass.npy`、`fp_bits.npy`、`train_structs.parquet`、`train_fp_sel.npy`。
3. `ahmedberatozer/casmi26-fpnet-full1/1/fpnet_full1.pt`。
4. 本地 `train.parquet` 通过 `casmi.build.build_spec_cache()` 建库。
5. 若保持原候选流行度重排，还需 popularity-prior V4 的 `pool_lsid.npy` 和 `pool_lpmid.npy`。

入口对应原始代码单元 14、15、17；它不需要先拉 7.2GB PubChem 全库、6.86GB DreaMS 输入，也不必启动 ICEBERG/GLACIER。这样运行的结果仍是 Engine 1 子管线，不能等同完整 E006。

## 许可和结果归属

Notebook 署名单元声明 Apache-2.0，输入组件保留各自许可。独立复现记录中部分输入标为 CC BY-NC-SA 4.0 或 Other，不能以 notebook 的代码许可替代数据/权重许可核查。本地研究材料保留这些标签；尚未确认其适合获奖最终管线。

历史 0.440 来自独立复现者的正式提交 `57067224`，详见 `upstream_mirror/evidence/submission_result.json`。本目录不包含本机正式提交或隐藏测试成绩。
