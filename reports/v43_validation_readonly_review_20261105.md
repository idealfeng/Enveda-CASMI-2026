# V43 验证适配：只读检查

没有改动共享 `validation/pipeline_adapter.py`、原始Notebook或资产；没有启动模型/GPU。

## 时间预算

`make_configuration()` 对48身份默认 ICE 和 N1 都为636秒。这个公式只使用分子数，没有计候选结构、加合物、谱数、CE桶、图碎裂复杂度或模型加载。

Flex失败证据：`runs/validation_flex_c2_20261105b/ice_work/ice_out.json.meta.json` 记录 load59.57秒、11939次预测耗564.91秒、总636.12秒，46个覆盖分子只完成32个，status=budget，预测失败为0。也就是说失败来自未完成工作，而不是模型崩溃。

V43用同一ICE模型/候选扩展路径，查询也是48身份；虽然最终候选与Flex不完全相同，636秒依然不能假定足够。V43严格commit模式还会强制执行N1合成代理测试，其负载不只是真实盲区分子数。建议本机48身份显式 `--ice-budget 2400 --n1-budget 2400`，GL4000可保留。它们只是工作预算，不是保证耗时；只有status=ok且covered全部完成才接受完整结果。

## 排序、身份、健康断言

- `prepare_v43()` 先断言原V43 SHA，再调用本地路径适配；validation hook没有修改ranker数据、权重、融合常数、官方identity、候选规则或模拟器公式。
- `install_e2()` 在完整候选池建立以后，把屏蔽谱的row_p置-1，再构建direct/all/pos/neg索引；不删除候选结构。运行断言逐索引确认没有屏蔽谱。Flex的真实E2审核还验证51个blocked raw key仍在候选池。
- `install_e1()` 保持CSR行号/offset和候选池，只屏蔽谱索引与representative；扩展库也沿用mask。
- 适配允许“处理过但检索为空”的诊断查询，替换了只为12占位例子写的非空断言；但保留全部active ID、`n_err==0`、官方identity唯一性、E006 control重建、rank2保持leader等排序检查。空检索通过sidecar独立记录，不等于模型失败可静默忽略。
- 强制 `IS_RERUN=False` 保留原commit健康检查；最终额外审核要求ICE/GL/N1 `status=ok`、无错误/预测或特征失败，ICE/GL `n_mols_scored==n_mols_covered`，N1 `n_mols_done==n_mols`，完整query IDs和参考隔离审核。ICE runner进程退出0本身不代表完成。

## 评估器对 V43 的适用性

`scripts/evaluate_validation_run.py` 依据config.pipeline分支。V43只要求完整final输出及真实runtime审核，不要求Saner variants。官方分子指标和np/cross分层可共用；E1/E2 JSONL、namespace stageparquet和empty sidecar字段与V43 export一致。

V43的`frozen_final25`是其source final，而Flex同名stage是外层Saner之前的冻结source final；标签scope已明确为“namespace export时的source final”。Saner/fold0在V43报告中标为不适用；共享manifest列出的它们的训练声明不代表V43加载过它们。

固定候选消融仅在Flex执行，control严格为variants/V0，并断言V0官方identity顺序与baseline0465相同，V1/CUSTOM候选identity集合精确相等。physical、文档先验、outsider/final只单独报告，不能混入Saner增量。

阶段召回边界不变：E2 mass window是E2本地结构池，不是104M PubChem；E1 ranked_all已经过自身物化/过滤；PubChem仅top列表。empty sidecar只证明E1top/E2top40/PCtop的空状态，不能反推未记录的质量窗空。缺失阶段继续unknown。

本轮依旧是存在FPNet full1明确训练曝光的参考库隔离诊断。没有提前运行actual评估，也没有读取/评分最终250留出。
