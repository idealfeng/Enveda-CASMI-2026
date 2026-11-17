# 冠军生产路径错误分解：20261115

- 状态：首个Class2一题完整生产canary执行中；Class1/3尚未真实执行。模型前向/隔离准入/最终指标分别记录，不把源码检查叫运行完成。
- 假设：近期同源模型与既有分数重排收益递减。完整冠军尚缺从静态/生成候选到MASS/head/AB最终排名的连续证据，先补该缺口以选择新能力路线。
- 父版本：正式58156482/Public .488，`submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb`，SHA `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`；嵌套FROZEN SHA `d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88`。
- 唯一算法方面改动：无新排序/模型参数；诊断显式屏蔽参考，Class3另屏蔽所有静态目标身份。加入只读观测、共享原清洗cache/mmap及4 CPU资源限制，实际执行文本适配、代码和输入SHA另保存。
- 模型：保留原public/v2、ICE/GL、原160特征ranker和guarded heads；原生成6母体、每母体60、总150、双步保持。没有新训练，没有注入旧分数。
- 查询：复用冻结48题面板，首题固定`cross_VXVNYCRICCVPTD`/8谱；选择理由是已知多个官方同身份SID，适合检验完整隔离，不能拿该单题成绩估计增益。推理test只含12个谱/离子/能量字段，真值及source_row不进预测输入。全48cohort的旧排除mask用于canary和后续同口径放大；锁定final250不碰。
- 三种可用性条件：Class1删除原query及内容重复；Class2删除全部目标官方身份参考，候选结构仍可用；Class3再删除静态目标结构，保留算法重新生成。它们不是隐藏实际类别标签或占比。
- 审计：原outer所有code cell到最终CSV；E1检索/analog/751扩展、E2全SID代表、独立AB都必须遵守mask。PC、E1、E2、LOTUS及rescue等静态来源的Class3排除不完整时拒绝报告。library_max由本次隔离原生产重算。
- 输出：`runs/champion_error_decomposition_20261115/canary_class2/`；`full_run.log`、`progress.json`、`launch_bindings.json`、执行脚本快照、inner适配记录、逐阶段原候选/CSV和失败证据。
- 启动：先WSL `source scripts/linux_env.sh`，用`run_champion_diagnostics_20261115.py --prepare --arm class2`准备，再root helper `mount_champion_diagnostics_20261115.py --arm class2`核对旧挂载所有权并绑定D视图。无网络或Kaggle写入。
- 评价：在完整推理输出冻结、隔离审计通过后单独用官方RDKit2026.03.3身份计算每阶段真结构存在/排名。缺候选、过滤丢失、25名截断、排序和最终后处理分别记；候选阶段无证据则标未知。预训练已知曝光仍存在，不能叫干净CV，也不是新榜分。
- 已知观测边界：E2 observer在import后安装，安装快照早于原runner的CFG/RANK赋值；实际运行配置需结合生成runner源码及main调用核实。不会据该早快照声称原默认是实际参数。
- 决策：首题只为放行隔离和完整路径；不重做produre1/2，不扫参数，不因单题变好提交Kaggle。后续研发主线是强独立信息或新的候选生成能力。
- 保留级别：原模型/提交不移动；新源码、执行快照、配置、指标/日志和失败证据保留。
