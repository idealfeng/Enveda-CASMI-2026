# 2026-11-07 公开高分方案复查

检索与官方API读取时点：北京时间2026-11-07凌晨。只读取公开源码、元数据及所需模型资产，没有运行模型、创建云任务或提交比赛。所有新文件均在D盘。

## 结论与今天的额度选择

确有新的高分列表条目和上游版本更新，但不能按标题数量安排重复提交。当前最值得独立复现的是 **popwenman 的公开 V2、`V8='MASS'` 配方**。Gold Apex V32与Roman V17的所有代码cell文本及AST完全相同，仅开头宣传Markdown不同，应视为同一配方。pop V2则仅将配置由`BOTH`改为`MASS`，不执行RR异构体重排。

建议今日四条新提交：V56+双神经、V56+三神经、pop公开MASS配方，以及V56+更积极的RR异构体重排。前两条由主代理另行准备；本次检索没有再安排重复的Roman/V32克隆。

原V56的我们账号实分0.479仍是锚点；此前三模型完整V30在我们账号实分为0.475，不能把同配方的作者个人best直接搬到我们账号。

## 最新源码核验

| 方案 | 实际最新版本与代码证据 | 本次得分证据和判断 |
| --- | --- | --- |
| Flex `flexonafft/casmi26-closing-the-evidence-gap` | V61未更新，SHA `ae4e0b21909396444d271fd4f1ae8a92c2682e349529b28cb59f79b973d63cf7` | 官方可读页面仍为当前0.473、Best0.479 V56；没有找到高于旧V56的新版本 |
| Roman `romanrozen/0-482-casmi-from-peaks-to-structures` | V17未更新，SHA `5bdea66bc23d299d9349122c9403a238e952bc91d356dffbe95d562e00553726` | 标题0.482；本次未取得当前版本具体官方Score值 |
| Gold Apex `zz3t3rn41/casmi26-peaks-to-structures-v2` | V30→V32，SHA `e01bdf039dc1107bad032c8c0713e6b1803ac05c6d482f8aa1998d7d4e073f04` | V32全部代码逐字等于Roman V17；唯一源码cell变化是cell0 Markdown，不是新算法 |
| `popwenman/casmi26-v32-sovereign-gold-apex` | V1，SHA与Gold V32逐字节相同 | 不能作为另一独立方案占额度 |
| `popwenman/casmi26-0482-gold-apex-v22` | V2，SHA `351d0fadaffd5d9894d76f55b3fa30247b269255d6ca46fe1e93f3d31ef9d9d4` | 官方scoreDescending列表第4；标题0.482，数值仍未独立核出。与Roman仅cell4 `V8='BOTH'`→`'MASS'`；优先复现这一明确分支 |
| Helios `heliosli/casmi26-0-482` | V2未更新，SHA `1d51ef0cbcafc00893a4d7f51142c0e712f1c14a0113366626f96b87bd2a10c6` | 原资源缺口未有新的公开证据，不优先占今天额度 |
| d1m4 hardened | V1未更新，SHA `7780631f63b07663792b7e47c06585c7d3799e1e2ad9755698657aa4b2959d7f` | 已知页面0.480，但与今日双模型线高度重叠 |
| Pablo starter | V4→V5，SHA `3c2ac5a53dd3c1b9d27ee2a12c8d777ead328b0400264271f4378208d6872713` | 多seed scorer仍需新的训练kernel来源，未核出更高当前成绩，不优先于可忠实执行的MASS分支 |
| prvsiyan `the-company-a-molecule-keeps` | 新V1，SHA `7d2f1d347e15eb93fc8ccdee31e276542a422a9f357e95045752abe5e16702dd` | 是120身份的行切分/结构分组泄漏示例，不是新的竞赛高分推理方案 |

官方列表的scoreDescending/dateRun各读取100条；类型化API未暴露Public/Best数值，版本字段仍可能缺省0。上表实际版本来自独立get_kernel源码读取。列表last_run_time与pull metadata last_run_time仍存在差异，不将它们当确切发布日期。

## pop公开方案的原生权重已经找到

其metadata包含公开训练kernel **`popwenman/casmi26-scorer-train-v80` V1**（id142914344，is_private=false），不再有旧deleted kernel的不可复现问题。原生输出：

- `casmi_spectrum_model_ours_v80/final_model.pt`：11,872,818字节，完整SHA **`c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`**。
- `config_used.json`：796字节，SHA **`b7781dc1087d6ac441dfc6ee9f0f169a0b238e4776bef01bb581d3789941af2d`**。
- 这份checkpoint与已有bgunshui v2 **逐字节同权重**；两份配置差异仅`output`/`work`目录，所有推理和训练参数相同。原`_swap_to_ours`在运行时还会复制public的`config.json`，只将原生配置另存为`config_used.json`。
- 同训练输出中`kit_staged/final_model.pt`为public scorer，SHA `44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642`。原`_swap_to_ours`显式排除`kit_staged`，不可把这个public模型当OURS。

已下载原生文件及小配置至`assets/kaggle/popwenman/casmi26-scorer-train-v80/v1/`，回执记录完整SHA；没有反序列化checkpoint或调用模型。可以保留原公开kernel V1依赖忠实复现；若以bgun数据集替代，已有完整权重和推理配置等价证据，须在工程适配中记录。

## 依赖、cell位置及可复用的RR

pop V2有29个cell：配置4、session/hidden识别5、双神经主调度14、mass表19、最终merge20、mass leader/RR调度22。`COMMIT_MODE='fast'`仅跳过可见输入的实际推理；通过官方rerun环境标志或test谱ID签名改变自动进入隐藏全量。

原metadata数据源为旧六项公共资产、`sanpier/catalogue-experiment-saner`、LOTUS及`metric/rdkit-2026-3-3-wheel`，另挂上述pop训练kernel V1。Catalogue V1匿名API可读、isPrivate=false、约25.6MB，内容为验证replay/面板/combiner，**没有final_model.pt**；当前核心源码无直接引用。Metric wheel V1公开，共4个cp310/311/312/313官方RDKit2026.3.3 wheel，约148.9MB；可在Kaggle挂载离线安装，本地未重复下载。COMP路径显式限定官方competition目录，不会把附加catalogue里的test/sample文件当测试集。

pop原metadata镜像为`de153e...`，训练输出有cpython313缓存，但推理session注明expects3.12。实际部署应检查Python/torch/RDKit或复用我们已跑通的`9a6bc...`镜像，不能仅复制镜像而省掉兼容性检查。候选评分和排序代码不因镜像适配而改写。

RR特征、覆盖器及LightGBM模型均嵌入源码，提取于：

`third_party/public_scan_zz3t3rn41__casmi26-peaks-to-structures-v2_20261107/review_only/`

| 文件 | SHA256 |
| --- | --- |
| rr_features.py | `aec9012e72324095308af81c1408aa36f6a44cb00f6d4389e87529a68329d176` |
| rr_overlay.py | `e83b7986c46d0ef02bc6cfde17e891c9e7ee66a0eed8c716f5e3474e5663ccf7` |
| rr_model.txt（183,690字节） | `3b80e1c9adf90721c99bb4e817a05379dd8b26e0988a001bd112330a66d9122b` |

RR原参数alpha1.0/lib_tau0.9，只有同leader公式组可动，train rawIK14结构固定槽位，可移动rank1；pop V2的MASS预设不执行RR。因此V56+RR（alpha1.5/lib_tau0.95、不叠mass、新先验）确为不同冲分分支。RR原生train freeze使用rawIK14，不能称为官方tautomer身份上的干净验证；可见输入又来自训练，必须看隐藏重跑中实际触发数。

## 证据目录

- `reports/public_baseline_scan_20261107/scoreDescending.json` / `dateRun.json`：官方各100条列表。
- `reports/public_baseline_scan_20261107/source_snapshots.json`：15份小源码快照及SHA。
- `reports/public_baseline_scan_20261107/extra_dataset_cards.json` / `extra_dataset_files.json`：额外数据源公开状态和文件目录。
- `third_party/public_scan_*_20261107/metadata.json`：独立源码版本与依赖。
- `assets/kaggle/popwenman/casmi26-scorer-train-v80/v1/download_receipt.json`：原生权重完整SHA和下载回执。

Web索引检索与直接页面读取已执行；新pop/Roman/V32页面未返回可用具体分数，不编造已验证0.482。Flex的当前/最佳分数可由[官方页面](https://www.kaggle.com/code/flexonafft/casmi26-closing-the-evidence-gap)读回。新的三模型、MASS与RR收益必须以我们自己的正式提交为准。
