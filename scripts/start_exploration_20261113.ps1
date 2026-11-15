$ErrorActionPreference='Stop'
$taskRoot='D:\Paper\casmi'
$taskState=Join-Path $taskRoot 'reports\optimization_20261113'
$taskExtra=Join-Path $taskState 'exploration'
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$env:PYTHONIOENCODING='utf-8'
$env:TEMP=Join-Path $taskRoot '.cache\tmp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX=Join-Path $taskRoot '.cache\pycache-win'

if(-not (Test-Path -LiteralPath (Join-Path $taskState 'exploration_release_gate.json'))) {
    throw 'Release gate required before starting cloud writes'
}
if(Test-Path -LiteralPath (Join-Path $taskExtra '.dispatcher.lock')) {
    throw 'Existing exploration dispatcher; do not launch twice'
}
if(Test-Path -LiteralPath (Join-Path $taskRoot 'reports\.improvement_ledger.writer.lock')) {
    throw 'An aggregate ledger writer already exists'
}

# Stop only the exact earlier read-only process created for this daily manifest.
# This does not cancel or alter any Kaggle Notebook or formal submission.
$taskOldLock=Join-Path $taskState 'watcher.lock'
if(Test-Path -LiteralPath $taskOldLock) {
    $taskOld=Get-Content -LiteralPath $taskOldLock -Raw | ConvertFrom-Json
    $taskOldPid=[int]$taskOld.pid
    if($taskOldPid -le 0) { throw 'Invalid old watcher PID' }
    $taskProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$taskOldPid"
    if($null -ne $taskProcess) {
        $taskCommand=[string]$taskProcess.CommandLine
        if(-not $taskCommand.Contains('watch_batch_with_ledger_20261113.py') -or
           -not $taskCommand.Contains('submission/optimization_20261113/manifest.json') -or
           -not $taskCommand.Contains('--watch')) {
            throw 'Old watcher PID no longer identifies the expected owned process'
        }
        Stop-Process -Id $taskOldPid
        $taskDeadline=(Get-Date).AddSeconds(5)
        while((Get-Process -Id $taskOldPid -ErrorAction SilentlyContinue) -and (Get-Date) -lt $taskDeadline) {
            Start-Sleep -Milliseconds 100
        }
        if(Get-Process -Id $taskOldPid -ErrorAction SilentlyContinue) { throw 'Old writer still running' }
    }
    $taskOld | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $taskState 'single_branch_watcher_replaced.json') -Encoding utf8
    if(Test-Path -LiteralPath $taskOldLock) { Remove-Item -LiteralPath $taskOldLock }
}
$taskOldStatus=Join-Path $taskState 'latest_status.json'
if(Test-Path -LiteralPath $taskOldStatus) {
    Copy-Item -LiteralPath $taskOldStatus -Destination (Join-Path $taskState 'single_branch_status_before_aggregate.json')
}
New-Item -ItemType Directory -Path $taskExtra -Force | Out-Null
$taskDispatch=Start-Process -FilePath $taskPython -ArgumentList @('-u','scripts/dispatch_subset_batch_20261112.py','--manifest','submission/optimization_20261113/exploration_manifest.json','--watch','--max-hours','6') -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskExtra 'dispatcher_stdout.log') -RedirectStandardError (Join-Path $taskExtra 'dispatcher_stderr.log') -PassThru
$taskWatcher=Start-Process -FilePath $taskPython -ArgumentList @('-u','scripts/watch_all_today_20261113.py','--watch','--max-hours','12') -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskState 'all_today_watcher_stdout.log') -RedirectStandardError (Join-Path $taskState 'all_today_watcher_stderr.log') -PassThru
[ordered]@{started_at=(Get-Date -Format o);dispatcher_launcher_pid=$taskDispatch.Id;watcher_launcher_pid=$taskWatcher.Id;manifest='submission/optimization_20261113/exploration_manifest.json';new_branches=4;maximum_total_today=5;single_ledger_writer=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskExtra 'background_start.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $taskExtra 'background_start.json')
