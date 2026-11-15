# 11/14公开源码：哪些有新信息，哪些仍是同一配方

范围：官方只读API各取scoreDescending、dateRun前40条，下载6份公开Notebook源码（每份小于2MB），先读取一个新外库的文件清单、3KB摘要。随后主控按既有用户授权补齐固定ExtLib2 v1的128.95MB资产，7文件的版本/长度/本地SHA已核验记录。未执行外来代码、未加载模型或大数组、未训练或正式提交。所有产物在D。

本地对照为58156482/.488的冻结配方。分数列表中的public_score与best_score均为null；排序靠前、标题和作者笔记不能替代正式提交读回。来源版本和源码SHA已保存，运行日期优先采用inventory的last_run_time；get_kernel元数据里的同名日期与列表不一致，不用它声称某一算法刚发布。

## 最有价值的新线索

**1. ExtLib2是真正新增的实测谱信息，值得优先核清来源并做覆盖差异。** [zz3t3rn41 V55](https://www.kaggle.com/code/zz3t3rn41/casmi26-peaks-to-structures-v2)新增第三个实测参考源[nakhun/casmi26-extlib2](https://www.kaggle.com/datasets/nakhun/casmi26-extlib2)，不是另一个同内容v2权重。公开v1共128,947,012字节；摘要记载490,840谱、62,782结构，来自GNPS2 432,221、MassBank 44,480、MSnLib 14,139，含123,995条[M-H]-及1,430条[M+Na]+。构建日期11/12，原AB只有约324,884谱。

这里还不能断言490,840条全是相对我们AB的新谱/新结构；需要按官方身份、谱和来源去重。作者offline_eval在250-query面板报告A覆盖214、B覆盖247，高阈值命中数增加，但其`gain proxy`是计数代理，隔离和真实ranker/最终名单边界未说明，不当作MRR或榜分增益。

Kaggle许可为`Other (specified in description)`、description为空，尚不能直接据文件名判定完整可用。build_log列出GNPS2的ALL_GNPS_NO_PROPOGATED、MassBank 2026.11和MSnLib具体文件，优先沿这些上游确认许可与是否允许竞赛部署。**MassBank_NISTformat.msp是MassBank发布文件的格式名，不能仅因含“NIST”就说它来自受限NIST库。** 三份小文件及hash在`extlib2_tiny/receipt.json`，元数据在`supplementary_assets.json`。后续已补齐128MB实谱至`assets/kaggle/nakhun/casmi26-extlib2/v1/`；`extlib2_download_receipt.json`和资产目录同名receipt记录7项长度和SHA、归档SHA及D盘路径，未解析数组/谱、未测重叠或收益。取得资产不等于已完成上游许可核查或可获奖部署判断。

建议的下一步：完成来源/许可核对→利用已固定v1只做相对AB新增合法身份/实测命中统计→再在精确.488保持旧命中行为的条件下追加Source C，基线与追加版分开读真实榜分。不要先扫.78/.80等阈值。

**2. Helios的.489标题对应的源码确实引入另一条生成器，但缺公开附件，不能称可完整复现。** [heliosli/casmi26-0-489 V2](https://www.kaggle.com/code/heliosli/casmi26-0-489)在旧.477谱管线之外加两项：rr3图网络＋Transformer的1–2切碎片证据（训练结构FREEZE纠偏）；第二张T4运行FRIGID-base，以E1预测指纹及首选分子式生成结构，指纹相似度≥.7且≤30重原子时向第2位插入，首选不动。它比放宽旧Engine的6→12母体是不同的生成信息。

但metadata有两个空dataset来源；代码要求`rr3_config.json`、`rr_deploy.py`、checkpoint，以及`frigid_runner.py`、`DLM.ckpt`、SAFE-GPT缓存与wheels。未找到就跳过，源码本身无法构成有效复现。此前也已见同类Helios/FRIGID路线，因此新.489标题不是已公开了所有缺件的证据。现阶段优先寻找这些完整可用的公共包或上游实现，不把少组件运行记作同配方。

**3. 独立神经编码器有新架构，但当前WSP Notebook质量不足，不能直接提交。** [kingdamon/casmi26-wsp-dual-encoder-inference V5](https://www.kaggle.com/code/kingdamon/casmi26-wsp-dual-encoder-inference)的新增cell35定义Conv1D谱编码器（2000 bins、0.5Da/bin）＋2048-bit ECFP分子MLP，共256维嵌入，按`1/sqrt(base_rank+1)+.22*cosine`融合，属于独立于现用峰Transformer的实际结构。

然而其[训练Notebook](https://www.kaggle.com/code/kingdamon/casmi26-cycle-3-wsp-gpu-trainer)只读请求返回403，公开模型查询无返回项，两个kernel附件为空。没有权重就静默保留原基线。若有权重，cell35读取`candidate_smiles`并按空白分隔，而前面生产输出为`smiles`且用分号；同时把多谱同molecule_id的DataFrame当单谱处理，未聚合。标题还称precursor-bound，但新增cell没有分子式/精确质量过滤。这些是源码可见的部署缺陷，不是本地运行验证。不能按名称中的WSP或训练时长直接判强；须先取得合法权重、训练数据/划分，再修输入与实际效果。

## 热门.500标题的真实差异

[ozertuu/0-500-casmi26-dual-neural-physical-isomer V45](https://www.kaggle.com/code/ozertuu/0-500-casmi26-dual-neural-physical-isomer)是目前可读的新slug，旧无前缀地址404不代表方案消失。**其首段写的是目标.500+、已验证基线.487，不是已经取得.500。** API未暴露实际该版本榜分。

V45仍嵌入同一FROZEN、MetFrag-lite、post和公共reranker。相对我们.488，主要改为质量中心-1.5ppm、free3/full8、旧RR8开为BOTH、先验/外库tier条件。metadata现有extra kernel只有popwenman V80；cell14的`_swap_to_ours`直接用第一个额外权重替代公共scorer，已不是旧V18的`.5/.25/.25`多模型算式。V80 final与我们v2相同已有SHA证据，未出现可核实的新第三模型；旧ozertuu scorer数据集请求仍403。**不能为了.500标题重复做一次同内容权重集成。**

[Alex V14](https://www.kaggle.com/code/alexchilton/casmi26-lb-0-488-peaks-to-structures-network)首段承认是analyticaobscura N1c的复现：同谱网络阈值.6/≥6匹配峰、λ.25，位于外库之前。我们11/13已提交不同位置且更保护的N1c（Public.488），不能说逐行等价，但它没有新的基座或数据。新版zz3 V55同样主要为MASS、N1c、adduct-aware AB和新Source C；新价值优先看Source C而非另一组质量/网络系数。

## 对停滞最有解释力的公开经验

[prvsiyan/what-the-library-has-not-heard V2](https://www.kaggle.com/code/prvsiyan/what-the-library-has-not-heard)明确报告：FRNet在神经分数单独排序的旧池上提升.012–.014，但加回生产已有碎片证据后只剩.001–.004，实榜.487→.486；所以后续改为**真实整条流水线输出**上的隔离回放。它构造190个训练文件和训练结构表均不存在的MassBank身份，移除两外库自己的参考，当前只跑30个测速且作者明确不拿30题分数判断改进；也承认ICE/GL/DreaMS预训练曝光未知。

这支持停止把“已有候选分数换个融合方式”视作新信息。不是要求重做我们的produre1/2；应复用已有验证框架，但新组件要相对精确.488的候选和全流程输出判断，先确认增益是否已被原碎片/神经证据吃掉。MIST等真正独立的分子子式信息由另一条讨论区审查负责，优先级可高于继续叠当前GL/head分数。

## 源码与指纹

| 来源 | 本次版本 | 源码字节 | SHA256 |
| --- | --- | --- | --- |
| Helios .489 | 2 | 678144 | e102d0218293fa1ec6ea0c80d102ce44d0e99bc4207321a304a9428da128e7e5 |
| Ozertuu目标.500 | 45 | 809666 | a77bde9b0b3df2cc836001aee4f8e298790bae61ded9565dfe6448b06d5ce0e3 |
| WSP dual encoder | 5 | 168734 | ab77323e4ae1d2e705512533d531a6aab51c810174819acbf28c019c363f4a99 |
| 未见结构回放 | 2 | 970009 | 2f9e6a206ae873e75d08a78360e825e8b9ade9c6b8a1e604d3cdf197c1bf37a4 |
| zz3 v2 | 55 | 826643 | 22e42f998a6a3ba4001272af40de7794a5c5a42692205149663e940a038e6a61 |
| Alex .488 Network | 14 | 816835 | 9bc6431ef5062876e973b7b7bbcd106ccc4cfaadeea01e3924c42ead8a03d95f |

`scoreDescending.json`、`dateRun.json`和`source_receipt.json`记录原始官方读回；每份源码按原字节保留并仅拆成`cells/`供静态阅读。`embedded_source_fingerprints.json`表明六份多数沿用同一物理碎片/后处理源码：`_physical` SHA eeacdcf0…、`_post` cd1594b3…、常见公共reranker e61c7c44…与我们冠军逐字节相同。模型权重未载入，因此对新权重只判断可用性/来源，不报模型效果或SHA去重结论。

本轮建议优先级：先核新增实测ExtLib2与讨论区独立MIST；Helios完整包作为候补；不按.500/WSP标题直接复现提交，不继续同源权重和旧GL/head的无依据融合。
