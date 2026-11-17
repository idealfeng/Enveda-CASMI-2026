# 两版冻结提交的独立审查

2026-11-17。只读原源码、冻结Notebook、recipe、metadata及已完成的组件回执；运行了便宜的编译、AST、身份和文本绑定核验。未执行全生产初始化、未启动Kaggle运行、未正式提交，也未计算新效益指标。当前未发现阻断问题。

## 优化臂：champion_network

冻结Notebook SHA `e8f5e733961da9d0030b0961712e67ff8953470f3ef52414431eb6432e79206a`，recipe SHA `4b1729fe7282cc195243f6bb64401463942ba82b9e4c3c144661cb6883f59156`。冠军原cells0–31深拷贝相等；网络插在head后、AB前；AB源码只有一处父审计参数从GUARDED改成新的NETWORK_BRIDGE。原GUARDED变量及审计文件未重写，最终观察器明确验证head→network→AB→最终CSV。原AB算法/官方身份guard、父数据版本保留。

内嵌网络helper与本地SHA `0028315c39325dc4362e3fa075bee8a2395dd0e1f3487d796ba8c89550620202` 精确相同。原Rogers函数文本及AST保持；固定LAM=.35/TAU=.6，仅读8列观测、候选/官方身份多重集保持，不新增prefix或库保护。12个身份例子与官方metric相同，summary解析夹具通过。真实历史生产两题无edge、输出不变；单独合成两题夹具1条edge且能改首，adapter和直接原函数的CSV均相同。合成夹具只证明分支和消费关系，不能当识别收益。

[冻结stage复核](champion_frozen_stage_review.json)、[helper复核](network_code_review.json)、[实际组件回执](../../../runs/public_network_canary_20261117/verification.json)。

## 原版臂：rogers_repro

冻结Notebook SHA `5921fe5b86cc995e779df4eac49ea0a84942bedc8e8bcaf15c6b1b6e99aca135`，recipe SHA `b8c7b3394eaebf074cf39566f53703bd2eccfe6283bf89aa751f5d98b6246634`。上游V1 SHA `51c32f200c265fff08bfa4a9841cb6345d1f56515dcd72e254df8da53e07ae99`；除scorer选择绑定及网络/AB调用包装外，原cells映射原样，两个函数文本完全相同。原(.12,.12,.12)先验、双模型、merge的两个SHA mismatch警告继续、rawAB无额外身份guard均保留。末层只记录AB后的重复身份，不偷偷替换候选。

10个dataset数字版本、V80 kernel实际V1（名称v80不是版本80）、原docker/T4、private/offline/GPU及recipe/function pins均核验。原V80 final逐字节等于冠军v2，所以此臂不是新权重集成。可见运行会真实执行网络和AB，而父模型仍fast；只有实际隐藏执行和正式评分能确认完整复现及我们自己的成绩。[冻结stage复核](rogers_frozen_stage_review.json)。

## 本轮纠正与边界

- 早先继承文字将merge方向写反；直接原源码证实Rogers为WARNING继续、冠军才strict assert，已通知实现者并修正建议，原源码未改。[纠正证据](merge_direction_correction.json)。
- 提取函数磁盘是CRLF，原始bytes SHA `da55c84b46a3a26fcccd9a292ed4892a62d3f50a3f07ce38bc072978a0e57822`；`read_text`归一LF后的UTF8 SHA才为`33153de76fccebe4ed2325bea7649573219e4cfb964483cd5c335ac7dc7e93b8`。部署明确按后者绑定函数文本。[上游参数确认](upstream_confirmation.json)。
- .492为作者公开报告及Alex ref58380172的复现记录，不是本账户新高。Helios .494包已被initializeddemo替换，不作强基线提交，见[本轮取舍](../RECOMMENDATIONS.md)。
