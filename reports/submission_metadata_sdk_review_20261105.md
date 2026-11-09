# 提交草稿的本地 SDK 与资产回执复核

本地 Kaggle **2.2.5**、kagglesdk **0.1.38** 的源码支持草稿中的 GPU、断网、machine_shape 和 docker_image 字段。当前模板不是格式不受支持；但它也没有证明服务端会分配所需 GPU、接受历史 Docker digest，或挂载相同历史输入版本。本次没有调用服务、读取凭证或导入会自动认证的 `kaggle` 包。

机器可读证据、安装源码 SHA 和字段映射见 [review.json](submission_metadata_sdk_review_20261105/review.json)。只读取 D 盘已有的小源码、JSON 和文件标识，没有安装、下载或大数组内容读取。

## 模板字段

| 字段/当前值 | 已安装客户端的证据 | 仍需区分的边界 |
| --- | --- | --- |
| machine_shape=NvidiaTeslaT4 | CLI直接赋给ApiSaveKernelRequest.machine_shape；类型为str，SDK属性说明列出T4 | 具体资源分配、配额与设备数量由服务端决定；CLI的acc参数还会覆盖模板值 |
| enable_gpu=true | get_bool接受JSON布尔，随后传入request.enable_gpu | SDK将此字段标为deprecated并指向machine_shape，但仍接收它 |
| enable_internet=false、is_private=true | get_bool接受JSON布尔并逐项传入请求 | 尚未创建云端版本，不能声称云端状态已生效 |
| docker_image=原V56历史digest | CLI读取并传入字符串；与原Notebook metadata相同 | SDK说明要求服务端已知的Kaggle镜像；本地无可用镜像清单，当前账号可用性未知 |
| docker_image_pinning_type缺省 | 客户端允许None；显式值只允许original/latest | 本地源码没有证明服务端默认语义，当前不声称云环境固定，也不自动添加某个策略 |
| language=python、kernel_type=notebook | 两者均在客户端允许值中 | 只证明客户端格式兼容 |
| dataset_sources等来源字段 | CLI将来源列表传入request；当前8个dataset source都未带版本号 | 通用dataset验证器接受owner/dataset或额外第三段version，但本地不能确认save_kernel的服务端挂载语义，本次不拼接版本或更改附件 |

具体源码为 `.venv/Lib/site-packages/kaggle/api/kaggle_api_extended.py` 的 `kernels_push`、`get_bool`、`validate_dataset_string`，及 `.venv/Lib/site-packages/kagglesdk/kernels/types/kernels_api_service.py` 的 `ApiSaveKernelRequest`。客户端仅对Docker/machine字符串做类型处理，不提供服务端镜像、设备或访问权限验证。

## 明确可审查的模板建议

1. CLI固定读取 `kernel-metadata.json`。初次复核时只有保留 `YOUR_KAGGLE_USERNAME` 的通用模板；随后用户给出用户名 `stormseye`，root已在本地另存正式文件，见下方修正记录。通用 `.template.json` 继续保留占位符，云端运行状态仍未验证。
2. 初次复核时title带有“review draft”，其slug不等于id中的 `casmi26-flex-v56-baseline`，会触发SDK提示。已生成 [仅修改title的建议模板](submission_metadata_sdk_review_20261105/kernel-metadata.proposed.template.json)，title为 `CASMI26 Flex V56 baseline`。初次复核尚未应用该建议；随后root已对齐实际本地模板及生成脚本的title，见下方修正记录。来源、镜像、GPU和占位owner均未改。
3. Docker pinning策略仍待明确。源码只证明original/latest是本地允许值，不能据此判定当前digest或服务端默认行为。没有自动添加pinning type，也没有换镜像。
4. `kernels_push`会清除代码单元outputs、连接list形式的source并重新序列化Notebook。本地逐字节原稿SHA应继续保存，但未来不能只用上传后Notebook的整文件字节SHA判断模型源码是否改变；还应核对单元源码、嵌入模型pins与运行时manifest。

### 复核后的本地修正

2026-11-05北京时间14:41核对：实际模板已与上述仅改title的建议模板完全相同，title为 `CASMI26 Flex V56 baseline`，与固定id的slug一致；用户名占位符仍保留。当前模板SHA为 `c92dfc2f6654c96bd2dbc5cbecdefb4a93b7cde2ed3b4a9ad7949274d5cc3697`，生成脚本SHA为 `66f955606df1f661bd071fe6d39a580aeb07ad8213f00419d39268013e0f3968`。Notebook仍为原SHA `0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769`。

JSON保留初次复核字段与其历史SHA，并追加 `post_review_updates` / `post_review_current_state`，不将旧状态覆盖成已完成云端验证。Docker pinning type仍未指定；没有读取凭证或调用云端服务。

北京时间14:45追加核对：用户已提供用户名 `stormseye`，root用 `--username stormseye` 本地生成 `submission/flex_v56_review/kernel-metadata.json`，id为 `stormseye/casmi26-flex-v56-baseline`，title与slug对齐，私有、GPU、断网字段保留。它与通用模板仅owner不同，SHA为 `a37937e32eda0a0db37afcdb25fd235ee9a58db1ca67d7dba1e54d7520da32cb`；原Notebook未改。**用户名信息已具备**；实际鉴权、比赛访问和云端接受仍未检查，未读取凭证或调用服务。

## 补齐3个别名数组的来源 SHA

初次审查发现 `local_asset_manifest.json` 中447项均存在、记录尺寸均匹配，但只有444项直接带recorded_sha256。缺少目标旁回执的3项是：

| 数组 | 字节数 | 已核实的同文件源 |
| --- | ---: | --- |
| pc_mass.npy | 847,004,040 | ahmedberatozer/casmi26-pubchem-tier V1 |
| pc_off.npy | 847,004,048 | 同上 |
| pc_smiles.npy | 5,520,120,190 | 同上 |

三项均为真实NTFS hardlink，`os.path.samefile`逐项为true。源/目标文件尺寸、源回执bytes、已有alias pin和link receipt尺寸相同；源回执SHA、alias pin SHA及已有verified_hardlink记录SHA完全一致。没有读取这些约7.2GB数组的内容。

已修正 `scripts/prepare_submission_review.py`：只有满足上述同文件、尺寸、来源ref/version和多份SHA记录一致的别名，才从源回执继承SHA，并保存 `hash_evidence_source`、`same_file_verified_now=true`、`fresh_content_rehash=false`。重新生成的本地清单现为 **447/447存在、447/447记录尺寸匹配、447/447有来源SHA**：444项目标旁回执、3项同文件别名链。没有把这次元数据核查说成新的全内容rehash。

8个附加来源中，必要文件清单覆盖6组实际载荷；`casmi26-spectrum-model-long`和`catalogue-experiment-saner`仅作为原Notebook附加来源保留，不在447项必要载荷内。未下载它们的额外大模型，也未更改附件列表。

## 本地包的当前边界

原V56 Notebook副本与AST核对、必要文件/尺寸/回执来源、SDK字段复核、本地48例诊断和单独的许可/曝光记录已经具备。`preparation_report.json`和提交目录README已同步这些事实，并明确Docker pinning未证实。

仍不能宣称正式前工作全部完成：用户名及本地账号metadata已经具备，实际鉴权/比赛访问、云端附件版本与模型pins、所请求GPU/历史镜像、未改动原Notebook的正式全量分支与冷启动预算，尚需分别验证。原稿的12例检查与生成适配器的48例恢复诊断都不能替代隐藏输入或400例冷启动。主办745072的原文和具体外部资产范围也仍有已有许可报告记载的证据边界。

此次没有push、submit、获取凭证、模型推理、全量资产rehash；没有修改活跃pipeline三文件或资产载荷。Docker和附件版本仅记录待核验事项，没有擅自改变。
