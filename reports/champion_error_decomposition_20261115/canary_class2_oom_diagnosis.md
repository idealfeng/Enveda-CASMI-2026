# 首轮Class2 canary：E2初始化失败的只读诊断

2026-11-15。没有重新运行E2、修改runner/mask、终止进程或更改WSL设置。原现场保留；主控已停止其本次root/inner继续fallback运行。

**确定观察到同期系统OOM；E2日志里的FileNotFound是未产出eng_lists.json后的下游症状。**

## 证据

- `canary_class2/full_run.log` 显示outer14正在完整baseline子进程；inner32的E2随后失败，原异常捕获打印 `ENGINE FAILED -> v4g lists kept: FileNotFoundError(2, 'No such file or directory')`，并继续inner34 PubChem、inner36。
- `canary_class2/kaggle/working/submission_pipeline.log` 的E2最后输出：82秒 library mass index、85秒2,539,608谱、92秒ChEBI/LMSD、104秒PubChemLite、106秒 `COCONUT 891,642; training structures to fingerprint 245,591`。没有Python traceback、pool完成消息、eng_lists或E2成功完成事件。
- 真实generated E2安装事件记录PID674，文件创建时间 **04:06:14.861 UTC / 12:06:14.861北京时间**；原outer32总计约215秒后进入fallback，与下面OOM时点吻合。
- `canary_class2_kernel_dmesg_readback.txt` 保存只读kernel原文，SHA256 `05e236006623284de9e6ffda084ab4ad6ce5d7b769246df2c8b77696e49cd987`。约北京时间 **12:09:51–52**（重复读回ctime有1秒时钟偏差）出现 `global_oom`，`Free swap = 0kB`、`Total swap = 2097152kB`，内核杀死python PID1693，anon-rss **6,184,556kB**、total-vm **12,510,600kB**。
- OOM任务表另有python1593/1632/1693，分别与本轮root574/inner613/E2 674恰好均差1019。这与WSL/systemd PID namespace映射相容，加上时间和内存吻合，**高度支持被杀的是本次E2**；死亡前未持久化NSpid映射/child returncode，不能把这个整数偏移单独当作严格PID身份证明。
- 后读 `/proc/meminfo` 已显示进程停止后的MemAvailable约6.95GB、swap约2GB空闲，只是事后快照，不代表出事时内存充足。

## 原因与最小资源适配

E2在建立全量候选池时fork fingerprint workers。原parent已保留完整2.54M参考、COCONUT/BIO/PubChemLite结构和指纹；训练结构fingerprint还会经历结果list、`np.stack`、`np.vstack`及最终排序拷贝。并行子进程的RSS包含大量共享页，不能把parent与四个worker RSS直接相加当物理占用；但worker私有RDKit状态、写时复制及parent瞬时拷贝仍可使7.5GB RAM+2GB swap耗尽。

1. 新revision将generated eng_runner的 `E.main(...workers=os.cpu_count())` 改为 **workers=1**，确实覆盖出事的 `build_pool(L,workers)` → `MPool(workers)`。真实E2的 `compute_frag`、`make_submissions`也复用该workers；所查E2/casmi_engine.py、pv.py、pv_fp.py无另外独立os.cpu_count池。这不改变指纹函数、map顺序、候选或排序参数。
2. 可直接复用 `validation/e2_resources.py:install(E,config_path,worker_limit=1)`，在参考mask hook后安装。它在build_pool前后释放不可达对象、Arrow unused pool及malloc unused，持久化内存快照；不改变活跃数组、指纹算法或顺序。只改一个worker不保证所有parent拷贝峰值必然可容纳，应继续实际观察。
3. E2/PC subprocess必须保存args、开始/结束时间、returncode、完整stdout/stderr，非零或缺少实际输出时在原catch外failfast，不能继续fallback再称完整冠军。SIGKILL可能没有Python traceback，应保留-9/137的实际返回值；本轮未记录故不倒填。
4. 若上述最小适配仍OOM，再另评估严格等价的内存映射/分块或更大内存环境，并保留新revision。不能通过少读参考、删结构、改模型、跳E2或复用旧分数解决“完整冠军”验证。

本次属于初始化/资源失败，没有该canary的完整最终CSV、类别指标或算法收益结论。冻结mask模块及原实验/资产均未修改，produre1/2未重做。
