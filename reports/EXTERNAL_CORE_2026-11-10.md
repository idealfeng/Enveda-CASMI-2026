# 五分支外库核心：实现与精确复现核验

核心源码：`scripts/external_library_variants_20261110.py`，SHA-256 `8c7b203f4fe90ccd95194f68cae5dd1afc7163119da84dd96c91e5f05df095e2`。

本模块直接运行已固定Alex原函数的AST，保留原读取顺序、float64峰处理、sqrt cosine、稳定质量排序、严格大于的best-match更新、raw-SMILES提议规则。观察节点仅暴露实际查询/得分/引用，路由source开关和经预先确定门槛的B前体替换。添加query adduct字段供Enveda使用，不改变AB匹配数学。

正式官方身份guard沿用固定旧helper。没有把等价SMILES“自动修正”成列表内代表；非法proposal仍整query回退，避免将未来身份感知优化混进来源消融。审计新增非法原因及引用身份是否已在control中，便于后续研究。

真实参考小试读取A的200,724条、B的124,160条usable引用，分别执行AB、A-only、B-only、AB可信B前体四种配置：

- AB实际最佳分数/匹配峰数/命中SMILES与旧可运行函数完全相同，最终CSV逐字节相同。
- 单库禁用来源的matching候选计数严格为0；另一来源计数与固定文件一致。
- 可信B前体分支只修改1,281条索引，其他记录原样回退，当前测试query输出无额外承诺。
- 强原库保护、缺查询、重复身份提议的行为保持；源码、查询、数据和实际分数到CSV均有绑定。

Enveda复合策略的真实RDKit身份夹具额外检查：AB确认当前首选即使未改变CSV，也属于有效命中并保护gap策略；AB无效别名不算有效命中；竞争版E同分保留AB；非法E保留AB结果。E在AB结果上升首，保留AB新增候选，例如AB `O;C;CC;CCC` 后由E的`N`胜出成为 `N;O;C;CC;CCC`；E若是AB新增候选的等价别名则保留AB。

E模块源文件、完整参考文件、查询准备、参考扫描行数、实际`query_best`与返回hit、same-adduct固定规则须同时满足审计。没有E适用query时，允许显式成功且不扫描；有适用query而无命中也允许，不以“没有涨分”或“没有命中”当运行异常。

最终证据：`runs/external_core_actual_canary_20261110_final1/verification.json`。四模式真实处理各约19–23秒，无GPU、训练或云端操作。早期无后缀canary是初稿检查，最终源冻结以final1为准。

这是接口、等价性与策略核验，使用真实参考自匹配小试，不是独立泛化或隐藏榜效果评价。Enveda全源实际检查与五个Notebook精确staged入口检查另由对应任务执行，不能用本报告替代。
