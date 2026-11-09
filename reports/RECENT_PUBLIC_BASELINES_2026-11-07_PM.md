# 11月7日下午：公开方案更新复查

读取时点：北京时间2026-11-07 14:39–14:50。只读搜索、官方API和小源码；没有创建云任务、提交比赛或运行模型。所有新增文件在D盘，上午快照未覆盖。

## 结论

有新代码可以作为今天的公开基线：**Gold Apex V35**，不再是上午V32/Roman的重复包装。其新机制是放宽物理首选判据、逐张谱投票、双模型outside打分、内联质量惩罚，以及NP首选提升/主动outside插位。完整配方可能提升，也可能因更积极地替换首选与候选而退步，必须保留一个完整公开基线并和优化版各自正式评分。

没有找到能够独立核实当前数值高于我们0.481的新公开版本。API高分顺序不提供具体Public/Best数值；网页索引及直接打开新页面未返回可用当前分数，不能把标题0.482或排序位置写成已验证成绩。我们自己的四条真实结果现在为dual0.480、tri0.475、RR0.436、公开MASS0.481；这些是提交读回证据，不是公开作者分数。

## 本次新发现与去重

官方`scoreDescending`、`dateRun`各读取100条。实际get_kernel快照下载17份，保存于 `third_party/public_scan_*_20261107_pm/`。

| 来源 | 实际版本/源码SHA | 结论 |
| --- | --- | --- |
| [Gold Apex](https://www.kaggle.com/code/zz3t3rn41/casmi26-peaks-to-structures-v2) | V35，`759067bc1449427089e95b811ee49f866580590905484577fe09a143740a2842` | 比上午V32有实质改动，今日最值得做一个完整公开基线 |
| [Alex MASS](https://www.kaggle.com/code/alexchilton/casmi26-lb-0-481-gold-apex-v22-mass-prior) | V11，`c51dcb371e8f0d5f1786c0198441d058a69310caea64e0e5e66f06b6c615dc40` | 虽在高分列表第2，但全部15个代码cell与上午pop MASS V2逐字相同；仅Markdown/位置不同，不能重复占额度 |
| guhongbin alex0481、hoowoo MASS | V2/V1，完整源码都等于Alex同SHA | 重复上述同一配方 |
| [Eason V44](https://www.kaggle.com/code/easonyanyan/casmi26-v44-dual-sota-exact-mass-apex) | V1，`a1ea0fe50eff6f64c0906f43c66b849ffca0a612e66c17eb5875c2c65ad85f21` | 弱先验NP0.02/SPEC0.05/gate0.87、双模型、质量惩罚、OR覆盖mask，outside双模型；与V35不同，但无新更高实际数值证据 |
| Flex | V61及SHA未变 | 未出现更高新Flex版本 |
| Roman | V17及SHA未变 | 已知BOTH/RR配方；不优先于我们刚取得0.481的MASS-only路线 |
| Helios主分支 | V2及SHA未变 | 没有新的源码或资源公开证据；此前无法完整复现的依赖问题不能靠成功写CSV忽略 |
| popwenman V32 | V1→V2，SHA `75eacbca1f810f3580f822bb59fc42d6d5d5a2698440673ba29fc6f716bd3f8a` | 配置现为MASS；仍旧质量表/RR内嵌骨架，不是Gold V35的新物理/merge实现 |
| Pablo | V6，源码SHA仍`3c2ac5...` | 版本号变化但源字节与上午V5相同，不作为新算法 |

## V35可直接执行的来源与资产

源文件：`third_party/public_scan_zz3t3rn41__casmi26-peaks-to-structures-v2_20261107_pm/source.ipynb`。

关键cell：配置4、session/隐藏模式5、嵌入旧pipeline11、stage machinery12、物理payload13、主/outsider双神经调度14、physical调用15、最终merge18。

原metadata无kernel依赖，数据源为已用旧6项、bgun v2、LOTUS，以及源码没有直接引用的catalogue/额外metric wheel。仍使用原public scorer与v2；没有新的checkpoint结构或新训练要求。可复用原来验证过的public `44436b...` 和v2 `c08d210...`，用实际模型SHA观察器阻止first-match或静默fallback。

V44 metadata反而含一个空dataset引用且未明确挂v2；若采用必须补齐已知公开模型、记录工程适配，不能照抄无效metadata。今日更推荐资产清晰的V35。

## V35真正的代码变化

与上午我们实分0.481的pop MASS V2相比：

1. **物理评分core不变。** `_physical`的SHA仍为 `eeacdcf0afb173a8b438054d93c30f061df7c9c69d1ae32db3530b2916f2e6a7`。变化发生在`_post`，旧SHA `cd1594b3bbfa75ce30997559c5403438b7cec011879dcb9c0d48e111715dd85d`，新SHA **`bce2f1a1cdda3b31cfaaacfdfe909b6474d88c3635ea971f02a782c8f136c579`**。新源码只assert长度，不再assert完整post SHA；我们的复现应仍固定完整新SHA。
2. **逐谱投票与更多top1机会。** 原来两张谱成一组，现在每张谱单独一组；最低谱数3→2。原来library>=0.87禁改top1，现在候选library比leader高0.02也可进入。原rank2候选采用较宽的margin0.080、baseline margin0.020、neural margin0.18、cos不差于leader；更深候选维持0.095/0.028/0.23及cos+0.003。rank2竞争分另加0.015。
3. **outside双模型。** 原MASS方案主候选双模型、outside只用OURS；V35新增outside的public/v2等权z融合，保留原时间保护和异常fallback。
4. **mass内联merge。** 参数仍center−1.5ppm、free3、full8、weight0.15，但直接对merge候选计算penalty。neutral mass优先来自`effective_query_spectra.nm`；fallback支持10种adduct，覆盖旧raw质量表遗漏的脱水adduct。它取每query第一条nm，不是跨谱稳健聚合。
5. **NP首选promotion。** 弱库且physical没有换leader时，若runner是NP而leader不是、leader pop<15，且runner的neural+pop+NP+mass证据超过leader0.02，就将runner升top1、旧leader放第2。这不是只改尾部。
6. **主动outside插位。** 弱库query把4个outside候选插到rank8/14/20/24，保留前7。它会替换原top25成员，不是仅补空槽。观察器不可错误要求与旧配方的候选集合相同。
7. **NP membership扩展。** 从LOTUS parquet补充np_map身份，而非只使用pool popularity表既有NP flag。仍保留高NP0.12/SPEC0.10/gate0.78。因此新增promotion和更多NP身份是一个耦合的强先验方向。

review-only物理代码已拆到该快照的 `review_only/_physical.py`、`_post.py`，供独立审核，未执行。

## 如何解释目前的提升、避免无效方向

从0.479到dual0.480，支持“192宽v2和public的互补”这条实际榜分路线。加入v4成tri0.475和RR0.436则没有支持继续加大这些组件的证据。公开MASS0.481同时改变了dual、先验、LOTUS与质量规则，额外0.001不能全部归因于质量惩罚；必须用基线/删减对照分解。

同分子式的异构体exact mass相同，所以质量惩罚主要处理不同式近质量候选，不能声称它直接分离同式连接异构体。V35新的逐谱物理判据和首选promotion才更直接影响这类排序；outside插位则涉及召回与尾部名次交换。

建议今日保留V35完整公开基线，优化版优先围绕四个不同机制：保守化/关闭主动outside替位、控制NP promotion与先验强度、对跨谱nm做稳健融合、给放宽的物理top1引入CE独立性/重复谱保护。不要再把v4/RR加回所有分支，也不把多个标题相同算法当五个方案。

## 检索证据与限制

本次web搜索和直接打开新notebook页面都未取得当前具体Score。已有公开讨论[743254](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743254)继续支持重点研究异构体与独立验证，但它是旧讨论，不能冒称今天新发现的涨分配方。公开页面无法读到分数时，最终以我们账号实际提交结果为准。

官方列表和新源码元数据：`reports/public_baseline_scan_20261107_pm/`；采集脚本 `scripts/scan_public_baselines_20261107_pm.py`。列表lastRunTime与get_kernel字段仍不一致，报告不据此编造精确发布日期。
