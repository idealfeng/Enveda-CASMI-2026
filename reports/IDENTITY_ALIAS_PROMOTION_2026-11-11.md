# 第五分支：仅恢复被旧身份guard拦下的已有候选

实现文件：`scripts/identity_alias_promotion_20261111.py`。

冻结SHA：`44b1964b9298a794bb303f3ce579c8d06ef8b8047f078fe868bed0154d607c02`。

该模块追加在原0.488的全部33个cell之后，原预测流程、两库匹配和身份guard照常执行。本模块不读取新谱、不重新打分、不增加候选、不修改中性质量或adduct判断。借鉴的是公开方案中的“身份已存在时移动原列表代表”机制；公开标题0.500不作为本分支的已验证成绩。

仅在以下条件同时成立时可操作一个query：

1. 原`external_overlay_runtime.json`明确记录`validity_guard_preserved_control=True`。
2. 原实际最佳匹配通过原cosine≥0.80、匹配峰≥4门槛，且标志与记录的分数一致。
3. 参考SMILES能得到官方RDKit 2026.03.3去立体/tautomer规范身份。
4. 此身份在外库前0.482列表和输入0.488列表各出现恰好一次。

操作为把输入0.488列表中现有的native SMILES移到第一位；身份已经在首位则不动。无效参考、阈值不足、原guard未拦截、列表外结构都不产生新提升。每个query的完整SMILES多重集、候选数、顺序中的其他元素均保持。

绑定先于任何操作：输入0.488 CSV必须等于原`EXTERNAL_OVERLAY_AUDIT.csv_sha256`；原运行JSON必须等于其`runtime_report_sha256`；外库前control必须同时等于原audit和原runtime的control指纹。进一步逐query重建原raw-SMILES proposal、合法性guard和旧最终输出，确保“被拦截”不是一个未经核验的标志。原CSV/schema/官方身份也须有效。

新审计从原实际匹配重新计算可操作集合和最终CSV；报告`eligible_queries`与`changed_queries`分别计数。原guard已确认且接受的AB输出不受本模块影响。全局绑定错误删除最终CSV并保留`submission_alias_promotion_control.csv`输入副本；fast可见路径只核验绑定并原样保留CSV。

26/26检查通过，证据：`runs/identity_alias_promotion_canary_20261111/verification.json`。包括：

- 原先rank2已有同身份、不同SMILES的候选升到首位，原生SMILES多重集保持。
- 原已首选、非法参考、列表外有效AB候选、低分匹配保持预期行为。
- 原已保存真实两库self-match回执的fast/hidden路径检查通过。
- 原运行JSON哈希、原control、输入AB、分数/门槛矛盾、模块指纹和越界重排均被拒绝。

没有GPU、训练、新参考重评分或Kaggle写入。这些验证用于证明接口和因果范围，不代表隐藏榜收益。精确staged入口还需重放原0.488最后一个cell再调用本模块，以测试真实被拦alias位于第二位的正分支。
