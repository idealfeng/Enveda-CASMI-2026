# 11/14：实际GL/ICE证据早期排序探索

状态：两个新版本已冻结，真实追加cell组件与源码绑定核验通过；本代理未进行云端写入，正式状态由主控回执决定。无收益声明。

共同父版本为精确冠军58156482、Public MRR@25 .488，Notebook SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。原33个cell全部逐对象保持，包括双神经、MASS、原晚接入head和AB；仅在完整最终输出后追加一个排序cell。公共模型、数据来源与版本不变，没有新增训练、谱库或候选。

两版都读取实际生产的 `gl_work/gl_out.json`、`ice_work/ice_out.json`，使用aggregate前向谱预测分数。这不是逐CE共识，不能用旧逐谱研究的收益作本版证据。保持raw字符串/官方score-key优先；只有无歧义的同官方身份别名才允许回退匹配，缺失、NaN、冲突保持缺失，有限零分仍是有效观测。全程不读目标结构或真值标签。

| 版本 | 固定机制 | 控制与目的 |
| --- | --- | --- |
| gl_evidence_early | 在同式原槽中用z(-log当前rank)+1×z(GL)重排原ranks2–25；至少2个观测且组内GL覆盖≥80%，未观测槽位不动 | 保留原top1；检验既有GL信号在最终早名次中的额外影响。不是新模型或新信息源 |
| dual_evidence_agreement revision2 | 原rank2–10的同式候选，GL和ICE的组内标准化分数都比当前leader高至少.1且为正分，组内共同覆盖≥80%，选择两者平均优势最大的候选与leader对换 | 允许改变top1，但需两模型同时支持；其他顺序不动。与纯GL尾序机制不同 |

共同保护：原library_max≥.9的查询和有效AB升首命中的查询整行保持。候选集合、官方身份合法性、同式槽位与ID顺序均核查；运行审计重算实际score消费、绑定控制CSV、GL/ICE文件、原library证据和AB runtime，模型输出篡改会被拒绝。

## 实际检查

- 使用已经成功完整生产运行的两题/20谱最终CSV和真实GL/ICE分数，执行新Notebook实际最后一个cell。fast_static与hidden组件路径都通过，原全部33cell未再次运行。这两题均被强library保护，因此实际最终排序均不变；观察器仍真的消费分数并记录保护。原两题生产输入含未用于预测的标签元数据，本次组件不读取任何test/标签文件，也不作准确率评价。
- 另仅用已保存的旧48条stage预测和真实GL/ICE分数，直接运行固定排序函数，不重构验证面板、不启动模型、无AB集成、不读标签、不算MRR。纯GL臂44行顺序变化、top1固定；双模型成对优势臂12行top1变化。这里只证明机制能扰动已有预测，不能称收益、精确冠军输出差异或隐藏测试覆盖率。
- 原始双模型“共同唯一全局赢家”臂在同一无标签组件缓存中0次升首，决定不提交；原目录及零变化证据保留。经主控同意改用明确的成对优势机制，另冻revision2，并保持.1优势、80%共同覆盖、rank≤10等固定条件，没有读取标签后扫阈值。两次机制不同，不将revision2冒充原臂通过。
- 实际调用 `kaggle_batch.load_manifest` 与 `local_preflight`，两版通过。源码、嵌入payload、recipe与私有离线GPU元数据指纹均绑定。

## 可提交入口与指纹

| 分支 | 取用的branch_spec | Notebook SHA256 | recipe SHA256 |
| --- | --- | --- | --- |
| gl_evidence_early | submission/optimization_20261114/gl_evidence_early/branch_spec.json | `de6b09110573232fcb33e3ff40b4a01428ec1a376edc2a839131bcea3726cc8d` | `ddcae1e322d8a0a6f1ebf416477b32aa98a3dd6a477ad3de9e53f65f63f01da9` |
| dual_evidence_agreement | submission/optimization_20261114/dual_evidence_agreement/revision2/branch_spec.json | `928da39f189adba270f21ec9c75c1260e4820aa46596c8b56cbbf372eb789d4f` | `e523db977cfe19c487a55c0b1faf414f54f234ed97e4b5fec29f46a4d50adb92` |

GL版本模块SHA `d33969d77fae5dab20bc3322f76ce76e4b346f82961098a0506389419e99259d`，路径`scripts/evidence_early_overlay_20261114.py`；dual revision2模块SHA `ef89002272e3264857de05e91668b89ce9d60eeb36c530a575670c5081a180ea`，路径`scripts/evidence_pairwise_overlay_20261114.py`。旧模块及首次冻结文件未覆盖。

证据：`evidence_early_preflight.json`、`evidence_early_components/verification.json`、`evidence_pairwise_components/verification.json`。构建入口：`scripts/build_evidence_early_20261114.py`与`scripts/build_evidence_pairwise_revision2_20261114.py`；组件入口：`scripts/check_evidence_early_20261114.py`与`scripts/check_evidence_pairwise_revision2_20261114.py`。重复构建拒绝覆盖，所有缓存/产物位于D。

决策：可按用户要求探索正式提交两版。新版本未执行全模型初始化到CSV的完整本地生产路径，未证明隐藏全集预算或收益；上云可见fast_static也不代表模型完整推理。若真实榜分提升，分别按最终GL重排或双模型成对优势升首记录整体来源，不能归因新增训练/新库/逐CE信息。失败、同分与降分也保留。
