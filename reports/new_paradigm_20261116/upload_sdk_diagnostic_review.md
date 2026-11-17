# 私有payload上传耗时与回执归一化诊断

2026-11-16，只读本地SDK源码与已脱敏create回执；未中止、重试或重新启动上传，没有读取或输出signed URL、token、header或进程内存。

## 本次最重要发现

上传自15:01:26 UTC开始，create回执于15:06:25 UTC收到 `error_present=false`、`observed_status='Ok'`、`observed_ref='/datasets/stormseye/casmi26-fiora-tims500-1116'`。上传器原accept表达式仅比较strip斜线后的ref与owner/slug，遗漏服务端 `datasets/` 前缀，因此误标 `server_response_requires_review_no_retry`。这是**可能已成功创建但本地ref规范化未识别**，不能据此重新create。已即刻通知主agent，后续只读ready、private、version1、准确ref来reconcile。

## 五分钟是否意味着挂住

本地SDK `upload_files` 对单zip调用 `_upload_file` / `_upload_blob`，不是每个zip内部文件独立传输。当前blob上传是 `requests.Session.put(url, data=TqdmBufferedReader(fp,...))` 单次流式PUT，未设置固定application chunk size，也**没有timeout参数**。主workflow `make_api` 注入的(15,45)只作用于Kaggle SDK HTTP client，不覆盖此独立requests Session。因此5分钟不能单独当成死锁或45秒timeout失效。

该Session安装 `HTTPAdapter(Retry(total=10,backoff_factor=.5))`；外围 `_upload_blob` 最多10次resume，遇INCOMPLETE查询服务端Range后继续。此为同一blob传输机制，不是对dataset create重新发起。主上传器已禁用其create API外层with_retry，且有独占claim；没有人工重试。

Dataset正式create发生于所需blob传完以后，所以传输期间status端点403仍可能正常。本次51,684,471B用时约299秒只说明最终完整链路耗时，不能反推出持续带宽或是否发生SDK内部resume。

## 能否安全观察进度

当前 `quiet=True` 且stdout/stderr在进程内StringIO，tqdm关闭，没有持久化逐字节进度日志。`ResumableUploadContext`稳定state目录在任务TMP下（本项目D盘 `.cache/tmp/.kaggle-uploads`），初始化和upload_complete会写入，成功context退出清理；它不持续保存每次read的offset。

状态内容含signed upload URL及blob token，**不要dump文件、日志或headers**。只看state文件存在、大小、mtime可判断是否初始化/清理，不能当上传百分比；本审查没有打开状态内容。本次读取时目录无可见残余state文件，与成功context清理一致，但最终仍应以服务端只读metadata判断。

如未来需要进度，应在下一次新workflow开始前预先添加仅字节计数/时间日志和显式传输timeout；本次已进行的上传不得为观察进度而停止或重新发起。云端可见metadata之后再推进Notebook。
