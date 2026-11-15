import os, sys, subprocess, importlib.metadata, time
os.environ['PYTHONHASHSEED'] = '0'
NOTEBOOK_STARTED = time.monotonic()   # record total notebook time, including the retained analysis
from pathlib import Path
if not Path('/kaggle/input').exists() and Path('.runtime/rdkit2026033').exists():
    sys.path.insert(0, str(Path('.runtime/rdkit2026033').resolve()))
try:
    installed = importlib.metadata.version('rdkit')
except importlib.metadata.PackageNotFoundError:
    installed = ''
if installed.replace('.03.', '.3.') != '2026.3.3':
    tag=f'cp{sys.version_info.major}{sys.version_info.minor}'
    wheels=sorted(Path('/kaggle/input').rglob(f'rdkit-2026.3.3-{tag}-*.whl'))
    assert wheels, f'Attach the RDKit 2026.3.3 offline wheel for {tag}.'
    subprocess.check_call([sys.executable,'-m','pip','install','--no-index','--no-deps','-q',str(wheels[0])], env={**os.environ, 'PYTHONHASHSEED': '0'})
from rdkit import rdBase
assert rdBase.rdkitVersion == '2026.03.3', rdBase.rdkitVersion
print('Official-metric RDKit:', rdBase.rdkitVersion)
