# 11月7日下午：真实榜分归因与下一轮五版

核查：北京时间2026-11-07 14:39，直接只读查询四个固定提交编号。未训练、未提交、未读取或评价锁定250。截图中的0.481/第131名是用户当前观察；API独立确认了分数，未据截图推断未来银线或最终名次。

## 已有真实结果

| 配方 | 提交 | Public | 相对原V56 |
| --- | --- | ---: | ---: |
| 原始Flex V56 | 58021256 | 0.479 | — |
| 原V56＋双神经 | 58063780 | 0.480 | +0.001 |
| 原V56＋三神经 | 58063822 | 0.475 | −0.004 |
| 公开MASS-only整套配方 | 58063883 | **0.481** | +0.002 |
| 原V56＋激进学习RR | 58063870 | 0.436 | −0.043 |
| 较早完整tri V30 | 58051406 | 0.475 | −0.004 |

上述四条新提交均COMPLETE、无error，原始读回证据在 `reports/aggressive_batch_20261107/<branch>/score.json`。数值是服务器显示的三位小数，不能反推逐分子变化或把千分位差异视为已证稳定泛化。

## 当前能归因到哪里

1. **双模型有正向实测。** dual-only保留原V56检索、物理层及弱先验，新增的是public/v2神经组合，因此这一组合在此版本上的显示增益为+0.001。仍不能从一个Public结果承诺未来稳定上涨。
2. **当前v4组合应暂时停用。** dual的权重是0.5public/0.5v2，tri是0.5public/0.25v2/0.25v4。可识别的比较是“用v4替代一半v2份额”损失0.005，不是保持原双模型再增加一个模型。两套不同外层配方的tri均0.475，是继续投入该固定组合的负证据，不证明v4在所有权重/分布上都无效。
3. **0.481来自整套MASS配方，不是已经证明单独由质量修正贡献。** 相对dual-only，整套MASS还提高SPEC/NP先验、改变library gate、引入LOTUS，并且outsider使用v2单模型而非dual融合。虽然8个核心helper的MODULE_SHA256和public MODEL_PINS一致，这些外层差异仍混杂；0.481−0.480的+0.001不能全算给MASS。
4. **强学习RR有明确的大幅负结果。** V56上alpha1.5、library gate0.95的102特征重排到0.436。应先停该强度/门槛的RR分支，不应因可见fixture能运行就继续提高alpha或直接叠到0.481上。可能的训练分布失配、特征相关性或首选覆盖影响，目前只有假设，没有隐藏逐例证据。

当前可信主线是public/v2双神经与质量/来源先验配方；下一轮仍须通过真正不同的配置取得因果信息。

## 新V35不是旧MASS的别名

下午拉取的 `third_party/public_scan_zz3t3rn41__casmi26-peaks-to-structures-v2_20261107_pm/source.ipynb` 含实质新代码：更松的physical首选处理、outsider双模型、质量惩罚内联到merge、基于NP证据的首选promotion，以及在非强library查询中将4个outside候选强制插入rank8/14/20/24。

因此新V35 baseline必须取得我们自己的分数，不能直接继承旧MASS-only的0.481。把所有优化版放在同一V35底座上，比同时改变底座与参数更便于解释。V35还已覆盖完整10种官方adduct，不能再次以“补齐脱水3类”作为一条无实际变化的提交。

## 最终建议的五版

| 版本 | 相对V35的唯一方向 | 具体patch | 目的与限制 |
| --- | --- | --- | --- |
| 新公开V35 baseline | 原配方对照 | 不改评分代码/配置，仅工程绑定和观察器 | 测量新physical、promotion、outsider等整套更新的真实效果 |
| weak_prior | 文档先验回到V56强度 | config cell4：SPEC_W 0.10→0.05、NP_W 0.12→0.02、LIB_HIT_GATE 0.78→0.87，POP_W保持0.10 | 检验强来源先验是否压过谱学证据；三项合为一次“恢复旧先验配方”，不能归到单独NP_W |
| robust_mass | 每query中性质量从首谱改为多谱中位数 | merge cell18的nm_map构建，见下节 | 真实功能改动，避免输入行顺序决定质量惩罚；不重训、不新增候选 |
| v2_emphasis | 提高有正实测的v2份额 | 主候选和outside双模型四列均改为0.25public/0.75v2；neural_ok与候选/覆盖规则不变 | 对已有正向权重做一个固定剂量检验，不重启v4；观察器必须使用新权重验算 |
| no_forced_outsiders | 保留原top25的召回与名次 | 只关闭merge cell18的rank8/14/20/24强插块；保留原有vacant补位 | V35强插最多挤走原top25末尾4个候选；若新outside不是正确结构可能净损MRR。该版既可能涨分也可能降低真实召回，须看榜分 |

Root当前选择这五条合理。与其再投强RR，更值得测量V35的新outsider强插是否有害。纯MASS_OFF归因仍有价值，但可以放下一批：若V35本身掉分，先定位新promotion/强插；若其稳定上涨，再拆质量项的净贡献。

## robust_mass：源码证明与精确建议

当前V35 merge cell18:264–269首先读取 `effective_query_spectra.parquet` 的 `molecule_id,nm`，然后 `drop_duplicates('molecule_id')` 取首行；fallback从raw test同样先按mid取首谱，再计算nm。这确实不是每分子的中位数。

中性质量来源链：冻结pipeline cell39先读完整test，再执行 `te['nm']=chem.neutral_mass(每行precursor_mz,每行adduct)`；后续cell48仅另建 `_targets=te.groupby('molecule_id').nm.median()`，未改写te。固定 `export_evidence.py:40` 原样导出scope['te']，因此effective表里的nm仍是逐谱值。核心Engine2也自行使用多谱neutral-mass中位数，支持“不同谱独立估计再稳健聚合”的工程一致性。

优先patch建议：

```python
effective = pd.read_parquet(path, columns=['molecule_id', 'nm'])
effective['nm'] = pd.to_numeric(effective['nm'], errors='coerce')
effective = effective[np.isfinite(effective.nm) & (effective.nm > 50)]
nm_map = {str(mid): float(nm) for mid, nm in
          effective.groupby('molecule_id', sort=False).nm.median().items()}
```

保留现有chem.neutral_mass的精确常数和可支持adduct集合，只改变聚合。fallback对raw test全部谱先以原V35 `_ADD` 计算nm，再过滤有限/>50，最后groupby(mid).median；不要先drop_duplicates。还可只补nm_map缺失query，而不覆盖已存在有效中位数。

若Root采用“始终从raw test的10adduct重算中位数”，也是真改动，但与原effective路径相比还混入了mass常数的微小差异，必须在recipe写清。V35 `_ADD` 的 `[M-2H2O+H]+` 为−35.013853，原7-adduct配置不含它；不要无说明地同时改到另一个近似常数再称纯聚合消融。

此patch只作用于最终质量惩罚，不自动改变候选检索的mass窗口；不能把它报告成提高数据库召回。中位数可以抵抗单张异常谱，但无法消除所有谱共同的系统校准偏差。建议small fixture同时验证：首谱离群时取正确中位数、输入行重排不变、多个adduct恢复相同neutral mass、全无效nm安全不施罚。

## 护栏和后续方向

- weak_prior改变LIB_HIT_GATE时，V35 promotion、strong-library保护和强插适用范围也随之变化，报告须称“先验/门槛配方”，不能称纯tail NP ablation。
- no_forced_outsiders只关强插，不能简单 `OUTSIDER_FILL=False`，否则会连带关闭vacant backfill，产生不同实验。
- 观察器不能硬编码旧MASS条件：质量/权重/先验的expected值必须与每个新recipe一致，hidden阶段照常验证全量、实际模型及精确混合。
- 若V35新版融合仍只是小幅上涨，下一步考虑按library confidence区分路线、给outside候选质量门控后再救回，而非无门槛更早插入；旧逐谱CE支持率可作为另一个结构证据方向，暂未证明效果。
- 外谱库新增应先做结构/来源/近重复增量审计。即使公开mirror更大，训练重合记录本身不构成新信号；本轮不因数据量宣传挤掉已准备的五个清晰对照。

本报告只做归因与源码patch建议，未生成stage、未改排名、未提交、未读取锁定250或任何隐藏测试内容。
