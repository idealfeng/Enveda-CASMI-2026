# 新公开神经基线审查包

日期：2026-11-06。只完成本地prepare及限定LOTUS小文件下载；没有模型运行、Kaggle push/Save&Run或比赛提交。

## 优先入口

`tri_v30/smoke_review`是优先的完整12查询云端部署检查入口。其`notebook.ipynb`只将原V30的`COMMIT_MODE='fast'`改成`'smoke'`，其他代码保持相同；`patch_receipt.json`保留原始/运行副本SHA。原始V30逐字节副本仍在`tri_v30/notebook.ipynb`，不能把其fast commit生成的dummy CSV当作12查询模型运行。

建议新私有Notebook ID为`stormseye/casmi26-public-tri-v30`，与原0.479锚点不同。元数据显式请求核心6历史版本、bgunshui v2/v4 V1和LOTUS V2，关闭互联网、请求T4、保留原镜像digest。这里的请求不代表服务器实际挂载/设备已验证。

`hardened_v1`为备选；原始源码本身就是smoke模式，所以其`smoke_review/notebook.ipynb`与原始源码逐字节相同。建议新ID为`stormseye/casmi26-n480-public-v2`。

## 已固定的文件

- 两份原始Notebook、上游原始metadata、八个经源码声明SHA验证的helper、59-cell frozen baseline均保留；两个source的frozen SHA都是`d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88`。
- `common_local_asset_manifest.json`复制既有447项记录SHA清单；本次逐项检查存在/尺寸，没有重读全部大数组。六个固定dataset版本在两份metadata中显式列出。
- 新模型`review.json`内含完整8-file bundle manifest，逐文件fresh SHA已核对；Saner代码依赖副本与bgunshui原生数据来源分开标记。
- LOTUS V2两文件共6,995,305 bytes已到`assets/kaggle/qwertykeypadapple/casmi26-lotus-candidates/v2`，逐文件receipt和`DOWNLOAD_MANIFEST.json`绑定来源/版本/尺寸/SHA。Parquet为149,983行，具备`smiles, inchikey14, formula, monoisotopic_mass, source`列；schema检查在`input_metadata/lotus_schema_check.json`。

## 附件决策

Hardened旧的`deleted/142141665` kernel source已从建议metadata移除，改挂新公开`bgunshui/casmi26-scorer-v2-model/1`。这提供公开依赖补齐路径，但不证明等于当年private checkpoint的每个字节。Hardened对v2使用public配置；当前public/v2配置不同项仅训练时长、epochs和output等，推断配置相同。

V30中的LOTUS不仅填空槽，还扩展NP membership prior，因此完整V30需要它，不能把缺文件后静默skip称作完整复现。包内已无已知缺失必要文件。

上游附加`sanpier/catalogue-experiment-saner`未被两份推断源码引用，建议metadata不附。单独`metric/rdkit-2026-3-3-wheel`也无需重复附加：核心attributed V9本身提供cp310/311/312/313轮子。本地已有cp312；旧云端V2挂载库存也记录cp313。正式新运行仍需检查bootstrap实际加载2026.03.3，正向模拟器继续独立2025.03.6环境。

## 运行前和产物验收门

1. 在独立cloudstage复制所选`smoke_review`，追加单独observer/补丁回执，不改这些原始快照。先做新的target不存在/owner/private/offline检查，不覆盖0.479锚点。
2. 要求public、v2、v4 checkpoint SHA分别为`44436b2d...9642`、`c08d2101...ff46`、`10565a0d...ec51`，实际三路不同，v4配置width256。上游有`_find_bundle_safe`绕过public pin、找不到专用模型后找任意config、找不到后复用base以及失败后复用旧特征等fallback；成功写CSV本身不代表三路都运行。
3. 检查`neural_public/v2/v4.parquet`的同一批active12查询/候选索引完全一致，全部neural_ok且有限，候选和新模型覆盖未缺失；再核实outsider三路实际参与情况和最终融合链。
4. 12查询计算＋388行可见占位是部署检查，不是隐藏400预测或Public Score。只在新代码版本检查通过后再考虑正式比赛代码提交。

## 本地最短路径建议

GPU推断用WSL/Python3.12并source `scripts/linux_env.sh`。若复用旧本地runner，需要重新核对外层cell映射：新source配置/神经阶段不在原V56相同cell索引，不能无审核套用原adapter。INPUT视图里供`Path.rglob('final_model.pt')`发现的public/v2/v4模型目录应是真实目录及叶文件symlink，不能只对父目录做symlink；Python3.12 rglob不递归目录symlink。当前最短、改动最少的完整12查询检查是上述Kaggle private offline smoke副本。

## 证据边界

当前准备包没有重现0.480/0.481/0.482。V30作者个人best不能自动归给当前版本，新增bgunshui权重许可卡仍Unknown；LOTUS卡和README宣称CC0来源，本包保留声明但不额外推导比赛资格。LOTUS `inchikey14`由作者清理流程产生，不代表所有结构已按官方互变异构规范化身份去重，正式最终CSV仍须用官方metric口径验证。
