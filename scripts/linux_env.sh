#!/usr/bin/env bash
# Source this before any project download, install, or model run.
# The workspace is on D:. Do not use Linux /tmp or a C:-backed home cache.
CASMI_WORKSPACE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export TMPDIR="$CASMI_WORKSPACE/.cache/tmp-linux"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export PIP_CACHE_DIR="$CASMI_WORKSPACE/.cache/pip-linux"
export XDG_CACHE_HOME="$CASMI_WORKSPACE/.cache/xdg"
export TORCH_HOME="$CASMI_WORKSPACE/.cache/torch"
export HF_HOME="$CASMI_WORKSPACE/.cache/huggingface"
export MPLCONFIGDIR="$CASMI_WORKSPACE/.cache/matplotlib"
export NUMBA_CACHE_DIR="$CASMI_WORKSPACE/.cache/numba-linux"
export TRITON_CACHE_DIR="$CASMI_WORKSPACE/.cache/triton"
export CUDA_CACHE_PATH="$CASMI_WORKSPACE/.cache/cuda"
export PYTHONPYCACHEPREFIX="$CASMI_WORKSPACE/.cache/pycache-linux"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1
export PYTHONHASHSEED=0
# Embedded upstream Engine 2 uses an author's machine paths in this mode.
unset CASMI_LOCAL
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR" "$XDG_CACHE_HOME" "$TORCH_HOME" \
  "$HF_HOME" "$MPLCONFIGDIR" "$NUMBA_CACHE_DIR" "$TRITON_CACHE_DIR" \
  "$CUDA_CACHE_PATH" "$PYTHONPYCACHEPREFIX"
cd -- "$CASMI_WORKSPACE"
