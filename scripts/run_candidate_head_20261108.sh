#!/usr/bin/env bash
set -euo pipefail
source /mnt/d/Paper/casmi/scripts/linux_env.sh
.venv-linux/bin/python scripts/train_candidate_multispectrum_head.py export --device cuda > runs/candidate_head_20261108/export.log 2>&1
.venv-linux/bin/python scripts/verify_candidate_head_training.py > runs/candidate_head_20261108/verification.log 2>&1
.venv-linux/bin/python scripts/train_candidate_multispectrum_head.py train --device cuda --steps 2500 --seed 20261108 > runs/candidate_head_20261108/train_seed20261108.log 2>&1
.venv-linux/bin/python scripts/train_candidate_multispectrum_head.py train --device cuda --steps 2500 --seed 20261109 > runs/candidate_head_20261108/train_seed20261109.log 2>&1
