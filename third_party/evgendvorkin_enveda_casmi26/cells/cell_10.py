'''CASMI26 v4n = v4i + ICE_LAM = GL_LAM = 1.0 (v4l, LB 0.380) + engine FP bank fpnet_full1 (v4m, LB 0.378)'''
'''CASMI26 v4i = v4h + PubChem-only channel pass-1 depth N1 1000 -> 5000 (recall; gate/slots unchanged)'''
'''CASMI26 v4h = v4g + GLACIER third re-scoring term: z(ranker) + 0.5 z(ICEBERG) + 0.5 z(GLACIER) (casmi26-glacier)'''
'''casmi26 v28 = v17 + pool popularity re-rank of the base list (mu 0.15, mode A); v17 = Ahmed v4g + popularity prior in the PubChem list (see make_v17.py)'''
'''CASMI26 v4f = v4b (FPNet A engine bank, LB 0.354) + ICEBERG post-ranker isomer re-scoring = the v3.6 model (v1 engine + FPNet A + moderate generation + gated PubChem channel, LB 0.358)'''
'''+ fe_v4 feature families computed on the SAME v1 engine run (derivation evidence / class-3 priors, fragmentation 2.0,'''
'''analog-structure relations, DreamsFP views) + a ranker retrained on the v1-engine simulation sim1x with them.'''
'''Built by work/analysis/fe_v4/build_v4v1.py -- edit there.'''
import os, sys, glob, re, subprocess, time, json, hashlib, pickle
from pathlib import Path
T0 = time.time()
LIB_TAU, REL_TH = 0.9, 600.0
TOPN, ICE_LAM, ICE_BUDGET, ICE_PC = 60, 1.0, 5400, True
SLOTS_AGG, SLOTS_GENTLE = [2, 4, 6, 8, 10], [4, 8, 12, 16, 20]
PC_SIXTH_SLOT = 24
SLOTS_AGG = SLOTS_AGG + [PC_SIXTH_SLOT]
SLOTS_GENTLE = SLOTS_GENTLE + [PC_SIXTH_SLOT]
print("PUBCHEM_SIXTH_SLOT active=" + str(PC_SIXTH_SLOT) + " aggressive=" + str(SLOTS_AGG) + " gentle=" + str(SLOTS_GENTLE), flush=True)
os.makedirs('/kaggle/working/numba_cache', exist_ok=True)
os.environ['NUMBA_CACHE_DIR'] = '/kaggle/working/numba_cache'
def find(pattern):
    hits = sorted(glob.glob(f'/kaggle/input/**/{pattern}', recursive=True), key=len)
    if not hits:
        raise FileNotFoundError(pattern)
    return hits[0]
def sha256(path, n=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(n), b''):
            h.update(b)
    return h.hexdigest()
FOLD_CHECKPOINT_SHA256 = {'fpnet_fold0.pt': 'ddf6eaaa8e541a16e3f0357ed30f0346e529054f75d5619aedb6024dcb1bd7f0', 'fpnet_fold1.pt': '1739d5683fa94fd73fe3b37db98ac364cb5dfdc22ad5bea9789be9c48d7cadc4', 'fpnet_fold2.pt': '257062cb6ece333226027de6e313792e7b364517adf42a05e0df950b8e27bbe2', 'fpnet_fold3.pt': 'ac61125ef34415d857d58a115e017e0af2aede044e3a5d524029dd1364cbd58c', 'fpnet_fold4.pt': 'ad0b2a43343287f7deb4334c4ad766e8aa236d7f0bbeb91e3702910ee49aabe7'}
FOLD_PATHS = [str(FOLD / f'fpnet_fold{k}.pt') for k in range(5)]
FOLD0_PATH = FOLD_PATHS[0]
for _fold_path in FOLD_PATHS:
    assert Path(_fold_path).is_file(), _fold_path
    assert sha256(_fold_path) == FOLD_CHECKPOINT_SHA256[Path(_fold_path).name], ('Untested fold-safe checkpoint', _fold_path)
os.environ['CASMI_FPNET_FOLD0'] = FOLD0_PATH
os.environ['CASMI_FPNET_FOLDS'] = json.dumps(FOLD_PATHS)
print('PubChem ensemble rule: z_AB + 0.5 * mean(z_fold0..z_fold4)', flush=True)
POP_LAM, POP_UNION = 0.15, 200            # v17: popularity prior for the PubChem-only list
os.environ['CASMI_POP_DIR'] = str(POP); os.environ['CASMI_POP_LAM'] = str(POP_LAM); os.environ['CASMI_POP_UNION'] = str(POP_UNION)
print('v17 popularity prior', POP_LAM, POP_UNION, os.environ['CASMI_POP_DIR'])
SRC_BONUS, SRC_BITS = 0.5, 1   # documentation prior + bonus for depositor-source groups (pc_src_mask.npy, dataset v5)
os.environ['CASMI_SRC_BONUS'] = str(SRC_BONUS); os.environ['CASMI_SRC_BITS'] = str(SRC_BITS)
assert os.path.exists(os.path.join(os.environ['CASMI_POP_DIR'], 'pc_src_mask.npy')), 'pc_src_mask.npy missing'
print('depositor-source bonus', SRC_BONUS, 'bits', SRC_BITS, flush=True)
NP_BONUS = 1.0   # natural-product bonus: COCONUT, LOTUS or NPAtlas membership (pc_np.npy, popularity prior)
os.environ['CASMI_NP_BONUS'] = str(NP_BONUS)
assert os.path.exists(os.path.join(os.environ['CASMI_POP_DIR'], 'pc_np.npy')), 'pc_np.npy missing'
print('natural-product bonus', NP_BONUS, flush=True)
LOTUS_W = 0.5   # literature prior: ln(1 + LOTUS references) from the natural-product knowledge table
os.environ['CASMI_LOTUS_W'] = str(LOTUS_W)
assert (POP / 'aligned_public_priors.py').is_file(), 'aligned_public_priors.py missing'
assert sha256(POP / 'aligned_public_priors.py') == '89873c7312c16be2180d44bb9eb3c4e9ce19c821e74ab92bb41666ea0c0f9248', 'Untested aligned prior helper'
assert (POP / 'pc_lotus_refs.npy').is_file(), 'pc_lotus_refs.npy missing'
print('LOTUS literature prior', LOTUS_W, flush=True)
assert (POP / 'pc_lsynonyms.npy').is_file(), 'pc_lsynonyms.npy missing (popularity dataset of 19.10 or later)'
print('PubChem synonym prior 0.5 (pc_lsynonyms.npy)', flush=True)
for _n in ('delta_pc_mass.npy', 'growth_pc_mass.npy', 'delta_pc_lsynonyms.npy', 'growth_pc_lsynonyms.npy'):
    assert (POP / _n).is_file(), _n + ' missing (popularity dataset of 20.10 or later)'
import numpy as _np
print('PubChem supplements: legacy delta', len(_np.load(POP / 'delta_pc_mass.npy', mmap_mode='r')), 'rows + growth',
      len(_np.load(POP / 'growth_pc_mass.npy', mmap_mode='r')), 'rows', flush=True)
tag = f'cp{sys.version_info.major}{sys.version_info.minor}'
whl = [w for w in glob.glob('/kaggle/input/**/rdkit-*.whl', recursive=True) if tag in w and Path(w).name.startswith('rdkit-2026.3.3-')]
assert whl, 'Official RDKit 2026.3.3 wheel is missing'
print('rdkit wheel:', whl)
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-index', '--no-deps', whl[0]], capture_output=True, text=True)
print(r.stdout[-500:], r.stderr[-500:])
r.check_returncode()
import rdkit; print('rdkit', rdkit.__version__)
assert rdkit.__version__ == '2026.03.3'
V4CODE = os.path.dirname(os.path.dirname(find('casmi26-v4b-models/**/casmi/engine.py')))
V4MOD = os.path.dirname(find('casmi26-v4b-models/**/MANIFEST.json'))
V3CODE = os.path.dirname(os.path.dirname(find('casmi26-v3-models/**/casmi/engine.py')))
V3MOD = os.path.dirname(find('casmi26-v3-models/**/ranker_0.pkl'))
POOL_DIR = os.path.dirname(find('pool_meta.parquet'))
PC_DIR = os.path.dirname(find('pc_smiles.npy'))
COMP = os.path.dirname(find('test.parquet'))
MAN = json.load(open(os.path.join(V4MOD, 'MANIFEST.json')))
bad = []
for rel, h in sorted(MAN['files'].items()):
    p = os.path.join(V4CODE, rel[len('code/'):]) if rel.startswith('code/') else os.path.join(V4MOD, rel)
    if not os.path.exists(p) or sha256(p) != h:
        bad.append(rel)
assert not bad, f'dataset files differ from MANIFEST.json: {bad}'
print('V4CODE', V4CODE, '\nV4MOD', V4MOD, '\nV3CODE', V3CODE, '\nPOOL', POOL_DIR, '\nPC', PC_DIR, '\nCOMP', COMP)
print(f"{len(MAN['files'])} files match MANIFEST.json; families {MAN['families']}", f'{time.time()-T0:.0f}s')

'''Compatibility repair: select the simulator RDKit 2025.3.6 wheel by interpreter and platform tags, including bundled .whl.ice files. Fail before inference when no compatible build exists; preserve the main RDKit 2026.03.3 environment.'''

def simulator_rdkit_wheel(pkg):
    from pip._vendor.packaging.tags import sys_tags
    from pip._vendor.packaging.utils import parse_wheel_filename
    compatible = set(sys_tags())
    bundled = sorted(glob.glob(os.path.join(pkg, 'wheels', 'rdkit-2025.3.6-*.whl*')))
    external = sorted(glob.glob('/kaggle/input/**/rdkit-2025.3.6-*.whl', recursive=True))
    for path in bundled + external:
        name = os.path.basename(path).removesuffix('.ice')
        _, version, _, tags = parse_wheel_filename(name)
        if str(version) == '2025.3.6' and compatible.intersection(tags):
            return path
    raise FileNotFoundError(
        f'RDKit 2025.3.6 wheel compatible with Python {sys.version_info.major}.{sys.version_info.minor} '
        f'and this platform is required for ICEBERG/GLACIER; candidates: {bundled + external}')

_simulator_pkg = os.path.dirname(find('casmi26-iceberg/**/ice_runner.py'))
print('Simulator RDKit wheel:', simulator_rdkit_wheel(_simulator_pkg))
