# 独立只读审查：两版best-validation集成

结果：60/60通过，可进入云端运行与输出核验；不构成榜分提升证据。

核对了固定checkpoint独立性、原scorer真实兼容小试、源码/payload/metadata/recipe指纹、精确混合配置、完整候选键与分数观察器、原outsider仍v2、latehead与AB不变。两个stage原33cell中只有14/29改动，追加末cell33绑定新配方及最终AB输出。

原V80 final与现有v2完全同SHA，不把重挂相同权重当新模型；本次使用实际独立best-validation checkpoint。

| 分支 | 权重(public/v2/extra) | Notebook SHA |
| --- | --- | --- |
| bestval_v80_tri | [0.5, 0.25, 0.25] | e1d732f2a4e1aab9a5ecda2d849176039636f4fb58c743f2eeee7e1a5e224681 |
| bestval_saner_tri | [0.375, 0.375, 0.25] | 363bcfcf402d58d4bac16375323b97924abd40125d8f1adcb54806935eb740af |

先前建议的配置审计缺口已在冻结前补齐：runtime配置必须等于固定kind配置；before-consensus、cell29和末audit均绑定固定kind，权重或分数篡改会拒绝。

审查未执行模型加载、GPU、谱库扫描、Kaggle读写；只读冻结文件和已完成的小试证据。完整检查见bestval_independent_review.json。
