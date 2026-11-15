# head_mean_ab：原mean尾排序与AB组合探索

- 用户明确要求使用剩余四次探索名额，本版无本地正向指标背书。
- 父版本：正式冠军58156482，Public .488；Notebook SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。
- 唯一概念变化：晚接入尾部排序使用原冻结v2 mean，去掉该位置的trained两head；仍保护前7、只换同式原槽位，随后保持AB原样。原生成、原双神经、MASS和AB不改。
- 历史58155938的v2mean-p7仅为不带AB的.482；历史没有提交本版精确组合，不把.482当新组合已知分数。
- 冻结文件：[branch_spec](../../submission/optimization_20261113/head_mean_ab/branch_spec.json)、[recipe](../../submission/optimization_20261113/head_mean_ab/recipe.json)。Notebook SHA `d61a87c4edc67ddd078845e6aeff2d09209e2ab6c75192d20cb3cdcd1318d270`，recipe SHA `cbb3916beddd216750f9b05384180f35700c8a98c6feb330a8c77ff9f79919a2`。
- 精确来源：冠军cell30/31替换为已正式跑通过的旧mean版本两个完整cell，其余31个原cell逐字节相同；新增最终observer核对mean→AB→最终CSV链和新recipe，不伪称原trainedhead执行。
- 模型：原v2 SHA `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`；mean scorer SHA `aac7fab01dbac124ff7debde08ed370fcf9cecc158064ffe83a575ee4f466fab`；无训练、无新下载、无新谱库。
- 实际组件核验：读取已完成生产r2的两个query/50候选中间产物，执行本版精确mean cells30/31（50.1秒）及AB/新audit cells32/33。mean实推理、score errors空、两行尾序均变化；AB确实加载A200724+B124160参考，最终observer通过。不是从生产初始化重跑，不是精确冠军候选集，不计算MRR/召回。[最终证据](../../runs/head_mean_ab_20261113_r3/verification.json)。
- 环境失误保留：首跑误将ICE自带RDKit目录放前面，版本断言即失败。后续从D盘既有官方wheel核SHA解压专用缓存，固定2026.03.3再运行，没有放宽断言。原失败目录和日志保留。
- 上下文更正保留：首次成功组件目录漏复制frozen_candidate_evidence，AB未使用原library_max保护。未据此宣称收益；补齐原生产文件（SHA `11345b56530731c3c7005ed594eb0a84edc4a276d97710e75e6d76dd3849c59a`）后，仅重放AB+最终audit35.5秒：原强匹配保护生效，0外库命中，与真实生产上下文一致。冻结部署始终保留生产文件，不存在此测试目录遗漏。
- 放行：[源和组件绑定](head_mean_ab_release.json)。云端可见fast_static仍为静态路径；正式隐藏全集、耗时和榜分均待Kaggle结果。本代理未执行上云或正式提交。
