# Flexonafft V56 上游排序对照

已通过 Kaggle 单文件输出 API 取得明确请求 `versionNumber=56` 的 `submission.csv`，存储脚本版本 ID 为 **364170882**。版本绑定经过两项检查：不存在的版本 `999999` 返回 404；另取 V61 单个小 CSV，得到不同存储 ID **364604504** 和不同内容哈希。因此 V56 文件没有被标成 latest。

- `flexonafft_v56_submission.csv`：原始 17,303 字节、400 行，SHA256 `d2027d8918d15b27fa271ba4961faa63c28fa7f4efbea0dd8069ecbfe6a5060b`。
- `flexonafft_v56_active12.csv`：12 个实际计算分子的完整候选顺序，每个 25 个候选，其余 388 行为 `CCO` 预览占位。
- 12 个 ID 与可见测试排序后前 12 个分子一致；可见测试签名匹配源码中的 `654e030e4173780e945252b4a5adf70b`。
- `flexonafft_v61_submission.csv`：仅用于版本接口对照，SHA256 `8eee78e5393a31490958b04257429bfff942fa4d8b3da81a847e50718d7c8b7b`，不能替代 V56 参考。
- `download_receipt.json` 绑定 V56 源 notebook SHA、输出来源及 CSV 哈希；`v61_control_receipt.json` 和 `download_probe_receipt.json` 保留版本区分证据。

这些文件可核对本地 top1、候选集合及完整顺序，不提供真实标签或隐藏测试预测。只下载了各约 17KB 的单个 CSV，没有下载完整 outputs 或缓存。
