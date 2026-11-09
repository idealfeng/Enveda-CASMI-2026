# 2026-11-09：0.482 后的机制对照与新信息

本报告仅设计和源码分析；自己的昨日分数由主线程另行官方 API 核对。本轮子任务没有启动云端 Notebook、正式提交或读取隐藏查询/标签。

## 0.482 能说明什么

昨日 `mass_guarded_head_tail_1108` 完整保留旧 MASS 流程，在全部旧规则及旧审计之后才使用两个冻结新 head，只排序最终列表的 rank8–25 同分子式原槽位。候选集合和前7不变。因此它与昨日流水线内部的全量替换（seed0=0.465、seed1=0.470）同时改变了接入位置和影响范围，不能断言“新 head 天生只能排尾部”。0.001 是一次公开榜观察，尚无私榜或多次稳定复验。

两个有区分力的对照：晚接入、仍同式槽固定，仅前缀7→3；晚接入、前缀仍7，但将 learned head 换回原 frozen-v2 逐谱均值。后者区分新训练收益与已有 v2 在最终列表重排的收益。直接增加 seed 或重复扫融合权重无法解决这个归因。

昨日 head 实际优化的是 positive+32 个全式最强错误候选的 CE，30991 个负例中15445同式。新的训练目标可以固定表示缓存，只用同式正负配对/同式列表损失，并约束分数偏离旧 mean；训练身份/负例仍排除所有 Monitor/Eval 和旧锁定面板。现有 frozen-v2 full-refit 曝光不因新 head split 自动消失。实际目标及训练结果由训练子任务独立记录。

## 今天有实质新增公开源码

官方只读 API 扫描两组各100条 notebook 库存；讨论从151增至154。列表没有暴露数值 public_score/best_score，因此标题0.485、0.530不可视为已验证成绩。4份源码共约3.2MB保存至 `third_party/public_scan_*_20261109`，版本和 SHA 见 `reports/public_baseline_scan_20261109_design/source_snapshots.json`。

- [Alex V12](https://www.kaggle.com/code/alexchilton/casmi26-lb-0-484-peaks-to-structures-extlib)：源码首段明确自报正式提交58141942=0.484，2026-11-08；同作者称 Ozertuu 原样0.478。不是我们帐号已得0.484。
- [Ozertuu V22](https://www.kaggle.com/code/ozertuu/0-485-sota-casmi26-from-peaks-to-structures)：相对旧 MASS，只改 POP/SPEC .10→.12、将两个 physical hash assert 改 warning，并增加外部实测参考谱 rank1 overlay。Alex 相对它的算法仅 TAU .85→.80。
- Roshan V33/V34还有先验、升首、physical邻接换序、多级库阈值等多项改动，不能归因于独立新 encoder 或标题分数。本轮不盲目采用整套多项强推规则。

Alex/Ozertuu没有附 bgun v2 或训练输出 kernel。`sanpier/catalogue-experiment-saner/1` 文件列表只有 panel/combiner/parquet，无 `final_model.pt`。因此复现时必须明确原来的 public/public fallback；不能擅自补 v2 后声称是原样。新的 baseline 审计会核验两个路径都为固定 public v1。

## 外部实测参考谱组件

两库当前版本及实际读取5文件共264584131字节（约252MiB）全部下载到 `D:\Paper\casmi\assets\kaggle`，fresh大小/SHA通过。完整回执 `library_downloads.json`，实际 schema `library_schema.json`。

| 数据 | 版本 | 实际文件 | 许可/来源 |
|---|---:|---|---|
| takumuhata/casmi26-extlib | 2 | ext_meta.parquet、ext_mass.parquet、ext_mz.npy、ext_in.npy | Kaggle标CC0，声明GNPS/MassBank/MoNA合并；metadata无逐谱license列 |
| samartalwar/casmi-2026-spectral-library-massbankharmonized | 1 | spectra.parquet | Kaggle标CC BY-NC-SA4.0，逐谱保留license/authors/publication/source |

A实际200724谱×128 float32峰；mass表144924结构，但列叫mono_mass，原代码只有exact_mass才拼接，因此不会因行数不同错拼。B139744谱；原代码去CASMI子集、缺SMILES及少峰后本次真实加载124160谱。**这些总量不等于对官方train或隐藏测试的新覆盖。**

原匹配条件保持不变：同离子模式、precursor窗口10ppm+0.002Da、sqrt强度cosine、片段绝对容差0.015Da、至少4峰且cos≥.80，原管线library_max≥.90保留；有命中则参考SMILES升首，候选外结构插首并截25。原程序计算neutral mass后并未使用，不按adduct约束，不做CE匹配。其raw-SMILES去重会重复官方tautomer/stereo身份，这是输出有效性风险，不能称理论上每次命中都正确。

本地 helper 只在原函数AST的两个 `refs.append` 和一个 best-match 决策前插观察调用。匹配数学不变；新增明确的官方身份输出guard：非法/重复身份proposal保留该query原列表并记原因；全局绑定/库加载失败则删除最终CSV、保留control和错误记录。fast可见dummy路径跳过匹配但核验全部库文件，防止不必要真实计算。

## 两个准备阶段

`scripts/build_external_overlay_stages_20261109.py` 只准备，不云端写入。

1. `public_alex_extlib`：Alex V12复现并明示上述输出guard/fast/观测适配；11个dataset版本固定，原public/public路径固定，所有其他原源码cell精确不变，大source cell无损压缩。
2. `mass_guarded_extlib`：昨日0.482整份32cell逐字不变，最后才追加完全同一外库匹配和guard；旧v1/v2与新head全部保留，只添加参考谱信息。原8+两新库，共10个固定dataset。

不能将这两者分差全归于库：baseline的模型和先验也不同。更干净的库增益比较是昨日自己的0.482 vs `mass_guarded_extlib`。

真实两库CPU canary `runs/external_overlay_actual_canary_20261109/verification.json` 全10项通过：A/B真实谱自匹配、原库强匹配保护、官方身份重复proposal回退、缺query保留、改动已观察cos被拒绝、错误control绑定删final等。实际原overlay16.2秒，含文件绑定和消费链重建20.13秒；这个5-query接口测试不代表全测试耗时或榜分提升。无GPU、无训练、无hidden查询。

## 官方许可澄清

已读取官方帖子完整原文至 `reports/discussion_review_20261109`，不可沿用“NC自动不得奖牌”的旧判断。

- [750330，David，2026-10-17](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/750330)：取消开源非商业许可数据限制；专有/不免费或NIST仍禁。
- [748363，David](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748363)：CC-BY-NC-SA一般可用。
- [745615，Marie](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/745615)：非商业条款不自动导致奖金或奖牌资格丧失。
- [749217，Marie Q4](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/749217)：公开GNPS/MassBank/MoNA一般可按发布使用，避免已知许可违规/NIST来源；MassSpecGym特定模型另有明确批准。

新帖子757152是参赛者提问NIST-trained ICE/GL与atlas，读取时0回复；不是官方新增禁止或批准。新的模型/数据不得只看标题判断。当前没有对外发帖或消息。
