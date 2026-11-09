# Forward覆盖审计与Na新增证据

对象为已有48查询开发诊断，存在公共预训练曝光；没有读取锁定250的查询或真值。这不是干净泛化评价，也不是0.481隐藏MASS运行的完整复现。

## 覆盖结果

主top25共1200行：GL按官方评分身份有分1100行，ICE有分1125行。GL缺分100行由50行不支持观测adduct、25行Na-only查询未送入、25行后续进入主榜的候选未送入构成；ICE缺分75行。没有发现“候选已送入、输入适用，但运行漏掉有限分数”的案例。按官方身份已有分不代表原始SMILES上一定有分，也不保证后续排序消费了对应信号；CSV另列exact-SMILES缺分与frozen evidence缺分。

现有检索日志的联合候选共7045个query—官方身份组合，GL未送4346、ICE未送4166，但9个真结构已经在最终候选内而首选错误的查询，真结构全部已送ICE与GL。扩大forward候选覆盖有空间，不能据此断言它是当前排序错误的主要原因。另2个真结构不在已记录检索候选内的查询不能靠重排解决。

## Na补评分小试

原GL输入只含146张H+，原ICE输入另有17张Na，分布12查询。固定保留原ICE候选列表及顺序、只补这些Na谱；11查询增加观测，1个Na-only查询首次得到GL分。12查询里仅cross_NOFOAYPPHIUXJR当前首选错、真结构rank8，其余11个本来首选正确，因此不能只期待补谱带来收益而忽略退化。

实际glacier.pt SHA为9192e4c2eeafe83317d5a2c2641e1fc4d68934488757a4faafeb66f2ab397a12。checkpoint配置embed_adduct/collision/instrument=True，adduct_embedder为14×22，源码Na映射index1；真实Na token和Na碎片质量偏移走原模型路径。adduct_embedder本身是固定onehot/multihot表示，Na行存在不证明模型训练中见过多少Na样本。

小试结果：12查询、1030候选、1511候选—谱分数全部有限，missing/nonfinite为0；1030个逐谱均值重构最大差5.55e−17。模型总用时102.74秒，加载75.22秒、预测21.23秒，峰显存0.44GB。14项独立检查全通过，原H+输入和输出fresh SHA不变。

产物位于`runs/gl_na_probe_20261108`；验证为`verification.json`，运行记录为`gl_out.json.meta.json`。没有改最终排序、没有评价新MRR、没有训练或提交。新增谱信息已经跑通，尚无排序或榜分提升证据。后续若融合，不能把Na-only均值与原H+均值机械等权平均；必须保留独立特征或按实际有限逐谱观测重新聚合，CE沿用原runner也没有在本试验修正。
