# 11/14：把晚接入排序从8–25名提前至2–25名

这两版是用户指定今日五次探索中的两条。假设是：此前保护前7使局部模型只改尾部，对MRR可动空间有限。本轮仍保留rank1，允许原同分子式槽位中rank2–25参与排序。它们不引入新训练、新谱库或新候选，不保证收益。

共同父版本为正式58156482、Public .488，SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`。主生成、MASS、双神经及外库版本保持原样；原33个cell仅30/31（晚接入执行/观察器）替换，AB cell32逐对象完全相同，另加最终分支audit。首选rank1在晚接入排序阶段固定，原AB随后仍可依据其原规则升首。

| branch | 晚接入评分 | 固定规则 | 唯一/组合变化范围 |
| --- | --- | --- | --- |
| head_prefix1_ab | 冠军原two-head模型与原权重 | prefix1、rank2–25同式原槽位、随后原AB | 相对冠军只改变前缀保护范围；实现使用已有可配置tail模块并重建精确审计 |
| mean_prefix1_ab | 原v2 mean，没有learned heads | prefix1、rank2–25同式原槽位、随后原AB | 相对11/13已提交mean＋AB版只改prefix7→1；相对冠军则同时更换晚接入评分及保护范围，不能把冠军比较净差单独算prefix贡献 |

两版部署使用既有可配置tail `scripts/guarded_head_tail_20261109.py`，SHA `783b767e6b5425879ea3bcc8dadbedc40ea349def0e943c65dbf9c5052af3a64`。评分payload和encoder固定原SHA；真实模型推理回执绑定有效query、候选和输出评分，并实际重构排序验证。公式槽位、候选multiset、官方身份、分子顺序均保留。无有效谱或身份异常时原行保留，异常全局fail closed。

构建入口：`scripts/build_prefix1_ab_20261114.py`，拒绝覆盖既有目录。组件入口：`scripts/check_prefix1_ab_20261114.py`，使用D盘现有官方RDKit2026.03.3和两个真实生成生产小样本的50候选中间件，依次执行actual cells30–33，复制frozen_candidate_evidence以保留原AB保护上下文。它只测试改动组件，不重跑完整生产初始化；候选来自12/300/noiso那次小样本，非精确冠军候选集合，不做准确率/召回率评估，也不重做produre1/2。

组件同时用本次真实评分重构prefix7结果，与历史同两题的实际trained/mean prefix7尾排序逐行比较。这样可以确认改变来自排序范围，而非悄悄换了评分或缺失AB上下文。组件日志、模型调用回执、输出、失败证据留在`runs/prefix1_ab_20261114/`；检查结果看`prefix1_ab_components.json`。源码/正式工具preflight结果看`prefix1_ab_preflight.json`。

| branch | Notebook SHA | recipe SHA |
| --- | --- | --- |
| head_prefix1_ab | `6c08b5287e42969ab0e67b50975ac46bae2c35f6dad76f8a32b94bc4ae022670` | `a6e2710a099fd00e9972e18126202dd70ebcdf6b43081d4a3a860f24b98bab64` |
| mean_prefix1_ab | `909972b476b706624d66cfa11f2bf1f32a45967d1f44fdd2231a136232d7fd5f` | `a0623e5314185582e93ce5c832e474ba9c938d262487ae347046f44cc207eaf1` |

正式提交由主控统一执行。可见Save&Run使用fast_static，不能称真实模型完整运行；新分支目前只有局部真实组件核验。只有官方隐藏评测完成且返回有效分才能讨论升降；如创新高按上述对照与改动范围记录来源，不把PENDING或候选变化记收益。

## 实际组件结果

两版均已通过实际cells30–33组件执行：trained head版98.1秒，mean版98.5秒，均实际评分50候选、两题全部改动rank2–7、首选保留，原AB零命中。每版tail/AB/final audit全部为hidden_full/passed，模型评分errors为空。用本次真实评分重构的prefix7结果逐行精确匹配历史相同两题的实际trained/mean中间输出。没有计算准确率或召回率，不据此宣称涨分。

运行进程exit0，GPU与大库已释放。分支stage及上述SHA保持不变；主控可按固定spec进行一次正式探索提交。机器可读汇总为`prefix1_ab_components.json`，源码和完整回执指纹见`prefix1_ab_release.json`。
