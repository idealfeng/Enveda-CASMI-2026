# Dot-source before project downloads/installations. No global user settings change.
$casmiWorkspace = Split-Path -Parent $PSScriptRoot
$env:TEMP = Join-Path $casmiWorkspace '.cache\tmp-windows'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $casmiWorkspace '.cache\pip'
$env:TORCH_HOME = Join-Path $casmiWorkspace '.cache\torch'
$env:HF_HOME = Join-Path $casmiWorkspace '.cache\huggingface'
$env:MPLCONFIGDIR = Join-Path $casmiWorkspace '.cache\matplotlib-windows'
$env:NUMBA_CACHE_DIR = Join-Path $casmiWorkspace '.cache\numba-windows'
$env:CUDA_CACHE_PATH = Join-Path $casmiWorkspace '.cache\cuda-windows'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
foreach ($casmiCachePath in @($env:TEMP, $env:PIP_CACHE_DIR, $env:TORCH_HOME, $env:HF_HOME, $env:MPLCONFIGDIR, $env:NUMBA_CACHE_DIR, $env:CUDA_CACHE_PATH)) {
    [System.IO.Directory]::CreateDirectory($casmiCachePath) | Out-Null
}
