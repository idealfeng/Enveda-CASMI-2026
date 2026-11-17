"""Launch one approved fixed pilot without tying it to an interactive shell."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/fiora_tims_model_20261115'
OUT=RUN/'pilot500'
RECEIPT=RUN/'training_launch.json'

if os.name!='nt':raise RuntimeError('Windows launcher; child model runs in D-backed WSL')
if RECEIPT.exists() or OUT.exists():raise FileExistsError('Preserve prior launch/output; do not duplicate training')
index=json.loads((ROOT/'runs/fiora_tims_pilot_20261115/index.json').read_text(encoding='utf-8'))
if index['status']!='completed_native_graph_and_label_cache':raise ValueError('Incomplete training cache')
model=json.loads((RUN/'migration_verification.json').read_text(encoding='utf-8'))
if not all(model['checks'].values()):raise ValueError('Unapproved model migration')
command='source /mnt/d/Paper/casmi/scripts/linux_env.sh && exec .venv-linux/bin/python scripts/train_fiora_tims_500_20261115.py --device cuda'
log_path=RUN/'training_console.log'
with log_path.open('xb') as log:
    process=subprocess.Popen(['wsl.exe','-d','Ubuntu','--exec','bash','-lc',command],cwd=ROOT,
        stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
script=ROOT/'scripts/train_fiora_tims_500_20261115.py'
value=dict(status='launched_not_completed',windows_pid=process.pid,
    started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),log=str(log_path),
    script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),optimizer_steps_requested=500,
    new_public_score=None,note='Detached hidden WSL process. Inspect pilot500/verification.json or failure.json; launch is not training completion.')
RECEIPT.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
print(json.dumps(value))
