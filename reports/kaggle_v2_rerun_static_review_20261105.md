# 云端V2与正式rerun路径只读审查

原Flex V56源码SHA仍为 `0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769`。没有发现正式rerun永久只处理12个分子的截断：唯一`SMOKE_N`切片位于`not IS_RERUN`分支。外层、内层都以非空`KAGGLE_IS_COMPETITION_RERUN`或与占位输入不同的谱ID签名进入full路径；full时主引擎遍历实际输入的所有分子组，postflight断言`processed`等于全部输入ID，导出与神经评分沿用该集合。

输入数量和ID来自运行时文件，没有固定400个ID列表；源preflight要求运行时sample IDs与test IDs一致。静态路径支持全体隐藏查询，仍须由首次比赛代码提交后的真实执行结果检验，不能把当前可见提交的400行输出当成隐藏400推理证明。

| 时间控制 | 原正式rerun设置 |
| --- | ---: |
| Kaggle请求session上限 | 32400秒（9小时） |
| ICE | 5400秒 |
| GL | 4000秒 |
| N1 | 1200秒（可见smoke为600秒） |
| optional outsider guard | 7.5小时 |
| physical overlay | 最多1500秒，并以总运行8.55小时为deadline；剩余不足180秒时跳过 |

full模式允许正向谱模型按预算保留部分已完成分数。因此“读取和尝试全部分子”不能写成“全部模型完整评分400个分子”。主baseline、最终列表Saner评分、consensus及所选CUSTOM控制失败有外层显式错误门；可选物理层有恢复控制结果的路径，需要实际产物检查。

本次V2版本绑定状态为COMPLETE。紧凑日志71条，最后时间1263.55秒，明确说明只覆盖12个visible smoke分子；未发现显式Traceback或错误恢复，神经输入失败为0，MERGE/FINAL为applied。`PROVENANCE=False`是原配置，`output_equals_custom=true`也可合法发生，不是失败证据。其余388行是否为CCO由单独的下载产物审核确认。

设备应查`run_manifest.json.gpu`和`e004_verification.json`中的实际nvidia-smi结果；64文件检查在`submission_pipeline.log`。Saner四个`MODEL_PINS`由stage0 `find_bundle()`逐文件完整SHA检查，并要求唯一匹配；`p2s_code/bundle.py`和pinned源码回执可支持该执行链。`v43_mounted_input_hashes.json`记录基线挂载内容，大文件仅size与头尾哈希，不能说是所有大文件的完整SHA或服务端挂载版本号证明。

安装SDK为kaggle2.2.5。正式代码提交方法是`competition_submit_code(file_name='submission.csv', message=唯一描述, competition=比赛slug, kernel='stormseye/casmi26-flex-v56-baseline', kernel_version=2, quiet=True)`；`kernel`不带`/2`，版本为独立参数。合法响应只有`message`与整数`ref`，需要正ref才称已受理。随后按该ref调用GetSubmission，其状态为PENDING/COMPLETE/ERROR；COMPLETE且public_score能解析为有限数值才报告榜分。网络结果不明只查询核对，不重复POST。此审查没有调用提交、运行、push、网络接口或读取密钥。

详细AST检查、日志摘要、预期MODEL_PINS及SDK字段见[结构化审查](kaggle_v2_rerun_static_review_20261105.json)。
