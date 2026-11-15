param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$workspace = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
if ($workspace -ne 'D:\Paper\casmi') { throw 'Unexpected cleanup workspace' }
$prefix = $workspace + '\'
$cutoff = [DateTime]::UtcNow.AddHours(-24)
$receiptRoot = Join-Path $workspace 'reports\project_cleanup_20261111'
New-Item -ItemType Directory -Path $receiptRoot -Force | Out-Null
$roots = @((Join-Path $workspace '.cache\pip-linux'))
$temporary = Join-Path $workspace '.cache\tmp-linux'
$roots += @(Get-ChildItem -LiteralPath $temporary -Directory -Force | Where-Object { $_.Name -like 'pip-*' } | ForEach-Object { $_.FullName })
$files = @()
$directories = @()
foreach ($candidate in $roots) {
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup target outside workspace' }
    $allowed = $resolved -eq (Join-Path $workspace '.cache\pip-linux') -or
        ($resolved.StartsWith($temporary + '\', [StringComparison]::OrdinalIgnoreCase) -and
         [System.IO.Path]::GetFileName($resolved) -like 'pip-*')
    if (-not $allowed) { throw 'Cleanup target outside explicit install-cache allowlist' }
    $entries = @((Get-Item -LiteralPath $resolved -Force)) + @(Get-ChildItem -LiteralPath $resolved -Recurse -Force)
    foreach ($entry in $entries) {
        if (-not $entry.FullName.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Escaped workspace' }
        if (($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Refuse linked cleanup tree' }
        if ($entry.PSIsContainer) { $directories += $entry.FullName; continue }
        if ($entry.LastWriteTimeUtc -lt $cutoff) {
            $files += [PSCustomObject]@{path=$entry.FullName; bytes=[long]$entry.Length; last_write_utc=$entry.LastWriteTimeUtc.ToString('o')}
        }
    }
}
$record = [ordered]@{status='planned'; checked_at_utc=[DateTime]::UtcNow.ToString('o');
    scope='Only pip HTTP cache and pip-* temporary installation files older than 24h';
    bytes_planned=[long](($files | Measure-Object -Property bytes -Sum).Sum);
    file_count=$files.Count; files=$files; deleted_files=0; deleted_bytes=[long]0;
    preserved=@('.cache/wheels-linux','.cache/windows-system-ca-bundle.pem','assets','runs','submission','produre1','produre2')}
$planPath = Join-Path $receiptRoot 'cache_cleanup_plan.json'
if ($Apply -and (Test-Path -LiteralPath (Join-Path $receiptRoot 'cache_cleanup_result.json'))) { throw 'Preserve existing cleanup receipt; do not reapply' }
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $planPath -Encoding UTF8
if ($Apply) {
    $record.status='applying'
    foreach ($file in $files) {
        $current = Get-Item -LiteralPath $file.path -Force
        if ($current.Length -ne $file.bytes -or $current.LastWriteTimeUtc -ge $cutoff -or
            ($current.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'File changed since plan' }
        Remove-Item -LiteralPath $current.FullName -Force
        $record.deleted_files++
        $record.deleted_bytes += $file.bytes
    }
    # Remove only directories proven empty; no recursive deletion or cross-shell paths.
    foreach ($directory in ($directories | Sort-Object -Property Length -Descending)) {
        if ($directory -eq (Join-Path $workspace '.cache\pip-linux')) { continue }
        if (@(Get-ChildItem -LiteralPath $directory -Force).Count -eq 0) {
            Remove-Item -LiteralPath $directory -Force
        }
    }
    $record.status='completed'
    $record.completed_at_utc=[DateTime]::UtcNow.ToString('o')
    $record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $receiptRoot 'cache_cleanup_result.json') -Encoding UTF8
}
[PSCustomObject]@{status=$record.status; files=$record.file_count; planned_gib=[Math]::Round($record.bytes_planned/1GB,3);
    deleted_gib=[Math]::Round($record.deleted_bytes/1GB,3)} | ConvertTo-Json
