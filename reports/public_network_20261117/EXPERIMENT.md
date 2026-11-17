# 公开0.492复现与冠军网络移植：两版已正式接受

2026-11-17北京时间12:13，官方已接受两版，当前均 **PENDING、无分数、无报错**。当前确认最高仍58156482/.488，不把公开作者的.492写成我们已取得的成绩。

## 来源及取舍

用户授权：查当前更好的公开方案，取得源码后复现并优化提交；本轮后续明确要求继续。11/17重新取得官方scoreDescending/dateRun清单及额度：当天允许5次、已用0、历史42次。快照：[fresh_inventory_and_quota.json](../public_review_20261117/fresh_inventory_and_quota.json)。列表API的score字段为空，排序靠前本身不能证明分值。

- **采用Rogers/Mathlete公开网络路线**：Rogers V1源码SHA `51c32f200c265fff08bfa4a9841cb6345d1f56515dcd72e254df8da53e07ae99`，Mathlete明确自报.492，Alex列出另一次复现提交58380172=.492。三者当前核心算法相同；有可读取源码、公开依赖和模型指纹，可做我们自己的正式对照。[上游确认](../public_review_20261117/review/upstream_confirmation.json)、[原始来源](../public_review_20261116/notebooks/rogersjohnson__casmi26-l4-lam035/metadata.json)。
- **不下载Helios .494/.495演示大包**：公开包描述明确原competition-trained参数不包含，七个学习组件为initialized demo/部分synthetic fit，MEGx表为生成fixture，补挂新slug也不能变成真实.494/.495复现。[完整证据](../public_review_20261116/helios_audit/REPORT.md)。11/17新.495与h495源码逐字节相同，仍绑定这些演示包，不能据标题认为已取得可复现强版。
- **新增anchored network V2作为候补**：flexonafft当前V3是训练Notebook，显式V2才是推理；V2仅将高置信邻居用作更强锚、保护高置信查询首位，无额外权重。没有核得我们自己的榜分，本轮未部署/提交，不与当前两版混记。源码保存于 `reports/public_review_20261117/new_sources/flexonafft__casmi26-anchored-spectral-network/explicit_v2/`。

## 固定两版

| 分支 | 实际改动与对照 | 正式编号 | 最新状态 |
| --- | --- | ---: | --- |
| rogers_repro | 公开Rogers原版：priors .12/.12/.12、原双神经、网络.35/.6在原raw AB前；无我们晚接入head或AB身份guard | 58455482 | PENDING |
| champion_network | .488冠军保持原MASS、.10/.10/.12、双神经、晚接入head和AB身份guard；仅在head后/AB前加入同一.35/.6网络，无额外首位/库保护 | 58455510 | PENDING |

不是同一父版上的严格单因素成对比较：两版的priors、晚head、ABguard和merge警告政策不同。Rogers merge对特定物理控制SHA不一致是warning继续；冠军为严格assert。本轮分别回答「能否在我们账号复现公开整版」和「该机制能否迁移到冠军」，不能把两版分差只归于head或某单个常量。

原网络使用同离子模式观测谱构建modified-cosine≥.6、至少6匹配峰的查询间边；候选得邻居前5的Morgan相似度支持，边权四次方，按`z(-log rank)+.35*z(network)`稳定重排。候选多重集不变，无目标结构/标签注入。原函数UTF8按LF归一SHA `33153de76fccebe4ed2325bea7649573219e4cfb964483cd5c335ac7dc7e93b8`；跨Windows CRLF原文件字节SHA不同不代表算法变更，权重和冻结Notebook仍逐字节固定。

## 模型、源码和执行证据

两版没有新权重/训练，公开V80 final仍等于现用v2，SHA `c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46`；公共Saner SHA `44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642`。复现版固定V80 kernel V1（标题v80不是版本80），10个dataset数字版本；优化版保原冠军所有资产版本。可见观察器校验实际选到的模型及两库字节。

- 复现Notebook SHA `5921fe5b86cc995e779df4eac49ea0a84942bedc8e8bcaf15c6b1b6e99aca135`；[recipe](../../submission/public_network_20261117/rogers_repro/recipe.json)、[独审](../public_review_20261117/review/rogers_frozen_stage_review.json)。上游算法保持，新增权重选择约束和完成观察，防止原try/catch跳过组件仍称复现。
- 优化Notebook SHA `e8f5e733961da9d0030b0961712e67ff8953470f3ef52414431eb6432e79206a`；[recipe](../../submission/public_network_20261117/champion_network/recipe.json)、[独审](../public_review_20261117/review/champion_frozen_stage_review.json)。原first32cells不变；AB只改一个parent_audit参数，改收新网络审计，不覆盖旧head审计。
- 网络组件真实canary：[verification.json](../../runs/public_network_canary_20261117/verification.json)。旧生产2题无边、无变化，是合法no-op；单独合成工程夹具1边、两题变化、首位变1题，且均与直接原函数CSV相同。合成夹具只验证分数消费，不是效果指标。
- 优化真实尾段：[verification.json](../../runs/champion_network_tail_20261117/verification.json)。从旧生产真实head输出开始，新增cell32网络、cell33真实A/B加载匹配、cell34最终CSV/JSON通过；head→network→AB链和旧head回执不变得到实际验证。**没有重跑完整E2/冠军初始化，也没有新效益指标。**
- Kaggle两版可见均COMPLETE，输出/真实网络观察器通过；复现版还实际加载匹配两库。父模型可见仍走fast，不能称隐藏完整成功。正式提交的是云端代码V1，隐藏时执行完整生产流程；本地诊断CSV没有上传作答案。

## 正式接受与当前状态

- [Rogers接受回执](rogers_repro/submission.json)、[官方状态](rogers_repro/score.json)、[可见审计](rogers_repro/output_audit.json)。Kaggle实际地址为 `stormseye/casmi26-rogers0492-reproduction-1117`；服务按标题生成slug后通过只读源码/版本/依赖校验对账，未重复推送或正式请求。
- [优化版接受回执](champion_network/submission.json)、[官方状态](champion_network/score.json)、[可见审计](champion_network/output_audit.json)。实际地址 `stormseye/casmi26-champion-network-before-ab-1117`。
- [唯一冻结清单](../../submission/public_network_20261117/manifest.json)，max_submissions=2，外部写均先claim，未知结果不自动重试。本轮两次正式请求都accepted，尚未取得新分；所有下载、缓存和日志在D，produre1/2未重做。

## 对近期停滞的纠正

11/13的网络实验是AB后.25，并保护高置信库和AB命中查询，不能把其.488解释为公开AB前.35网络已无收益。此前把未对齐流程的组件/小面板结果用于推断整个生产路线价值，判断过头；「公开易得收益已吃完」也不是当前证据支持的结论。

FIORA的谱预测改善与真实同候选排序小幅增益并未证明生产排序安全，正式58435031=.285已作为反证保留。本轮先取得原版与移植版真实榜分，决定采用/停止；不预报稳定提升，不用运行次数或检查数量替代效益证据，不将PENDING当零分或新高。后续任何创新高按用户要求记录提升来源与归因边界。
