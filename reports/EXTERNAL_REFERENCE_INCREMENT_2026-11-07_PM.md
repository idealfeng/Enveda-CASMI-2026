# 训练库外参考谱增量：11月7日下午可行性审查

结论：**Enveda-180原发布数据可合法作为通用外部参考库，并且已经有可直接挂载的公开Kaggle派生包；这条路线无需重训。** 但本次未读取完整谱库、未独立计算相对官方train或现有结构池的实际新增，也没有证明隐藏测试覆盖或涨分。建议作为下一轮独立数据增量实验，不强行插入本日下午已经准备的五条MASS优化提交。

本次仅下载公开元数据、README、manifest，以及55,546字节Parquet footer；未下载完整谱文件或任何超过20MB的文件，未读取竞赛测试答案、锁定250真值或运行模型。全部产物在D盘。

## 1. 主办许可和计数边界

[官方讨论745148](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/745148)中，Competition Host Marie Killian明确允许使用Enveda-180 Zenodo发布数据。该帖作者报告：按官方去立体化/互变异构评分身份，相对train有816个标准adduct结构、3,193张谱，其中408张H+谱；另约2,900个结构只出现于in-source-fragment adduct。**这些是讨论作者的统计，本次没有复算，也不能解释为816个隐藏测试命中。** 主办对其缺失原因只作可能被train准备流程过滤的解释，没有确认隐藏重叠。

原始来源：[Zenodo record 21346580](https://doi.org/10.5281/zenodo.21346580)，作者Krettler等，Enveda-180，许可 **CC BY 4.0**。原数据用于训练或检索时保留完整来源、许可及版本记录；不将目录或模型公开可访问等同于其他来源的许可证明。

## 2. 原Zenodo记录与可下载粒度

已保存原API元数据和版本列表。固定记录21346580的publication_date为2026-07-13，created为2026-07-14 UTC；metadata未标语义version，不能擅称v3.0。concept DOI为10.5281/zenodo.20436850，API当前返回三个记录：21346580、21211983（7月6日）、20436851（metadata明确v1.0.0，5月29日）。复现应固定具体record和文件校验值，不只固定concept DOI。

| 文件 | 压缩字节数 | 格式/用途 |
| --- | ---: | --- |
| enveda-180-filtered.mgf.gz | 285,632,591 | 本记录最小谱文件，仍约286MB |
| enveda-180-filtered.msp.gz | 286,358,046 | filtered MSP |
| enveda-180-filtered.jsonl.gz | 312,000,735 | filtered JSONL |
| enveda-180-filtered.parquet.gz | 366,300,248 | filtered Parquet再gzip |
| enveda-180.mgf.gz | 1,699,674,313 | 原始MGF |
| enveda-180.msp.gz | 1,700,550,682 | 原始MSP |
| enveda-180.jsonl.gz | 1,856,437,727 | 原始JSONL |
| enveda-180.parquet.gz | 2,638,835,469 | 原始Parquet再gzip |

记录没有独立的小型增量谱文件或轻量结构目录。对gzip外壳文件，不能只凭HTTP Range直接挑任意结构/谱；下载少量头部也不能证明已取得train外完整增量。原记录MD5及稳定链接均已保存在原元数据JSON，未下载大文件验证MD5。

## 3. 已找到并验证元数据的Kaggle派生包

**可挂载：`egehseyinca/enveda180-casmi26-reference-ccby4/1`。** [公开数据页](https://www.kaggle.com/datasets/egehseyinca/enveda180-casmi26-reference-ccby4)。匿名卡片API确认isPrivate=false、当前V1、CC BY4.0。README明确来源为同一Zenodo记录，声明不包含竞赛test labels。卡片文件总计218,633,992字节。

| 文件 | 字节数 | 发布manifest声明的SHA256 |
| --- | ---: | --- |
| enveda180_hplus_hminus_references.parquet | 218,514,313 | 37b8f37c5f5f536ed804d4d0456e20f183fa32388f30ae1c1712928471146069 |
| enveda180_only_candidate_aliases.parquet | 116,885 | 3ed2d8f086e51931798a34e241027de66cad76b929c0dba1d866f31f2b21e150 |
| README.md | 1,413 | 8c11be644b23b5ec48a52dc47d97ccf1a3ca471f8ad6d19e35408e454406e6d1 |
| content_manifest.json | 1,381 | 本次下载SHA39db3b7d9fca35c56f3f2d44fa1245e159c89a5b03cd2a02f976b6a7ecb5b297 |

README/manifest本次已完整下载并校验。两个Parquet的上列SHA是发布者声明，**本次没有下载全文件，尚不能称独立完整SHA验证。** 挂载后运行前应对实际全文件fresh SHA核对，防止数据源指向不同内容。

发布manifest计数：730,252张参考谱，H+554,650/H−175,602；包内已删除285个同adduct精确signature重复。另有3,720条源库独有结构alias，涉及3,717个scoring identities。该结构目录与帖子816标准adduct结构是不同计数口径，不能直接比较，也不能把3,717都称为有可匹配H+/H−谱的新结构。

### 独立检查的Parquet schema

本次两次HTTP206读取精确字节范围，共55,546字节，获取55,538字节metadata footer；pyarrow仅解析footer，确认 **730,252 rows / 48 row groups**，与manifest总行数一致，没有读取峰列表数据页。

| 字段 | 类型 |
| --- | --- |
| reference_key | large_string |
| smiles | large_string |
| neutral_mass | double |
| adduct | large_string |
| ms2_mzs | list<double> |
| ms2_normalized_intensities | list<double> |
| spectrum_signature | large_string |

没有CE或instrument字段。已知来源是Enveda-180不能恢复每谱CE；该派生包适合same-adduct参考相似度，不宜伪造跨CE一致性特征。reference_key虽声称为评分身份，使用前仍应以候选SMILES和官方RDKit2026.03.3核查；不能默认它等于raw InChIKey14。

## 4. 最小接入路径

1. 在新实验Notebook附加上述V1，无需先把218MB谱下载到本地。读取README/manifest、核对实际全文件SHA和schema、版本及来源；不改变当前0.481产物。
2. 先只读`reference_key/smiles/neutral_mass/adduct/spectrum_signature`建立元数据索引。用官方评分身份与现有train、PubChem∪COCONUT结构池分别做membership审计，分开统计：新结构、有新谱的老结构、精确重复、不同adduct/条件。同一结构在多个库中出现不能算独立召回增量。
3. 第一试只对`[M+H]+`/`[M-H]-`使用同adduct、质量窗内的外部参考相似度，复用现有峰预处理和谱相似度实现。不要对400×730k做无质量约束全比较。先记每query候选/参考数与时间，不预设会有多少命中。
4. 作为独立外库overlay输出分数、来源、候选官方身份和匹配谱signature；保留原强谱库命中，首次仅测试已冻结的高置信回填/重排规则。它可能帮助结构召回，也可能为已有结构补条件；这些必须分别测量。无CE元数据时不把多条相关谱当独立CE票。
5. 在公开、确定性冻结的开发面板上测试假阳性、重复制谱去除与排名变化；所有开发目标结构须从所有参考来源按既定验证任务全局排除，或者明确这是允许独立参考谱的library-retrieval测试。不得使用锁定250反复选阈值；不同验证任务不能混报。最终只有正式隐藏评分能说明本比赛收益。

可先做更轻的结构目录审计：`enveda180_only_candidate_aliases.parquet`只有116KB。它相对train新增不代表相对PubChem∪COCONUT新增；在尚未证明有结构池缺口前，不应仅为扩池增加同式干扰项。这个文件没有谱，不能替代reference overlay。

## 5. 成本与今天是否可接

没有新训练需求；挂载已公开数据即可离线运行。元数据筛选和有界质量匹配可独立实现，不必重建2.54M主谱缓存。218MB是压缩文件体积，解码全列和Python对象可能显著占用更多内存，尤其本地WSL只有约8GB；建议在Kaggle分阶段读取，先做数量和吞吐测速，再固定预算。这里没有测量全库读入或匹配耗时，不给虚构分钟数。

**技术上今天可以挂载，但尚无已审计、可直接插入当前MASS配方的matching overlay代码。** 元数据/来源/许可已具备下一步条件，实际train增量、重复处理、候选融合及时间/内存都未验证。因此不建议为赶第五个提交直接把整个mirror混入主流程；本日下午先完成有真实榜分依据的MASS改动。外库overlay适合单独预留下一批一个分支。

## 6. 其他公开资源筛查

- `anhnamphamhoa/casmi26-extlib-compact/1`：公开CC0，4.68MB，卡片明确只是mass/SMILES catalogue，**没有谱**，不能作为外部谱增量。
- `takumuhata/casmi26-extlib/2`：公开CC0，当前文件总约264.7MB，包含`ext_mass.parquet/ext_meta.parquet/ext_mz.npy/ext_in.npy`及coconut_index。有通用谱缓存形态，但卡片没有明确来源描述；本次未下载大数组、未证明来源/许可逐项或train重叠，不建议抢先整包接入。
- MoNA官方downloads中的Enveda-180全量仍约2.3GB MSP/2.6GB JSON；不是更小增量通道。官方train已含GNPS/MassBank/MoNA/MSnLib，先查新版本身份/条件增量，不整库重复拉取。
- [Enveda公开处理代码](https://github.com/enveda/enveda-180)可以审查adduct和预处理来源，但不是一个可直接恢复任意缺失谱的小下载包。原发布还含CCS/RT，竞赛query没有相应输入时不能直接作为匹配tie-breaker。

## 证据

全部位于`reports/external_reference_increment_20261107_pm/`：Zenodo原元数据/versions；Kaggle公开卡片和文件清单；mirror README/manifest；footer range回执、55KB footer-only snapshot和独立schema JSON。没有全库或峰值内容的下载；footer-only文件不能拿来实际读取数据页。
