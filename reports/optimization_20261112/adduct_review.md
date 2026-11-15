# 11/12 V18外库匹配版交付

分支 `adduct_extlib`；固定父版本为正式.488 / 58156482。保留冠军前32个cell完整对象，仅替换末尾外库cell；实际输入控制由原 `GUARDED_TAIL_AUDIT` 绑定外库前.482输出。未换模型、未改生成或训练。

- 公共来源：ozertuu V18，整Notebook SHA `54ad16b546964a1044f07aa5229cd7ee81145882d73a83fda061923e9254adcd`；提取原函数 SHA `8e1439c05d7721946ab21e08fec18b4d54d890d3188bf7ec111b32712c545624`。
- 原函数仅AST加入两处参考计数和一处实际best-match观察，匹配数学未改。中性质量12ppm+.002Da、adduct兼容、结构质量15ppm、cosine .8/至少4峰、原库.9保护。MassBank仍沿原public exact_mass±H假设，未混入另一前体纠偏。
- 公共proposal按其身份逻辑提升原生候选或加入外部结构，随后保留原official RDKit身份合法性guard；非法提议退回对应control。实际分数、质量门槛、身份选择、原始计数和最终CSV可由observer独立重构。
- 5份既有参考文件逐一检查大小/SHA/实际选择路径。fast_static明确不匹配；hidden路径要求两库均完整加载。全局失败删除最终CSV，保留控制文件；解压安装失败也保留preinstall控制。

## 真实入口核验

- [模块canary](adduct_module_canary.json)：16/16，通过fast与真实AB匹配，A=200724、B=124160，3合法hit、2首选变化，坏实际分数拒绝。
- [冻结末cell canary](adduct_stage_canary.json)：20/20，通过实际安装/fast/hidden与损坏payload失败保护；3hits、2首选变化；精确保留first32。
- 真实AB完整参考加载的小接口检查使用既有5查询selfmatch控制，不是produre1/2重跑，不计算MRR或声称收益，不运行GPU/完整上游MASS。

## 固定stage

`submission/optimization_20261112/adduct_extlib/branch_spec.json`可纳入根agent的部署manifest；本agent未进行Kaggle写入。

- Notebook SHA `da79811ad20e32ed6c68082d488785ff893793f6d5a5ec36f71dc5ebc74871af`，857325字节。
- Metadata SHA `297b379c80d2b591c0faac7d1cc97b8c71ee0eda7ffae74bdb3ed6a6010a2dd6`。
- Recipe SHA `b700e845e2eb850674c2d461498d6a991d6165e18bc66aab3e3d75e9c67a123f`。

结论限于新组件部署一致性；实榜效果由正式提交判定。固定stage与模块不要原地改写。
