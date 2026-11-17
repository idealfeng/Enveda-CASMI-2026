#!/usr/bin/env bash
set -euo pipefail
source /mnt/d/Paper/casmi/scripts/linux_env.sh
exec .venv-linux/bin/python -B scripts/build_fiora_submission_payload_20261116.py "$@"
