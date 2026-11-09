# Prvsiyan V43 上游排序对照

仅通过 Kaggle 单文件输出 API 下载了明确请求 `versionNumber=43` 的 `submission.csv`。输出存储脚本版本 ID **360497306** 与已下载 V43 源码 manifest 一致；不存在的版本 `999999` 返回 404，接口未忽略版本参数。

- `prvsiyan_v43_submission.csv`：原始 17,303 字节、400 行，SHA256 `5c098f153b748a651757c5aea2f078a7d1d82cfb3ae89bd656c5cc81a203ce76`。
- `prvsiyan_v43_active12.csv`：12 个实际计算分子的完整候选顺序，每个 25 个候选，其余 388 行为 `CCO` 预览占位。
- 12 个 ID 对应原源码的排序后前 12 个可见测试分子；可见测试签名匹配源码中的 `654e030e4173780e945252b4a5adf70b`。
- `download_receipt.json` 绑定源 notebook SHA、源脚本版本、下载地址和两份 CSV 哈希；`download_probe_receipt.json` 记录版本探测。

这份输出可用于 top1、候选集合及完整顺序对照，不包含真实标签或隐藏测试预测。没有下载完整 outputs 或缓存。
