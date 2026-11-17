# Rogers .492 原版臂：本地冻结准备

2026-11-17。仅准备文件和静态检查；本报告未启动Kaggle、未正式提交、未取得我们自己的.492。

公开锚为 [Rogers V1](https://www.kaggle.com/code/rogersjohnson/casmi26-l4-lam035)，本地原始源码SHA `51c32f200c265fff08bfa4a9841cb6345d1f56515dcd72e254df8da53e07ae99`。Alex公开说明引用其账户正式ref58380172得到.492，属于作者的复现证据，不是本账户成绩。

本地冻结入口：[Notebook](../../submission/public_network_20261117/rogers_repro/notebook.ipynb)、[recipe](../../submission/public_network_20261117/rogers_repro/recipe.json)、[branch_spec](../../submission/public_network_20261117/rogers_repro/branch_spec.json)。Notebook SHA `5921fe5b86cc995e779df4eac49ea0a84942bedc8e8bcaf15c6b1b6e99aca135`；recipe SHA `b8c7b3394eaebf074cf39566f53703bd2eccfe6283bf89aa751f5d98b6246634`。目标新私有版本为 `stormseye/casmi26-rogers0492-repro-1117` V1。

原配置保留POP/SPEC/NP=.12/.12/.12、双模型均分z、MASS、LAM=.35/TAU=.6的原N1c及后接原raw AB。未插入我们的late learned head，未添官方身份guard，未改原merge对物理文件SHA不一致时warning继续的策略。此前继承文字把Rogers/冠军的warning与strict assert方向写反，已按原始source纠正：Rogers是warning，冠军是assert。

为避免任意递归首个模型命中，固定只选V80输出 `casmi_spectrum_model_ours_v80/final_model.pt` 且SHA必须为现用v2 `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`。它不是独立新权重。其余模型/特征/配置与5个AB资产均检查现有SHA；10个dataset及V80 kernel固定数字版本，保留上游docker/T4/offline。

原网络函数与raw AB函数分别保持逐字节SHA `33153de76fccebe4ed2325bea7649573219e4cfb964483cd5c335ac7dc7e93b8` 和 `9ceaa95ddda0fb304758c9acd7dd1f256c528fcb4a8304c0152f8b6d8e3e3e76`。只包裹两次调用记录完成标志、stdout、实际两库加载计数以及CSV前后SHA。上游catch继续不能绕过最终观察器；网络只允许同候选重排，AB原逻辑允许新候选插入。最终重复官方身份仅记录，保留原版行为。

静态cells编译、原函数字节、未改cell对齐和 `kaggle_batch.local_preflight` 均通过。观察器正常完成/原函数异常/未到完成标志/读错control夹具通过，见[回执](rogers_repro_builder_checks/verification.json)。这些是审计夹具，不是原生产完整初始化或网络效益验证。

可见运行仍为原父版fast，但原网络与AB会真实读取可见谱并执行；新增最终审计明确区分该组件与完整生产。正式隐藏重跑才要求完整pipeline执行回执、双神经实际分数、MASS执行及网络→AB→最终CSV消费链。当前尚待真实云端运行审计；失败或正式接受必须继续保留并记账。
