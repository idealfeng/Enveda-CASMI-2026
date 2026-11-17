"""Stop only the known failed, task-owned class2 diagnostic process tree."""
from pathlib import Path
import os
import signal
import json
import time

root=Path('/mnt/d/Paper/casmi/runs/champion_error_decomposition_20261115/canary_class2')
log=(root/'kaggle/working/submission_pipeline.log').read_text()
if 'ENGINE FAILED -> v4g lists kept:' not in log:raise RuntimeError('No observed E2 failure')
rows={}
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        args=[a.decode(errors='replace') for a in (p/'cmdline').read_bytes().split(b'\0') if a]
        stat=(p/'stat').read_text().rsplit(')',1)[1].split()
        rows[int(p.name)]=(int(stat[1]),args)
    except (OSError,ValueError):pass
matches=[pid for pid,(ppid,args) in rows.items() if any(a.endswith('/run_champion_diagnostics_20261115.py') for a in args) and 'class2' in args]
if len(matches)!=1:raise RuntimeError('Expected one owned replay, found '+str(matches))
order=[]
def descend(pid):
    for child,(ppid,args) in rows.items():
        if ppid==pid:descend(child)
    order.append(pid)
descend(matches[0])
receipt=dict(status='stopped_incomplete_diagnostic',reason='E2 no eng_lists.json; original source swallowed failure and used fallback.',stopped_pids=order,root_replay_pid=matches[0],at_epoch=time.time())
(root/'operator_stop.json').write_text(json.dumps(receipt,indent=2)+'\n')
for pid in order:
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
print(json.dumps(receipt))
