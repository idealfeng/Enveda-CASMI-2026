# E006 V1 上游排序对照

已通过 Kaggle 单文件输出 API 匿名取得 `submission.csv`，明确请求 `versionNumber=1`。没有下载整个 output 数据包。

- `canqiang_e006_v1_submission.csv`：上游原始字节，17,224 字节、400 行，SHA256 `a5f021a6d43963eb681a478d2e356478e19c068b02e68d060084d5bd453f1eab`。
- 该哈希与固定 GitHub 镜像中的历史 `source_preview_comparison.json` 和 `platform_acceptance.json` 一致，绑定到已保存的 E006 V1 源码。
- `canqiang_e006_v1_active12.csv`：按原源码的 `SMOKE_N=12`、可见测试分子 ID 排序规则抽取的 12 行实算排序，每行 25 个候选。其余 388 行属于上游预览占位。
- 本地可见测试的 spectrum ID 签名与原源码完全一致：`654e030e4173780e945252b4a5adf70b`。
- 来源、版本、哈希、ID 和抽取方式分别记录在 `download_receipt.json`、`active12_receipt.json`。

这份参考可核对本地结果的 top1、候选集合和完整顺序，不提供真实标签，也不能用于估计隐藏测试成绩。
