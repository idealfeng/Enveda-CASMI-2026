import glob, json, subprocess, sys, time
from pathlib import Path

def find(pattern):
    hits = sorted(glob.glob(f'/kaggle/input/**/{pattern}', recursive=True), key=len)
    return Path(hits[0]) if hits else None

try:
    import rdkit
except ImportError:
    tag = f'cp{sys.version_info.major}{sys.version_info.minor}'
    wheel = [w for w in glob.glob('/kaggle/input/**/rdkit-*.whl', recursive=True) if tag in w][0]
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-index', '--no-deps', wheel], check=True)

CODE = find('pipeline.py').parent            # my code + v2 weights
V3 = find('fpnet_v3_config.json').parent       # output of the GPU training notebook
sys.path.insert(0, str(CODE))
DATA = find('train.parquet').parent
COCO = find('coco_meta.pkl').parent
PUBCHEM = find('pc_smiles.npy').parent
POP = find('pc_lsid.npy').parent
CFG = json.load(open(V3 / 'fpnet_v3_config.json'))
print(CFG)