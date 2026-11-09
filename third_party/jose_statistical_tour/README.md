# José Statistical Tour：源码归档与审查

2026-11-04 从 [Kaggle 原页](https://www.kaggle.com/code/josefreitasalvesneto/casmi-2026-a-complete-statistical-tour) 的公开 pull API 获取 V3。源码 SHA-256：`ec4dc4f169d483cec5c8ca808f6e464f09ab0633abd0c4cf044a8434783a1a6c`。API 原文、metadata、下载回执及便于阅读的源码文本均保留在本目录。未执行 Notebook，未下载新数据或依赖。

值得参考：按来源库分析仪器/化学空间差异、流式读取峰数组、强度阈值扫描、碰撞能量缺失处理、多谱按分子聚合、按库分析质量精度。它是 EDA 与简单检索实验，不是新增强预测模型。

## 不能照搬的结论

- V3 的 markdown cells 0、55、63 将下载的 dummy test 与 Public LB 混淆，进而建议忽略 Public LB。[主办 David Healey 的澄清](https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/741404)明确：Public LB 使用隐藏测试的 public split。占位文件来自训练集不能推出榜分也是训练自匹配。
- 文中 train 2,539,575 / np-examples 1,151，与本地当前 2,539,608 / 1,184 不一致。具体统计须在当前数据重算；不据此推断隐藏测试分布。
- 1% 强度阈值是候选实验配置，不能凭该 EDA 就替换现有清洗阈值或认定所有弱峰无信息。
- Class 2 要排除目标的参考谱；删除全部相同 scaffold 的近邻属于更强的结构外推压力测试，单列报告，不称为唯一有效的 Class 2 验证。
- 其约 0.91 是作者特定 Class 1 检索实验的自报值，不是正式榜分，也不是所有模型必须跨过的统一门槛。
- 代码中的原始 inchikey14 分组应升级到本项目的官方 RDKit 2026.03.3 评分身份；官方数据说明允许的质量、加合物范围不由 dummy test 决定。

Kaggle 页声明 Notebook 为 Apache-2.0；外部数据许可独立核查。当前仅保留源码用于参考，后续取有用的统计方法，先不完整重跑它的图表或检索实验。
