# 11/16晚轮公开源码与附件核查

本轮按官方API读取scoreDescending与dateRun各100条；只下载7份公开Notebook源码，未执行外来源码、未下载模型权重、未提交。所有新产物在D。对照为我们的58156482/.488；FIORA58435031的正式状态由主控单独读回。

## 当前最可复现的更高分候选：公开.492网络版

- [Mathlete V7](https://www.kaggle.com/code/mathleteutd/casmi26-0-492-test-set-network-rerank)：首段明确报告网络LAM .25→.35在Public取得.492，并列0/.15/.25/.35/.50分别.487/.487/.488/.492/.484。源码与完整metadata已存本目录。
- [Alex V2](https://www.kaggle.com/code/alexchilton/casmi26-0-492-what-moved-the-board-59-arms)：首段明确报告复制[Rogers L4 V1](https://www.kaggle.com/code/rogersjohnson/casmi26-l4-lam035)后，本人账户得.492，给出提交ref58380172。这是比单纯标题更具体的作者复验声明。
- 公开列表API的public_score/best_score仍均null，因此本报告把.492标为**作者声明及公开复验记录**，不冒充我们已取得的榜分。真正复现分需主控提交后官方读回。
- 3份代码各不完全相同，不能只凭同标题当逐行等价；机制/代码差异由另一独审负责。本扫描保留每份原字节与来源版本，供明确选择一个父版。

复现依赖版本在[roger_dataset_versions.json](roger_dataset_versions.json)：MassBank1、Saner1、fold-safe FPnet5、NP knowledge10、NP panel10、popularity13、attributed-v4g9、Takumu2、catalogue1、official RDKit1，全部可读public/Ready。它们是当前dataset view，不证明上游历史运行挂载的具体版本。

V80训练Notebook当前真正版本是**1**，名字v80不是版本80；[完整metadata](popwenman__casmi26-scorer-train-v80/api_metadata_full.json)、[37项输出清单](popwenman__casmi26-scorer-train-v80/output_inventory.json)已核。可冻结`popwenman/casmi26-scorer-train-v80/1`，SDK明确支持kernel_sources的`owner/slug/version`格式。`casmi_spectrum_model_ours_v80/final_model.pt`是现冠军v2重复权重，不能拿它当新的独立模型；`kit_staged/final_model.pt`则是原Saner副本，不能误取。

## .494标题不能完整复现：现附件是demo替代权重

[Helios V4](https://www.kaggle.com/code/heliosli/casmi26-0-494-public-demo)已从旧.489的空附件变成可读公开附件，但以下当前V2数据集的**作者description明确说明**：原比赛训练权重不包含，私有参数用初始化demo权重替代，joint ranker为synthetic fit，当前包不是.494的复现包、没有声称榜分。

| 数据集 | 当前版本 | 总字节 | 核验 |
| --- | ---: | ---: | --- |
| heliosli/casmi26-rr-v3 | 2 | 215790052 | 12项文件、公开，description明确demo |
| heliosli/casmi26-frigid-e1 | 2 | 1763756610 | 首100项文件，仍有后页，description明确demo |
| heliosli/casmi26-joint-ranker | 2 | 17809 | 5项文件，description明确synthetic/demo |
| heliosli/casmi26-pxv2-deploy | 2 | 37619346 | 7项文件，description明确demo |
| heliosli/casmi26-rt-np | 2 | 56520478 | 6项文件，description明确demo |
| heliosli/casmi26-denovo-v3 | 1 | 161517657 | 4项文件、description为空，不能据此判性能 |

完整dataset view/许可/版本说明与文件表见[dependency_inventory_v2/](dependency_inventory_v2/)。不下载这些GB级demo包来冒充.494复现。

旧`heliosli/casmi26-m5`直接files/view403，但另一独审发现新slug `casmi26-m5-v2d`、`casmi26-j2-judge`等并进一步审查，**旧slug403不能扩大成所有M5都不可读**。以该独审报告及新dataset description为准。

首次用`dataset_status()`批量查询时，连已知public的official RDKit附件也返回404；此接口不适合判断他人公开dataset的存在。本轮随后用`dataset_list_files()`与`get_dataset()`实际读通，保留首轮失败及更正证据，不把首轮404写成附件不可用。

## 本轮源码指纹

| 作者/方案 | 当前版本 | 源码SHA256 |
| --- | ---: | --- |
| Helios .494 public demo | 4 | `5f09d769677e2d50caf3806f4e64d45fcc82b6785ed228d40e53648a45e36b0d` |
| Mathlete .492 | 7 | `75fdf3f700b65d880952292755d713035f04d65a4431f98b022fb6bef652671e` |
| Alex .492 59 arms | 2 | `fac7dca7b3bab658b92113e27dcd914140c5f00219a5be607adb1306aa78c9e9` |
| Rogers L4 lam035 | 1 | `51c32f200c265fff08bfa4a9841cb6345d1f56515dcd72e254df8da53e07ae99` |
| zz3 peaks-to-structures-v2 | 60 | `d7cdbf2eca1e68f199cf6c4022ac948f3e8ee4b122a547909e4892ecbcdd1145` |
| Ozertuu apex-gold-486 | 2 | `de709060dbdded5c61c3580f99529c1ddc6071914a0096e070563605c15bcc75` |
| Aryan GPU FP+fragmentation ranker | 1 | `117a1a4e0c551b753f00ca823fa959bf2d351ba020591a0cd5925e5f33fcdbc1` |

列表last_run_time显示上述新公开条目于11/15–16更新；get_kernel metadata的同名日期有已知异常，不能覆盖列表实际时间来判断新旧。源码下载版本与SHA采用实际get_kernel返回值。

建议主控优先选择.492公开、完整且已有他人复验声明的一版做我们自己的真复现，再单因素优化并分开提交；.494保留架构信息，不能用demo参数消耗正式额度并声称同配方。
