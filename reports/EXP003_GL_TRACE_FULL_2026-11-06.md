# EXP003：完整GL逐谱trace独立核验

2026-11-06，**passed，30/30项检查通过**。未读真值、未评价MRR、未预测锁定250。

- 原完整输入45query、3679候选、146谱逐字节复用，逐谱适用pair共12187；所有pair顺序、身份、谱元数据与输入一致，缺失/非有限0。
- 新旧聚合输出逐值完全一致，最大差0；逐字节相同：True，两者SHA `424ffecab17f571a858da452c27a6f1ce2dda64d01549b0854d1ce1c0b0c62d9`。
- 3679个候选均值由逐谱值独立重构，精确相等3679/3679，最大差0。
- upstream为ok，45/45query及3679/3679候选评分完成；CUDA、RDKit2025.03.6，预测/特征错误0。旧site marker未改，日志确认bootstrap no-op。

## 权重与配置绑定

实际CLI没有`--ckpt`覆盖，原loader读取`ckpt/glacier.pt`。fresh完整SHA `9192e4c2eeafe83317d5a2c2641e1fc4d68934488757a4faafeb66f2ab397a12` 与模型包MANIFEST及既有下载回执完全一致。模型配置来自该文件中的`hyper_parameters`，同一个完整文件SHA同时绑定权重和配置；loader随后strict加载state_dict。核验器未反序列化checkpoint或加载模型。

旧runtime inventory另有相同checkpoint路径、大小和首尾4MiB指纹，现已再次比对相同。需保留边界：旧runtime没有完整checkpoint SHA，当前trace header也未在加载时哈希权重；本次是运行后对实际默认文件与既有固定manifest/下载回执进行完整SHA补证，不能说runner pin本身证明了权重。

机器报告：`runs/exp003_gl_trace_full_20261106/full_trace_verification.json`。此结果允许后续只读导出一致性特征，不代表排序或榜分提高。
