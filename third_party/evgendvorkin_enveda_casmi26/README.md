# evgendvorkin / Enveda CASMI 2026：V27 原始源码

已从 [原始 Notebook](https://www.kaggle.com/code/evgendvorkin/enveda-casmi-2026/notebook) 的公开 API 下载当前 V27，下载日期为2026-11-04。页面浏览工具不能读取正文；代码结论来自下载的实际源码。

- `source.ipynb`：未改动的完整原始 Notebook，SHA-256 `10c2c7e3e6bb33c34bafbe3ffd9d85cb4b1aa56f323ebba48b3674b3d69f9bca`。
- `metadata.json`、`api_response.json`、`download_receipt.json`：版本、原始API响应与来源回执。
- `cells/`：按单元拆分的可读源码/说明；`embedded/`：静态提取的 Engine 2、PubChem 等内嵌源字符串。
- `source_audit.json`：语法、逐文件哈希、依赖和本地 fold 权重可用性检查。仅使用 AST 读取，没有执行上游代码。

## 与现有基线的关系

V27 仍属于现有 Ahmed / E006 / prvsiyan 多引擎骨干：谱库、analog、指纹模型、树排序、PubChem、ICEBERG/GLACIER、N1与官方identity融合。它包含751张外部参考谱扩展、fragment gap、window40及Engine 2 rank2 overlay。不能当作完全独立的新模型等权投票。

值得后续单独测的差异：

1. PubChem通道加载全部五个 fold-safe FPNet，源码规则是 `z_AB + 0.5 * mean(z_fold0..z_fold4)`。当前 Flex V56 使用的相关增强主要是 fold0；五折集成可能提供增量，但必须在同一候选集与明确训练排除身份上验证。
2. 在原有五个 PubChem 插入位置之外，追加第24名的第六个位置。这个策略改变候选分配，不宜与神经集成一起改后再归因。
3. 本份 V27 未挂载 Saner 模型，不包含 Flex 的同一 Saner最终神经层，不能视为 Flex V56 的全量替代。

## 当前边界

- 原脚本需要 Python3.12、主RDKit2026.03.3、隔离模拟器RDKit2025.03.6，GPU preflight限制T4；本机运行仍需适配。
- 仍区分12分子可见占位检查与隐藏重跑，源码下载不代表完成复现或获得榜分。
- 目前只下载源码和元数据。五折权重中本地已有fold0，fold1–4尚未下载；不能删掉缺失权重后声称复现该集成。
- 五折模型平均不等于无泄漏OOF：一个普通训练身份即使被model k留出，仍可能被另外四个模型训练过。评估训练身份的未见泛化时，只能使用对应未见组件或确有全模型排除证据的查询；不能用五折平均在本地训练样本上得高分后当作独立验证。
- 页面搜索快照显示过其他历史版本的成绩，不用于给当前V27标注榜分。源码中的旧分数注释也不是本机结果。
- API未给出明确的Notebook整体许可字段；保留原作者署名，输入代码、权重和数据按各自条款审查。

现阶段先完成已启动的验证台与Flex/V43对照，再按需把五折神经集成和rank24候选分配拆成独立消融，不重复下载整个依赖集合。
