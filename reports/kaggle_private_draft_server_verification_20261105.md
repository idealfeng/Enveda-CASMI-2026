# 私有Kaggle草稿V1的只读回拉核验

已通过本机已安装Kaggle SDK认证，只读回拉 [stormseye/casmi26-flex-v56-baseline](https://www.kaggle.com/code/stormseye/casmi26-flex-v56-baseline) 的 **V1**。目标、私有状态、断网设置和原始单元源码核查均通过。这个结果验证了已保存的草稿及其服务端元数据，没有启动Notebook或提交比赛。

原始证据见 [核验JSON](kaggle_private_draft_server_verification_20261105.json)；源码和元数据保存于新的D盘目录 `reports/kaggle_private_draft_pull_20261105`。请求使用SDK的typed `GetKernel`，与 `kernels_pull` 相同的读取接口，明确指定 `version_label=v1`。没有调用save、run、push或submit接口，没有输出或保存Key、认证头或客户端对象。

## 已由服务端回报并核验的事实

| 项目 | 回拉结果 |
| --- | --- |
| ref / id | stormseye/casmi26-flex-v56-baseline / 142840437 |
| current_version_number | 1 |
| title | CASMI26 Flex V56 baseline |
| 类型与语言 | notebook / python |
| is_private | true |
| enable_internet | false |
| enable_gpu / enable_tpu | true / false |
| competition来源 | enveda-CASMI26-molecule-id-mass-spectra |
| dataset来源 | 6个必需来源均返回；没有两个未用可选附件 |
| docker_image | 与请求中的历史digest完全相同 |
| machine_shape | NvidiaTeslaT4，与请求相同 |

Docker digest的实际回报值为 `gcr.io/kaggle-private-byod/python@sha256:9a6bcfda6d03b2cd9aa347ee8c1bae62043328ed0f4afe9bda014e4f8bbf9435`。这证明服务端元数据保存并回报了该字符串；仍未验证实际分配容器是否能拉取、启动并使用它。`machine_shape`和GPU标志同样只验证到元数据层，没有实际设备或配额分配证明。

## 原始源码与单元语义

原始V56、cloud staging和回拉源码都包含 **24个单元：15个code、9个markdown**。逐单元顺序、类型、连接list/string并规范化换行后的source全部一致；15个代码单元的Python AST也全部一致。

判定没有依赖Notebook JSON排版、outputs、execution_count或其他保存元数据。此次回拉文件恰好连整文件SHA也与本地原稿相同：`0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769`，文件大小670,002字节；一般情况下SDK可能重新序列化，仍应以单元源码/AST及模型pins核对。

## 附件版本的证据边界

| 必需来源 | 创建请求中的版本 | GetKernel回报 |
| --- | ---: | --- |
| dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets | 9 | 只有未带版本的slug |
| dmitriigluzdov/casmi26-fold-safe-fpnet | 5 | 同上 |
| dmitriigluzdov/casmi26-natural-product-knowledge-table | 10 | 同上 |
| dmitriigluzdov/casmi26-natural-product-panel-benchmark | 10 | 同上 |
| dmitriigluzdov/casmi26-pubchem-popularity-prior | 13 | 同上 |
| sanpier/casmi-spectrum-model-v1 | 1 | 同上 |

六个来源身份均已由回拉确认，**具体六个版本号没有在此次SDK元数据中暴露**。创建请求使用 `owner/slug/version` 是请求证据，回拉slug不证明运行时实际挂载版本，也不能据此断言版本请求被忽略。还需要能暴露版本ID的服务端记录，或实际运行中核对挂载文件、model pins与manifest。

## 实际运行后才能确认的事项

- 所请求GPU、显存和会话配额能否实际分配，历史Docker容器能否启动。
- 附件真实挂载文件是否与本地固定版本、哈希和源码pins一致。
- 所有离线依赖是否齐全、完整输入路径及冷启动时限是否通过。
- 正式隐藏重跑与真实比赛分数；当前没有这类结果。

返回的 `last_run_time` 原值为 `2026-11-02T07:04:51.133000`，没有暴露时区，且日期早于本地本次创建收据。其确切来源未核实，未将它当成本草稿已执行的证据。本次创建记录明确是quick-save、不请求运行；本核验只执行读取请求。

核验期间所有新增源码下载、缓存/临时目录和pycache均指向D盘。模型、数据资产、云草稿版本和附件均未被本核验修改；没有Run、push或submit。
