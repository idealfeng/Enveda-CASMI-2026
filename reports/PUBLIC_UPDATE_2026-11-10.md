# 2026-11-10 公开方案与讨论区窄审

本次为只读研究，辅助当日五次提交规划。官方SDK高分、近期列表各100条，另取7份公开推理源码、1份公开训练源及V8的6个小文件。全部在D盘，没有下载模型权重、大数据，也没有启动或提交任何Kaggle Notebook。原始证据在 `reports/public_update_20261110/`。

**这批检查未独立确认一个比本项目0.488更高的公开真实分数。** API列表不返回实际Public/Best数值，标题与作者自报不能当作我们的复现结果。没有搜索到不等于不存在；本次只覆盖列表窗口和选定来源。

## 对今日名额最有用的发现

1. [Alex新V13](https://www.kaggle.com/code/alexchilton/casmi26-lb-0-487-peaks-to-structures-scorer)自报0.487、提交58185447。全部排序code cells与昨日V12逐字相同；真正变化是附件加入 `popwenman/casmi26-scorer-train-v80`，第二神经路径不再退回public/public。它本身没有提供新的外库匹配算法。当前本项目已有0.488，不建议为了公开0.487重复花一槽。
2. 公开 `guhongbin/casmi26-v591-massbank-only` 的整个Notebook SHA仍等于旧Alex V12；其附件移除Takumu、同时加入V80训练kernel。因此它不是本项目固定0.488基座的单因素B-only证据。`v593-kpeaks3`同样只是既有匹配阈值分支，作者历史消融中K=3、TAU=.75、LIB_TAU=.95在其0.484基座均显示同分；不能据此预测本项目的0.488结果。
3. [ZZ3 V45](https://www.kaggle.com/code/zz3t3rn41/casmi26-peaks-to-structures-v2)确有新的V8模型选择分支，同时还改先验、质量规则和NP promotion。不能整套替换后将差值全归于编码器。Pablo V14有三枚V80种子融合与额外命名组件，但未取得超过0.488的可核实成绩；不建议今日挤占新数据对照。
4. `heliosli/casmi26-0-488`虽然当前标题0.488，源中仍有历史0.477记录、FRIGID/SAFE-GPT生成和若干未暴露名称的dataset依赖；不适合作为一条即拉即交的更高基线。

## V8是否值得另做基座实验

[bgunshui/casmi26-scorer-v8-model](https://www.kaggle.com/datasets/bgunshui/casmi26-scorer-v8-model) v1发布总大小37,838,240字节，其中权重37,831,657字节。发布许可CC0。已读配置确认为width384、heads12、layers4、embedding384、hard negatives48、negative pool512、epochs160×400steps；当前v2为192/6/3/192、16/128、80×500，确有实质差异。

- config SHA `343f0dbe79b7809a908d694bb649480dafce8f615b38bfae27b0b61526d2216f`。
- model.py SHA `2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39`，仍是同一参数化模型实现。
- features.py SHA `d230b7dc98043e851497c352e0fef056aa6e3e7d33f4899b41e4032e5d493582`。与旧版相比，结构特征不再先做tautomer canonicalization，缓存身份改为SMILES；必须保留其训练时预处理，不能用旧features冒充相同输入。
- 发布训练记录报告随机8小时holdout诊断MRR0.6755596、最佳epoch120，最终以全部数据refit120epoch；旧v2的0.6603来自不同5小时切分，二者不是可直接比较的干净验证。data_audit明确0个external-only身份，仍仅官方train，没有新增测量信息。
- 旧训练head的输入embedding是192，不能直接套384维V8。当前0.488晚接入wrapper还严格固定旧v2权重；测试V8必须保留独立旧v2 bundle，或者显式设计新的晚接入组件，不能只换附件。
- 权重本次未下载，因而**没有实测权重SHA、严格加载、速度或实际榜分**。猜测的 `bgunshui/casmi26-scorer-train-v8` 地址404，尚未完成准确训练源码绑定。V80公开训练源已保存，其配置基本同当前v2，未证两枚checkpoint字节不同，不能把V80标题当额外新模型。

V8是后续可测的备选基座，尚不是今日已就绪的替代名额。优先保留本项目0.488，完成A/B来源归因、新实测库Enveda证据与匹配物理约束；不要仅因更宽模型和更高异切分诊断数立即换主干。

## 新讨论与官方事实

- [754610主办回复](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/754610)：David明确允许官方发布的DreaMS checkpoint，同时重申最终方案须能由比赛数据和公开记录资源端到端复现。因此DreaMS可进入月度新基座候选，不应再笼统将其排除；本次没有下载或接入。
- [757307](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/757307)：MassSpecGym/MIST的NIST清洗边界仍是参赛者问题与跟帖，读取时没有主办新裁定。不能将参赛者担忧写成官方新增禁令。
- [757309](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/757309)：PubChem/COCONUT候选索引再分发也是新提问，读取时无回复。
- 昨日757152主题现显示Deleted Topic；不要把已删的参赛者问题当作正式规则更新。

本次规划建议：不为复现一个未高于0.488的标题重复消耗今日槽位。V8或DreaMS需要独立的小规模加载/测速、明确训练源与预处理绑定，再决定未来哪一天作为新组件对照。
