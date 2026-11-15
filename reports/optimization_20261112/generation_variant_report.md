# 11/12 生成预算变体：部署检查

父版本：正式58156482 / Public .488，冠军Notebook SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。

最终候选：`submission/optimization_20261112/generation_expand/revision2/`。Notebook SHA `7ed40ac01c64448490cf9cfd85ad21210e34163e81affdb2e1a1dcbac7514753`；runtime模块SHA `32145802187bda9fe178048df49ec9ecfce6a0c7bab46c15550b5a479774eef9`。

## 实际改动

配置为12谱母体、单母体最多60产物、总计最多300产物；保留原双步转换，关闭near-zero delta的额外同分异构化枚举。min_sim和质量容差不变。它是整组生产生成配方，不将各项效果分别归因。

只改原外层cell12：在原stage machinery之后追加专用runner路由，另增加最后审计cell。其余原32个cell对象完全保留；原FROZEN及原8个MODULES逐字节不变，原神经集成、physical/MASS、晚接入head与AB继续原序执行。

真实触点是新runner在frozen cell37执行完后，绑定实际E/V1FE实例，再修改E.cfg、包装hooks_v1.derive_rec/E.generate/V.run和原rank_score。不能只包装Engine.generate类方法，因为V1FE初始化会用hooks_v1覆盖它。

每个query记录实际母体调用、7–12母体参与、生成数/触顶、时间、候选、完整特征hash、实际RK_FEATS的160列名称和顺序/float32投影hash、finite分数。原始V1FE实际产出252列，ranker实际选160列，不混淆这两个维度。最终审计记录生成SMILES在完整最终25中的保守交集数量，不读truth、不宣称隐藏收益。

## 必要部署检查

- exact staged setup/新runner真实传入参数/原runner不改/源码pin/最后fast audit/坏source删除CSV：9/9通过，`runs/generation_prod_canary_20261112_route_revision2/verification.json`。
- 真实2查询：完整2,539,608谱库与710,701结构池，原生产FPNet全量权重、A/B/D特征模型和v4b ranker，CUDA推理。无truth读取、无身份排除、无MRR评价、未重做produre面板。
- 7/7实际检查通过，`runs/generation_prod_canary_20261112_actual_revision2/verification.json`；完整计数在同目录runtime和real_query_results。

| 查询 | 原生成数 | 新生成数 | 新增身份 | 移除身份 | 实际母体数 | 新V1FE秒 | Engine前25中的生成结构 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_VXVNYCRICCVPTD | 150 | 8 | 5 | 147 | 12 | 2.46 | 8 |
| np_DUXQKCCELUKXOE | 150 | 300 | 264 | 114 | 12 | 8.50 | 7 |

新增/移除为原生score-key候选集合差；这些数字不是正确结构召回或排名增益。两个查询按既有生成较多记录选择，仅测试接口和预算。真实两轮query阶段共65.1秒，不含库/模型初始化。此小试没有重跑完整GL/ICEBERG、晚接入head、AB或外部参考delta，只验证生成到实际ranker的通路；后续原序消费由未改的原cell与最终runtime审计约束。

## 保留失败与修复

draft1原stage保留，未提交。其观察器错误要求原始V1FE宽度等于160；实际应验证252列中按RK_FEATS选择的160列。revision2修正并重新执行两查询验证。另将hidden query范围改为set+count相同，避免错误要求test与sample行顺序一致；实际输出CSV仍要求sample顺序。

Windows直接模拟Linux runner时write_text换行造成SHA不同，故字节级路由检查在目标Linux执行并通过。上述失败记录保留在`generation_draft1_failure.json`和旧canary目录。

没有下载新模型、没有训练或Kaggle写入。本报告支持可部署性，不预报Public收益。
