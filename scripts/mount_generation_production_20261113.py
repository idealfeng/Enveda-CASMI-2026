"""Replace only this task's temporary /kaggle bind mount after verifying its source."""
from pathlib import Path
import argparse
import subprocess
import shlex

parser=argparse.ArgumentParser()
parser.add_argument('--source',required=True)
parser.add_argument('--run',action='store_true')
args=parser.parse_args()
source=Path(args.source).resolve(strict=True)
workspace=Path('/mnt/d/Paper/casmi')
assert source.is_relative_to(workspace/'runs') and source.name=='kaggle'
assert source.parent.name.startswith('generation_production_20261113')
found=subprocess.run(['findmnt','-n','-o','SOURCE','/kaggle'],text=True,capture_output=True)
if found.returncode==0:
    old=found.stdout.strip()
    assert old.startswith('D:\\[/Paper/casmi/runs/generation_production_20261113') and old.endswith('/kaggle]'),old
    subprocess.check_call(['umount','/kaggle'])
else:
    assert Path('/kaggle').is_dir() and not list(Path('/kaggle').iterdir()), 'Refuse nonempty unowned directory'
subprocess.check_call(['mount','--bind',str(source),'/kaggle'])
print(subprocess.check_output(['findmnt','-n','-o','TARGET,SOURCE','/kaggle'],text=True))
if args.run:
    run_root=source.parent
    command='source '+shlex.quote(str(workspace/'scripts/linux_env.sh'))
    command+=' && export PYTHONPATH='+shlex.quote(str(run_root/'resource_site'))
    command+=' && .venv-linux/bin/python scripts/run_generation_production_20261113.py --tag r2'
    with (run_root/'full_run.log').open('w') as log:
        result=subprocess.run(['runuser','-u','storm','--','bash','-lc',command],stdout=log,stderr=subprocess.STDOUT)
    raise SystemExit(result.returncode)
