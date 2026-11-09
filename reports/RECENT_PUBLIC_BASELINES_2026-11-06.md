# 近期公开基线复查与数据需求

核查日期：2026-11-06（北京时间）。主线基线已由官方API确认为提交58021256、Notebook V2、COMPLETE、Public 0.479，原始上游配方为Flex V56。

## 搜索范围与证据等级

先检索近7–14天公开页面，再查询官方比赛Notebook列表的scoreDescending及dateRun各100条，并拉取候选实际源码。搜索索引遗漏了改名后的Roman新地址与部分新分支；不能仅凭搜索没命中就宣称没有更强基线。

列表元数据未提供具体Public/Best Score，部分版本字段是缺省0。实际源码版本以独立pull为准。列表last_run_time与pull的lastRunTime字段有差异，本报告不将它们当作确切发布日期。标题、作者个人best、当前版本得分与我们的复现得分分开记。

## 实际找到的分支

| 来源 | 已固定源码 | 得分证据 | 新增内容与可复现边界 |
| --- | --- | --- | --- |
| [d1m4 hardened](https://www.kaggle.com/code/d1m4official/enveda-0480-ensemble-hardened) | V1，SHA `7780631f63b07663792b7e47c06585c7d3799e1e2ad9755698657aa4b2959d7f` | 官方页面索引Public/Best均0.480 V1；作者称11月1日复现0.480 | 双神经评分与回退修复；元数据仍指向deleted/142141665，缺模型会复用public bundle。新的公开v2数据集提供了补齐旧依赖的路径，尚未在我们账号复现0.480 |
| [Gold Apex peaks v2](https://www.kaggle.com/code/zz3t3rn41/casmi26-peaks-to-structures-v2) | 当前V30，SHA `73c8bdc7799ffdad7ef756015c74c90365ee060122f2567f8a3c061ff42cc0df` | 作者文档写个人best0.4810；不能把该best直接归给当前V30 | 当前三路0.5public+0.25v2+0.25v4，另有NP先验、leader规则、LOTUS补位。两新模型现已公开，无kernelDataSources。优先作为新公开路线候选；原代码仍有模型缺失回退，必须以实际hash/覆盖证明三模型均运行 |
| [Roman新地址](https://www.kaggle.com/code/romanrozen/0-482-casmi-from-peaks-to-structures) | 当前V17，SHA `5bdea66bc23d299d9349122c9403a238e952bc91d356dffbe95d562e00553726` | 标题0.482，未取得当前版本具体官方分数 | 比旧V8有重大更新：Gold Apex基底、质量先验、嵌入式102特征LightGBM异构体模型。旧kernel依赖仍deleted；公开v2可尝试补齐。嵌入式reranker可独立研究；不能把整个多因素配方的标题分归因给某一步 |
| [Helios](https://www.kaggle.com/code/heliosli/casmi26-0-482) | 主V2，另Happy分支V5 | 标题0.482，未取得具体官方Public/Best数值 | rr3 GNN/transformer加训练集外新版参考谱。必要数据引用为空，extlib数据卡当前403，公开作者数据列表未发现相应CASMI资源。缺cfg会跳过，不能将成功写CSV当完整复现 |
| [Pablo Starter](https://www.kaggle.com/code/pablodiegoo/enveda-casmi26-starter-notebook) | 当前V4，SHA `6b034783fe062131dd219797b4b15231cab7a4c8f9c59d916f8fffd17e65b7a7` | 出现在官方高分排序前列，本次未独立读取具体分数 | 四神经模型、公开seed包与训练Notebook输入；未先下载全部权重，避免同时引入多条来源。seed包作者自己的plain测量为0.479，不能把增加seed视为必涨 |

Flex主仍V61，已知Best为V56的0.479；Evgen仍V27，没有取得新更高版本证据。

## 已取得并验证的新增资产

两份[bgunshui v2](https://www.kaggle.com/datasets/bgunshui/casmi26-scorer-v2-model)、[v4](https://www.kaggle.com/datasets/bgunshui/casmi26-scorer-v4-model)均匿名API200且isPrivate=false，固定V1。checkpoint合计28,786,404字节，含必要代码/配置的本地payload为28,806,023字节，均位于D盘。

- v2：width192/heads6/layers3/embedding192，checkpoint SHA `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`。
- v4：width256/heads8/layers3/embedding256，checkpoint SHA `10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51`。必须使用实际256配置，不能套原192默认。
- 两数据集原生只有README/config_used/checkpoint/training_result；model/features/inference来自已有Saner V1代码，来源在receipt独立标记。16/16文件fresh SHA复核通过。
- 两模型均已weights_only、strict state_dict加载，并用两条按原min_peaks规则筛选的现有真实谱及两个候选完成CPU前向，形状和数值有限性通过，两个权重不同。这是兼容性检查，不是完整基线或得分复现。
- 训练配置为官方train、external_paths=[]、full refit，明确含原validation身份；不能在这些身份上称干净CV。数据卡license仍Unknown，公开可下载不等于已证明获奖方案的再分发许可。

原始源码在`third_party/*_20261106`；公开列表在`reports/public_baseline_scan_20261106`；新模型完整性、训练及许可审查见`reports/new_scorer_assets_20261106/REVIEW.md`，加载检查见`reports/public_scorer_compatibility_20261106.json`。

## 下一步顺序

1. 保留0.479锚点。先以现有固定候选/查询比较public、public+v2、public+v2+v4三个预登记神经组件，不混改NP先验、结构池或其他后处理；明确旧面板曝光边界。确认所有新模型实际覆盖且无重复权重回退，再准备完整公开基线复现。
2. 完整新基线确认后，做EXP003逐谱支持一致性。新增工具`scripts/forward_trace_runner.py`已完成静态/合成观测不改均值检查，尚未运行真实模型trace；不把工具就绪写成算法增益。
3. Roman嵌入式异构体模型可列为独立候选组件；质量偏移、新先验与LOTUS回填分开评估，不一次并入后归因。

## 是否需要更多数据或谱库

当前不先批量扩库。官方已有2,539,608谱，内含GNPS/MassBank/MoNA来源；再整库拉取易增加重复和匹配成本。现有48分子开发诊断46/48有真结构在final25，9个召回后首选错的案例均同式，优先排序新证据；这些曝光诊断不能用作隐藏集召回率。

需要补的是验证独立性、困难同式候选与逐谱证据。先从已有开发数据和外部记录做身份/来源审计；未查看身份本身不能消除预训练接触。扩结构库须先证明缺失源身份，排除adduct、质量窗、剪枝/topK原因；扩参考谱则先取元数据增量、去重并选择仪器/能量/加合物匹配的几百至几千条小试。

新的训练集外参考谱可能有价值，Helios路线提供了这种线索，但其当前不可得资源不能直接采用，也不能推断海量扩库必涨。[主办讨论744470](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/744470)明确排除NIST及其训练方案；新增参考谱保留逐记录来源/许可，并全局屏蔽开发验证目标身份的所有来源与近重复。
