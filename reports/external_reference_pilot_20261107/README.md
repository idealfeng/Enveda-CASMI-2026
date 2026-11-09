# Enveda-180外部参考：本轮实测与边界

本轮已经取得完整公开参考文件并推进到真实数据审计，但**尚未证明它们相对官方train有多少独立新增，也没有运行参考匹配或证明榜分收益**。用户侧当前日期为2026-11-08，所有产物在D盘。

## 已独立完成

- 固定公开数据集`egehseyinca/enveda180-casmi26-reference-ccby4/1`，来源Zenodo record 21346580，CC BY 4.0。
- 全部下载在`assets/kaggle/egehseyinca/enveda180-casmi26-reference-ccby4/v1/`。参考谱218,514,313字节，完整fresh SHA256为`37b8f37c5f5f536ed804d4d0456e20f183fa32388f30ae1c1712928471146069`；aliases116,885字节，完整fresh SHA256为`3ed2d8f086e51931798a34e241027de66cad76b929c0dba1d866f31f2b21e150`。均与发布者manifest一致。
- 实际读取5个元数据列，不读取峰数组。参考谱730,252行，166,777个发布者key，167,490个独特SMILES；H+554,650行/H−175,602行。
- 对3,720条aliases全部用官方RDKit2026.03.3去立体化、互变异构canonical、InChIKey14复算，得到3,717个身份，发布者key错配0。
- aliases中只有431个身份在这个H+/H−参考文件中出现，共1,600张相关谱（H+1,377、H−223）；这些相关参考行的SMILES也已复算，key错配0。其行号/身份/adduct/质量/signature已保存为`alias_related_reference_rows.parquet`，供后续只选择相关峰数据。
- 从当前官方train全部2,539,608行重新读取两窄列，确认其277,566对独特raw-key/SMILES与既有结构目录完全一致。没有假设该目录中的raw-key就是官方评分身份。
- 完整metadata/alias审计重跑20.31秒，详见`partial_audit.json`。

## 当前不能声称的结果

431个身份/1,600张谱是**发布者source-only目录关联的可审计范围**，不是本轮已独立证明的train外结构/谱数，更不是隐藏测试覆盖。独立train membership、PubChem/COCONUT覆盖、精确/近重复谱和匹配准确率尚未完成。

参考文件没有CE或instrument列；不能从同一结构多张谱伪造跨CE独立支持，也不能仅凭已知库来源恢复具体采集条件。

## 耗时止损及可续跑能力

完整train+reference合并445,722个独特SMILES。全表tautomer canonical首批8,192身份已持久化在`official_identity_cache.sqlite`；两个4,096批次之间31.85秒，约129 SMILES/秒。单纯线性推算全部约58分钟，且复杂分子有长尾。确认耗时后已停止该CPU作业，没有为了等全表拖延本轮反馈。

后续脚本默认只做已完成的metadata/alias小审计：

```bash
source scripts/linux_env.sh
.venv-linux/bin/python scripts/audit_external_reference_increment.py
```

显式选择完整身份审计时，默认每次只增加8,192个身份，SQLite可恢复；只有全部相关SMILES都完成才输出完整`audit.json`：

```bash
.venv-linux/bin/python scripts/audit_external_reference_increment.py --full-identity-audit --max-new-identities 8192
```

`--max-new-identities 0`才表示无身份数上限。每次重算fresh外部文件SHA并核对当前train独特目录，缓存绑定RDKit2026.03.3。该脚本不读取query/锁定留出真值、不读取峰列、不训练、不创建Notebook或提交。

不能用完整分子式直接筛掉潜在匹配以加速：官方InChIKey14省略部分质子化差异，现有`validation.metric`明确完整formula不是安全identity匹配gate。仅heavy composition预筛aliases仍留下158,382条train结构，不能描述成只需几千次canonical。

## 下一项有实质价值的工作

先完成431身份的官方train membership边界，并核对现有结构候选池是否已有这些身份。随后按same-adduct、窄质量窗做外部参考overlay，独立输出来源、参考数、相似度和时间。老身份的新条件补充与新身份召回分开量化；先排除重复采集/近重复，不将730k总谱重复计作新信息。

公开来源：[Zenodo固定记录](https://doi.org/10.5281/zenodo.21346580)、[公开派生数据](https://www.kaggle.com/datasets/egehseyinca/enveda180-casmi26-reference-ccby4)、[主办许可讨论](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/745148)。
