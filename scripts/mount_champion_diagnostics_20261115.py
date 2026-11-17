"""Bind only a verified task-owned D view and launch one diagnostic replay."""
from pathlib import Path
import argparse
import subprocess
import shlex

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--arm',choices=['class1','class2','class3'],required=True);p.add_argument('--full48',action='store_true');p.add_argument('--revision',default='');a=p.parse_args()
if a.revision and not a.revision.isalnum():raise ValueError('Alphanumeric revision required')
run=ROOT/'runs/champion_error_decomposition_20261115'/(('full48_' if a.full48 else 'canary_')+a.arm+('_'+a.revision if a.revision else ''))
view=(run/'kaggle').resolve(strict=True)
if not view.is_relative_to(ROOT/'runs/champion_error_decomposition_20261115'):raise ValueError('Unexpected bind target')
found=subprocess.run(['findmnt','-n','-o','SOURCE','/kaggle'],capture_output=True,text=True)
if found.returncode==0:
    old=found.stdout.strip()
    prefixes=['D:\\[/Paper/casmi/runs/generation_production_20261113','D:\\[/Paper/casmi/runs/champion_error_decomposition_20261115/']
    if not any(old.startswith(t) for t in prefixes) or not old.endswith('/kaggle]'):raise ValueError('Refuse unowned mount: '+old)
    subprocess.check_call(['umount','/kaggle'])
elif not Path('/kaggle').is_dir() or list(Path('/kaggle').iterdir()):raise ValueError('Refuse nonempty unowned /kaggle')
subprocess.check_call(['mount','--bind',str(view),'/kaggle'])
command='source '+shlex.quote(str(ROOT/'scripts/linux_env.sh'))
command+=' && export PYTHONPATH='+shlex.quote(str(run/'resource_site'))
command+=' && .venv-linux/bin/python scripts/run_champion_diagnostics_20261115.py --arm '+a.arm
if a.full48:command+=' --full48'
if a.revision:command+=' --revision '+a.revision
with (run/'full_run.log').open('x') as log:
    result=subprocess.run(['runuser','-u','storm','--','bash','-lc',command],stdout=log,stderr=subprocess.STDOUT)
raise SystemExit(result.returncode)
