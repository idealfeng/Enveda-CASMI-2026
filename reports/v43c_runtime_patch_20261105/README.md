# V43c runtime 修复（已整合，完整运行待验证）

经root确认旧Flexc已停止后，2026-11-05已核对全部before/helper SHA并整合两个`.after`；`recovery.py`未改。原字节与新冻结源均按SHA归档，6文件compile及7项tiny tests通过。Flex原始E2单元、生成runner、科学模块payload在修改前后相同配置下完全一致，资源hook仅作用于V43。最终证据见 `applied_receipt.json` 和 `flex_e2_source_equivalence/CHECK.json`。没有启动模型、GPU或全量扫描。

下文保留整合前的审查说明和运行步骤；其中“未应用”描述的是当时草案状态，以本段及`applied_receipt.json`为准。新运行开始后，共享运行源继续冻结。

## 已准备

- `validation/stage_process.py`：保存完整stdout/stderr、returncode、负返回码对应signal、timeout部分输出、config/helper/stream hash。使用独立`engine2_capture*`名字，不被现有简版`engine2_process.json`覆盖。
- `validation/v43_runtime_patch.py`：仅针对新V43源单元替换E2 subprocess调用；在原top-level try/except结束后、已有通用coverage assert之前调用`require_success()`。原代码即使吞掉CalledProcessError/timeout，外层仍抛明确失败，不能继续PC。
- `validation/e2_resources.py`：将原E2 main的workers=32限制为4（未来可用1）；原main的指纹、fragment、canonicalization三个进程池均受限。build_pool前后只回收不可达Python/Arrow/libc缓冲。保存实际32→4、内存快照和helper hash。
- `integration.diff`：共享adapter/runner的精确unified diff，尚未应用。`*.before`是原字节备份，`*.after`是编译通过的目标文本；`integration_receipt.json`绑定所有before/after/helper SHA。recovery.py不改。

## 数值/数据边界

资源hook保留原build_pool、fp_and_mass、所有原算法、map输出顺序、所有科学参数和同一输入对象。Python GC只回收不可达对象，Arrow release_unused和libc malloc_trim只释放空闲allocator块，不改变仍被L/POOL等对象引用的数组。原E2先建立完整候选结构，再屏蔽参考谱的流程未改；mask、候选身份、权重及排序参数未改。

这说明修改的目的与边界，不是整条管线逐位等价或内存一定足够的实测证明。完整V43c仍须独立运行验证；若4 workers仍OOM，保留现场并改新目录/1 worker，或做带来源及等价证明的raw CSR mmap缓存，不能回退到静默缺E2。

## 已做的小检查

- 4个failfast模拟测试通过：负returncode=-9且存在旧输出仍拒绝；timeout保留部分流且原catch不能吞；零退出缺输出拒绝；成功但空召回允许且active IDs精确。
- 3个资源合同测试通过：输入/返回对象保持、workers封顶、其他科学参数保持、异常重新抛出并记录。
- `draft_prepare_sanity.json`：用草案adapter只生成32个V43单元，全部compile；ENG_FILES中三个科学模块经路径规范化后与b现场精确一致。没有执行这些科学模块。
- 没有启动模型、进程池、全量数据扫描或GPU。

## Flexc结束后的整合

1. root明确活动Flexc已结束后，先核对共享三文件与`integration_receipt.json`里的before SHA一致，helpers SHA亦一致。
2. 将两个`.after`应用至对应adapter/runner，保存本目录before字节；recovery.py保持原样。随后compile、运行上述7个tiny tests。
3. 新目录`runs/validation_v43_c2_20261105c`使用`--pipeline v43 --e2-workers 4 --ice-budget 2400 --n1-budget 2400`。不得重用b失败目录；也不得将此hook插入Flex恢复E2的来源绑定中。
4. 配置记录helper hashes和workers上限。实际只有E2完成、exactactive输出和下游健康审核通过才接受。
