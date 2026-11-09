# Engine2 初始化成本与三方案缓存边界

检查日期：2026-11-04。只读分析已下载源码和本次运行日志；没有修改活动进程、原始 Notebook 或当前生成的 Engine2 源码，没有启动额外模型、下载或缓存构建。

## 本次实际耗时

`runs/prvsiyan_smoke_20261104a/console.log` 中 Engine2 子进程打印的相对时间：

| 时间点 | 已完成工作 | 相邻阶段约耗时 |
| --- | --- | ---: |
| 104 秒 | 加载 2,539,608 张原始谱及质量索引 | 104 秒 |
| 122 秒 | 合并外部库，准备给 245,591 个训练结构算指纹 | 18 秒 |
| 167 秒 | 形成 1,137,233 结构候选池 | 45 秒 |
| 297 秒 | 完成谱库索引及 275,810 个 representative | 130 秒 |
| 302 秒 | 两个指纹神经网络加载到 CUDA | 5 秒 |
| 324 秒 | 12 分子的 channels 完成，进入 2109 候选的 MetFrag-lite | 约 21 秒，自 303 秒测试输入日志算起 |
| 437 秒 | 碎片步骤和 4 个 our-ranker GBM 的训练阶段完成 | 自 324 秒约 113 秒，日志未进一步分开计时 |
| 488 秒 | 8 个 prvsiyan-ranker GBM 完成 | 自 437 秒约 51 秒，含前组模型打分和释放 |
| 497 秒 | 子进程提交列表准备完成 | 9 秒 |

父进程记录 **cell12 总耗时 525.789 秒**，约 8 分 46 秒，包含子进程、输入/输出与日志处理。这个数字属于本地 12 分子 smoke 的完整 Engine2 阶段，不能称作纯模型训练时间或完整隐藏测试推断时间。

原始谱库加载和索引合计约 234 秒，比本次训练结构指纹的约 45 秒更耗时。神经网络模型加载及查询推断只占该阶段的一部分。父进程使用 `capture_output=True`，子进程结束后才把中间日志写入控制台，因此等待时看不到这些阶段进度。

一次 `/proc` 快照显示过 D 状态及 `p9_client_rpc`，可支持当时存在 WSL `/mnt/d` 文件 I/O 等待；单个快照不能判断该进程此前是否已经完成某一阶段，不能用它分解总耗时。

## 当前候选数没有显示源码/输入冲突

本次日志为：COCONUT 原始池加 ChEBI/LIPID MAPS **98,433** 条，再加 PubChemLite **356,820** 条；源码沿用 `COCONUT` 标签打印合并后的 **891,642** 条，随后加入有效训练结构 **245,591** 条，得到 **1,137,233** 条。

这与当前 V43 `build_pool` 的扩展逻辑一致。早期约 712k 是另一阶段的基线规模；Engine1 的预构建 V2 pool 和 Engine2 的动态扩展 pool 也属于不同对象，不能按一个固定数字理解。

## 静态一致性证据

检查对象为下载的 prvsiyan V43、Flexonafft V56 和 Canqiang E006 V1。以 AST 内容（忽略行号）比较：

- 三者 `formula_mass`、`load_library`、`_fp_init`、`fp_and_mass`、`_reps`、`build_index`、`fit_rankers`、`fit_pv_rankers` 的函数体相同。
- 三者 `pv.neutral_mass`、`pv.clean_store`、`pv_fp.load_fp_models` 的函数体相同，峰清洗/相似度参数相同。
- V43 与 Flex V56 的 `build_pool` 只在资源定位路径和注释上不同，均添加 PubChemLite。两方 COCONUT/Bio/PubChemLite 共 14 个对应文件的下载收据 SHA-256 全部相同；64KB 指纹坐标文件还重新读取确认了同一 SHA-256：`a61e372fc41091bf5c7467e08134081266262665077cb9e2c56d73e4887f3013`。
- E006 的 `build_pool` **没有 PubChemLite 扩展块**，因此其完整候选池和 pool ID 分配不能直接当作 V43/Flex 的池。
- 训练函数相同，但种子配置不同：V43/E006 的 `RANK.SEEDS=(0,1)`，Flex 是 `(0,1,2,3,4,5)`；V43/E006 的 `pv.CFG.SEEDS=(0,1,2,3)`，Flex 是 `(0,1,2,3,4,5,6,7)`。

## 能缓存什么

| 对象 | 跨方案共享条件 | 建议缓存键和内容 |
| --- | --- | --- |
| 原始谱库 `L` | 三者加载逻辑相同；训练文件、质量公式/加合物函数必须一致 | train 文件身份、`load_library`/`formula_mass`/`neutral_mass` 及质量常量版本。保留 `off,mz,it,prec,nm,pol,tims,ik,smi` 的原值、dtype 和行序。原始两峰数组约 3.21GB，可用 copy-on-write mmap |
| 单结构 `fp_and_mass(smi)` | 三者函数相同；需要相同 RDKit、指纹 bit 坐标、原始 SMILES | 精确 SMILES + RDKit 版本 + `fp_bits.npy` hash + 生成参数/函数 hash；保存 packed fingerprint、精确质量、失败标记。275,810 条 6930-bit packed FP 上界约 239MB，质量约 2.2MB |
| 完整候选池 `P` | V43/Flex 的对应候选输入 hash、训练标签顺序和 RDKit 一致后可共用；E006 单独建一个视图 | 所有外部 pool/meta/fingerprint 及训练标签 hash、`build_pool` 的语义版本。保存 `fp,mass,keys,smiles,k2i`，保留 stable mass sort 和重复 key 的第一次出现规则 |
| `L['row_p']` 与 `I` | 必须绑定完整候选 key **及其顺序**，不能仅看索引函数相同 | `L` 身份 + 有序 P.keys hash + representative 参数。保存 `lib_rows/lib_nm` 和 all/pos/neg 的 rep 索引、pool ID、质量、清洗 CSR |
| CPU ranker | 按每个种子/类别权重分别缓存，再依原列表顺序组装 | ranker 数据 hash、特征顺序、sklearn 版本、函数/超参数、类别权重、seed。V43/E006 与 Flex 的完整模型组不同；可在输入确证后复用共同种子，补训练额外种子 |
| 查询 channels | 需要相同查询谱、候选池、参考库、模型权重和全部查询参数 | 查询内容 hash + L/P/I + FP 权重 hash + channel 配置；这是之后的优化，不能仅按可见 `molecule_id` 缓存 |

原始 `L` 与当前已经构建的 Engine1 clean CSR 不是同一种缓存。Engine2 加载原始 float32 峰，并优先按分子式得到中性质量；其代表谱另用 0.2%/256 峰等规则处理。把 Engine1 清洗 CSR 直接替换进去会改变预测行为。

现有 `train_fp_sel.npy` 属于更大的指纹块布局；不能因为它已经存在就直接替换 Engine2 的 6930-bit packed FP。该布局增加了其他指纹块，需先证明按块映射、结构行身份和 bit 数值一致，当前没有这项等价证明。

## 原代码是否已经自动缓存

Engine2 没有持久化的 `np.save`、`pickle.dump` 或命中检查来保存这些 `L/P/I` 对象；每次进程启动都会重新建立。`POOL`、`_g` 是进程内状态，子进程退出后释放。Numba 的 `cache=True` 和 D 盘 `NUMBA_CACHE_DIR` 主要缓存编译结果，不会代替谱库、候选池、指纹或排序器的数据缓存。

当前运行不会自动导出这些中间对象。后续若加缓存，应在下一次启动前设置透明缓存适配，先用小样本逐值比对，再比较完整候选顺序/特征/输出。优先考虑 **原始 L + representative index**，其次是训练结构指纹和分种子的 CPU ranker；不要修改正在运行的源码或把缓存优化结果冒充未适配的原环境复现。
