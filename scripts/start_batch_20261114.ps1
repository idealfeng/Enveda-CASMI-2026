$ErrorActionPreference='Stop'
$taskRoot='D:\Paper\casmi'
$taskState=Join-Path $taskRoot 'reports\optimization_20261114'
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$env:PYTHONIOENCODING='utf-8'
$env:TEMP=Join-Path $taskRoot '.cache\tmp'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX=Join-Path $taskRoot '.cache\pycache-win'
if(-not (Test-Path -LiteralPath (Join-Path $taskState 'release_gate.json'))) { throw 'Release gate required' }
foreach($taskName in @('.dispatcher.lock','watcher.lock')) {
    if(Test-Path -LiteralPath (Join-Path $taskState $taskName)) { throw "Existing active task lock: $taskName" }
}

# Preserve and retire only the prior daily ledger process/lock. No Kaggle job
# is canceled. Validate command text before stopping any live process.
$taskGlobalLock=Join-Path $taskRoot 'reports\.improvement_ledger.writer.lock'
if(Test-Path -LiteralPath $taskGlobalLock) {
    $taskPrior=Get-Content -LiteralPath $taskGlobalLock -Raw | ConvertFrom-Json
    $taskPriorPid=[int]$taskPrior.pid
    if($taskPriorPid -le 0) { throw 'Invalid prior writer PID' }
    $taskProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$taskPriorPid"
    $taskStopped=$false
    $taskRetired='prior_process_absent'
    if($null -ne $taskProcess) {
        $taskCommand=[string]$taskProcess.CommandLine
        if(-not $taskCommand) { throw 'Cannot verify current owner of prior PID' }
        if($taskCommand.Contains('watch_all_today_20261113.py') -and $taskCommand.Contains('--watch')) {
            Stop-Process -Id $taskPriorPid
            $taskDeadline=(Get-Date).AddSeconds(5)
            while((Get-Process -Id $taskPriorPid -ErrorAction SilentlyContinue) -and (Get-Date) -lt $taskDeadline) { Start-Sleep -Milliseconds 100 }
            if(Get-Process -Id $taskPriorPid -ErrorAction SilentlyContinue) { throw 'Prior writer still running' }
            $taskStopped=$true
            $taskRetired='exact_owned_prior_watcher_stopped'
        } elseif($taskCommand.Contains('watch_batch_with_ledger_') -or $taskCommand.Contains('watch_all_today_')) {
            throw 'A different ledger worker owns the prior PID; inspect before takeover'
        } else {
            $taskRetired='pid_reused_by_different_process_no_process_stopped'
        }
    }
    [ordered]@{at=(Get-Date -Format o);prior_lock=$taskPrior;prior_process_stopped=$taskStopped;disposition=$taskRetired} | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $taskState 'prior_writer_retired.json') -Encoding utf8
    if(Test-Path -LiteralPath $taskGlobalLock) { Remove-Item -LiteralPath $taskGlobalLock }
}
$taskDispatch=Start-Process -FilePath $taskPython -ArgumentList @('-u','scripts/dispatch_20261114.py','--watch','--max-hours','6') -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskState 'dispatcher_stdout.log') -RedirectStandardError (Join-Path $taskState 'dispatcher_stderr.log') -PassThru
$taskWatcher=Start-Process -FilePath $taskPython -ArgumentList @('-u','scripts/watch_batch_with_ledger_20261114.py','--watch','--max-hours','12') -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskState 'watcher_stdout.log') -RedirectStandardError (Join-Path $taskState 'watcher_stderr.log') -PassThru
[ordered]@{started_at=(Get-Date -Format o);dispatcher_launcher_pid=$taskDispatch.Id;watcher_launcher_pid=$taskWatcher.Id;branches=5;max_submissions=5;single_ledger_writer=$true;manifest='submission/optimization_20261114/manifest.json'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskState 'background_start.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $taskState 'background_start.json')
