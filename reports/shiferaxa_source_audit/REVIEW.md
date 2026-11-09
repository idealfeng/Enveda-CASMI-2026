# shiferaxa/casmi26：本地源码审查

审查日期：2026-11-04。结论：**值得拉取，主要补我们的验证与自训练工程，不应作为第四套独立强榜分模型。**

## 已获取的内容

- 上游：<https://github.com/shiferaxa/casmi26>。
- 当前 `main` 通过 `git ls-remote` 解析到 `41f0c5dde78e551fb5aedbb3421156a38b3f427d`。
- 固定提交的官方 GitHub ZIP 已提取到 `D:\Paper\casmi\third_party\shiferaxa_casmi26`；这是源码快照，没有 Git 历史。
- ZIP 392,024 字节，展开 1,111,582 字节，77 个文件；无 LFS 指针、无模型/数据 payload。未安装依赖，未运行仓库代码。
- 下载、临时文件和回执均在 D 盘。逐文件 SHA-256 及 ZIP 来源见 `download_receipt.json`。GitHub 元数据 API 当时受未认证速率限制；采用 Git 协议解析 SHA、官方 codeload 提供精确提交源码，未依赖搜索缓存来确认提交内容。
- `LICENSE` 为 Apache-2.0，`NOTICE` 署名 Amha Shiferaw 并说明 prvsiyan/haideptry 派生代码。该许可不自动覆盖外部 Kaggle 数据、权重；仓库未附其 payload。

## 实际内容与我们的关系

四通道是：谱库 entropy similarity、质量平移后的 analog/fingerprint 相似度、MetFrag-lite 的峰强解释率、谱到指纹 Transformer 的 logits 点积，然后 HistGradientBoosting 排序。`src/casmi/fork/core.py` 是较早 prvsiyan/haideptry 公共管线的模块化移植，不等于今天 prvsiyan V43 的全部分支。

我们正在复现的 E006/V43/Flex 已继承这条骨干，并进一步使用 Ahmed Engine 1、独立 PubChem 通道、ICEBERG/GLACIER、identity 融合，以及 Flex 的 Saner 神经层等。直接把这个仓库再作为一个投票成员会重复证据。它有自己的指纹模型训练代码；只有实际训练、严谨留出并确认错误互补后，新的 checkpoint 才可能提供新增信息。

| 可用内容 | 具体文件 | 如何用于我们的下一步 |
| --- | --- | --- |
| 可分阶段复用的实验台 | `src/casmi/fork/harness.py:1–23`，`channels`/`evidence`/`rank` | 借鉴将昂贵特征计算与便宜重排分开；改造为调用我们现有冻结管线的特征，不退回旧基线 |
| 同仪器面板及三种 mask | `scripts/run_fork_val.py:1–16, 105–118` | 复用 np-examples 查询提取、留库/留候选场景和失败分解的结构；先修官方身份与泄漏边界 |
| 排序器训练行导出 | `scripts/dump_rank_features.py`、`scripts/train_ranker.py` | 提供由真实候选生成训练行、按查询分组评估和对比公共 ranker 的范例；按我们当前特征重新导出 |
| 指纹模型数据预处理 | `kaggle/prep/notebook.py:140–148` | 将 np-examples 的原始身份全体排除、另留 2% 结构验证；改为官方评分身份后可作为我们自训数据管线起点 |
| 指纹 Transformer 训练 | `kaggle/train_fp_v2/notebook.py:1–25, 270–300` | 六层 d512 模型，6930-bit 头；BCE + 63 个同质量窗口 hard negatives，merge views、峰增强、验证最优 checkpoint；可作为后续自训起点，尚未在本机训练 |
| 实验失败经验 | `docs/plan.md` 的 dated log | 作者记录随机 overlap holdout 与 np250/LB 的 ranker 顺序相反、自训更多种子边际收益很小、ranker rows 比继续加种子更关键、镜像丢 pin 会静默掉阶段；均为作者报告，非本机验证事实 |

## 采用前必须改的具体处

1. **评分不能直接照抄。** `src/casmi/metric.py:40–56` 会跳过无效和重复 identity 且不占 rank；`key14` 不先移除立体化学，tautomer 规范化失败时还退回原结构。`requirements.txt` 仅要求 `rdkit>=2025.3`。我们应继续使用精确官方 2026.03.3 规范化与排名定义；先用边界用例核对，避免在不等价指标上选模型。
2. **排除身份要升级。** `fork/harness.py:176–177, 193–194` 的 mask 与 `run_fork_val.py` 主要按原始 inchikey14 比较，不能保证官方 tautomer identity 的所有等价结构都排除。预处理同样按 raw key 分组；所有谱库、analog representative、候选、模型训练 split 和缓存键须统一身份。
3. **多个训练行文件的 group 要全局统一。** `scripts/train_ranker.py:27–33` 对每个文件的 group 加偏移；如果同一查询身份出现在多个文件中，它会被当成不同组，可能跨训练/验证。合并前必须按官方身份重建全局 group，而不是只偏移数值 ID。
4. **占位分布不是隐藏测试约束。** `validation.py` 默认 m/z 240–465，早期文档把占位测试质量范围当筛选依据，Class 1 还有自匹配 sanity。仅作为调试；正式验证要移除自身/重复采集，覆盖更多质量和加合物，不剪死隐藏测试输入。
5. **留库不等于全栈未见过。** 公共 FPNet/ranker 等模型训练身份不透明时，按 hide_key 删除参考谱仍不能证明干净泛化。np250 也已被公共作者多轮使用；保留开发集、最终留出集与跨库面板，污染风险单列。

## 推荐采用顺序

先完成现有三套 smoke → 引入它的 mask/特征缓存/失败分解思想建立我们的验证台 → 重新导出当前强基线的分子级 OOF 排序数据 → 定点比较现有模型与单个自训指纹 checkpoint。先不重跑其旧榜分 kernel、不下载其权重、不租新卡。第一轮候选固定的神经排序增量消融仍按 `reports/public_pipeline_components.md` 进行。

固定提交链接：

- [README](https://github.com/shiferaxa/casmi26/blob/41f0c5dde78e551fb5aedbb3421156a38b3f427d/README.md)
- [训练源码](https://github.com/shiferaxa/casmi26/blob/41f0c5dde78e551fb5aedbb3421156a38b3f427d/kaggle/train_fp_v2/notebook.py)
- [验证入口](https://github.com/shiferaxa/casmi26/blob/41f0c5dde78e551fb5aedbb3421156a38b3f427d/scripts/run_fork_val.py)
- [实验记录](https://github.com/shiferaxa/casmi26/blob/41f0c5dde78e551fb5aedbb3421156a38b3f427d/docs/plan.md)
- [评分实现](https://github.com/shiferaxa/casmi26/blob/41f0c5dde78e551fb5aedbb3421156a38b3f427d/src/casmi/metric.py)
