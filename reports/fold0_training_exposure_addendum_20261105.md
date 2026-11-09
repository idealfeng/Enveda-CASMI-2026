# fold0 训练接触边界补充 — 2026-11-05

32 分子实验应称为 **query-spectrum/positive-identity exclusion diagnostic**。已经检查查询身份的谱和正标签排除，并排除 Saner 已知 checkpoint-selection query/decoy；没有建立两个模型都 selection-unseen 或所有结构接触均被排除的结论。

## checkpoint 保存与终止规则

本地精确资产为 `dmitriigluzdov/casmi26-fold-safe-fpnet` V5，checkpoint SHA `ddf6eaaa8e541a16e3f0357ed30f0346e529054f75d5619aedb6024dcb1bd7f0`。只读检查 checkpoint ZIP 内 `data.pkl` 的 opcode，未实例化模型或读取 tensor storage，得到 `step=82855`、`hours=5.0`、`max_steps=1000000000`、`eval_every=5000`、`eval_groups=3000`、`seed=0`、`holdout=hold,np`。

公开 `train_fpnet.py` 第 128 行按时间/步数进度终止，第 155 行为非有限 loss 异常停；160–168 行监测 hold/NP/train 指标，周期保存 last、结尾保存 final。源码没有按验证指标挑选 best 或 early-stop 的分支。元数据与时间预算终点相符，但不足排除发布者人工挑 recipe、训练时长或模型版本；精确历史 checkpoint 选择过程仍未完全重建。

## 监测集重建

按公开 `eval_groups()` 使用完整谱 metadata、sid→pool 映射、公开 split，按 `(sid, mode)` 排序，依照固定 RNG seed 12345 顺序抽 hold、np、train，每组最多 3,000 个结构—极性组。得到 hold 3,000 组、NP 499 组、train 3,000 组。当前 32 个实验身份中 9 个与这些监测身份相交：

- cross：FXQWNOQBKFDNLT、QEMNCANMUTYZIZ、HIQKXJJFHLCCFB、ZGNUKVOCLXSERM、BNSLBDHDDFTTMY、RMLDUGFLFJVZGE。
- NP：GMBQZIIUCVWOCD、HELXLJCILKEWJH、IEDVJHCEMCRBQM。

这是公开 recipe 下的确定性重建，未证明历史执行中这些组的每一张谱都曾被监测，也不是“监测了便直接梯度泄漏”的判断。它足以说明无法把本实验整体称为没有模型选择接触的独立测试。

## 负例结构池

`casmi/traindata.py` 第 41–43 行的 holdout gate 过滤训练谱/正样本；104–120 行的 `negatives()` 从全候选池质量窗抽样，空/小窗还混入全池随机负例，没有移除 hold/NP 的池条目。`train_fpnet.py` 第 139–147 行把这些负例指纹放入 contrastive ranking loss。

因此支持的排除对象是查询谱及正标签，不是所有结构身份指纹。特定 32 个结构实际是否在历史 minibatch 被采作负例无法由当前 artifact 确认，应记录 unknown。数据库候选作为负例是否符合某个验证定义，应由该实验事先明确；不能将当前结果宣传为任意定义下的完全未见结构性能。

本补充不改变已经冻结或评分的实验文件。原始 official-score 复核和候选集一致性仍成立；其统计及归属解释需要携带以上限制。
