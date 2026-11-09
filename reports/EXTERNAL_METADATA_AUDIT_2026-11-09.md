# 2026-11-09 两新增参考库：有界元数据审计

实际审计耗时 55.93 秒。没有新下载、网络写入、GPU、官方 train 全文扫描或隐藏查询/标签读取；仅复用已存在结构目录及原8,192条只读身份缓存。

## 原始发布者身份的覆盖

下表 raw key 是发布者 InChIKey 前14位；**不能直接当比赛的去立体/tautomer规范评分身份，也不能把表中差集当已证实新增结构。**

| 库 | 元数据可用谱行 | 不同raw key | 与train raw key重叠 | train raw key外 | 精确SMILES重叠 |
|---|---:|---:|---:|---:|---:|
| A | 200724 | 151338 | 6414 | 144924 | 3908 |
| B | 139096 | 18265 | 10350 | 7915 | 8360 |

A/B raw-key交集 1998。A为Takumu extlib v2全部metadata；B为MassBank v1去历史CASMI flag和缺SMILES后的metadata，未加最少3峰过滤，故不是此前实际overlay加载引用数。

## 官方评分身份采样

结构目录 277566 个raw-key/SMILES对，fresh SHA与此前已逐对核对官方train的目录相符：True。其中 canonical_checked=True 的对数 5987；已检查不同SMILES 5987；官方身份 5830。是否覆盖全部训练SMILES：False。未检查行的identity字段不被当作规范化证据。

从每库train raw-key之外按固定hash最多抽1024条，本次实际规范化/查缓存 2048 条（上限2048）。可确证train成员 1；无效身份 0；在完整train中证明缺席 0；未在已检查子集找到、但不能证明train缺席 2047。精确SMILES已在train的采样条数 0。

因此，这次不能声称整库提供了多少官方训练集外新结构；也没有评估PubChem/COCONUT候选目录增量或隐藏覆盖。即使结构早已在train，不同仪器/能量的真实参考谱仍可能帮助直接匹配，但收益必须由独立验证及真实提交判定。

## 条件元信息

- A：严格属于官方10种adduct的谱 197449；仅将 `[M+HCOO]-` 对应 `[M+FA-H]-` 后为 197601；仪器字符串含tims的谱 0。
  前10 adduct：`[["[M+H]+", 103493], ["[M+NH4]+", 43814], ["[M+Na]+", 24601], ["[M+H-H2O]+", 21985], ["[M-H]-", 2621], ["[M-2H2O+H]+", 1748], ["[M+K]+", 674], ["[M+CH2O2-H]-", 382], ["[M+CH3COOH-H]-", 331], ["[M+CH3COO]-", 168]]`（全分布见JSON）
  前8仪器：`[["LC-ESI-Orbitrap", 196207], ["LC-ESI-qTof", 1272], ["ESI-Orbitrap", 706], ["LC-ESI-QTOF", 645], ["", 359], ["LC-ESI-QFT", 309], ["ESI-qTof", 183], ["LC-ESI-ITFT", 168]]`
- B：严格属于官方10种adduct的谱 105509；仅将 `[M+HCOO]-` 对应 `[M+FA-H]-` 后为 106704；仪器字符串含tims的谱 0。
  前10 adduct：`[["[M+H]+", 70339], ["[M-H]-", 33493], ["None", 26540], ["[M]+", 2669], ["[M+HCOO]-", 1195], ["[M+Na]+", 1137], ["[M+CH3COO]-", 604], ["[M+CH3COOH-H]-", 590], ["[M+CH3COO]-/[M-CH3]-", 564], ["[M+NH4]+", 338]]`（全分布见JSON）
  前8仪器：`[["LC-ESI-QTOF", 53546], ["LC-ESI-QFT", 25568], ["LC-ESI-ITFT", 22677], ["EI-B", 11202], ["LC-ESI-QQ", 9615], ["ESI-QTOF", 3849], ["LC-ESI-Q", 2738], ["LC-ESI-QQQ", 1956]]`

这些是metadata可用性，不是同仪器训练外验证集；当前公开外库overlay只按离子模式及precursor匹配，并没有按adduct或CE约束。

## 重复谱与来源筛查

有界检查A前 2048 行与B前 2048 条非CASMI记录。严格signature为排序后有限正峰的float32 m/z、basepeak归一化float32强度、原adduct、小写mode和6位小数precursor；缺失precursor跳过：{'B_missing_precursor': 53}。重复group 21，重复额外行 22，跨库重复group 0。这是小样本严格字节重复下界，未比对官方train谱，也不是全库谱去重结论。

B的source/source_institution/spectrum_id/license中含NIST字符串的行数：0。A没有逐谱source/license列。字符串未命中不能证明无NIST来源，当前许可判断仍引用主办方允许公开GNPS/MassBank/MoNA一般按发布使用的明确回复（749217），并不能由本元数据审计替代来源证明。

未改变当前优化配方、模型、验证切分或已冻结提交资产。逐条身份采样与完整计数保存在同名JSON。
