# 生成候选 r3：修复审计目录假设

本轮先前revision2云可见运行失败，**未正式提交**。失败日志 `generation_failed_log.txt` 明确显示最终审计试图读取 `/kaggle/working/code/generation_runtime_patch_20261112.py`，实际部署CODE是 `/kaggle/working/p2s_code`。此前本地入口测试用了code目录，因此遗漏了该差异。

## 最小修复与冻结范围

- 新module：`scripts/generation_runtime_patch_20261112_r3.py`。最终audit用`Path(__file__).resolve()`绑定当前实际安装的module，runner取其同目录，并核对launch记录的actual_runner解析后是同一路径。
- 新builder：`scripts/build_generation_variant_20261112_r3.py`。
- 新stage：`submission/optimization_20261112/generation_expand/revision3/`，branch `generation_expand_r3`，target `stormseye/casmi26-generation-expand-r3-1112`，旧失败target和stage保留。
- 安装时保留兼容basename `generation_runtime_patch_20261112.py`，使runner文本和导入完全不变；实际安装的字节为新r3 module，并校验新SHA。
- 全部推理函数（audit之前的源代码）与revision2逐字节相同，配置仍12母体、总300、单母体60、双步、额外同分异构化关闭。没有修改生成或排序算法，没有新增训练、没有重跑两查询模型或produre面板。

冻结指纹：

| 文件 | SHA256 |
| --- | --- |
| Notebook | `1f9a7119dd4fdb45e006c71bd89719646dd08723faf0737920e1b0fd658c73a9` |
| module | `0a9a19291ab2f4867331b6f4c81c535c30246ad2d0df873e11dd8ce04d3c8590` |
| runner（与r2相同） | `153c85fb59025f3c2fa75cf9a64ffe7aa6cdb26b25113fee9fa46643c22f1182` |

## 验证与范围

`runs/generation_recovery_r3_20261112/verification.json`：12/12通过。使用真实CODE布局`p2s_code`，且没有兼容用的root/code目录；执行exact staged setup、确认实际run_stage参数指向新runner、执行exact appended final fast audit。

hidden审计路径测试复用revision2真实两查询的`generation_runtime.json`和ranked CSV，逐字节保留；AB审计和launch是明确构造的fixture，只检查审计路径与输出绑定，**不是新全量推理或Kaggle hidden运行**。另外篡改launch为另一个目录后，审计拒绝并删除最终CSV，证明实际module目录与launch目录约束生效。

生成推理的既有7/7证据仍在 `runs/generation_prod_canary_20261112_actual_revision2/verification.json`。原stage/结果和失败日志不覆盖。新r3的Kaggle运行和正式提交由根协调器处理，本恢复任务没有Kaggle写入。
