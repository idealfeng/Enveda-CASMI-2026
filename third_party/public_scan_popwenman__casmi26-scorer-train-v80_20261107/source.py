# casmi26 scorer train v80: our own copy of the second spectrum scorer that the 0.480 neural ensemble blends in.
# Recipe: bgunshui's casmi26-scorer-train-public (2026-11-01, since removed): Saner Turhaner's public training kit
# (sanpier/casmi-spectrum-model-v1, Apache-2.0) with its config verbatim except epochs 16 -> 80 and time budgets that
# never bind, plus the kit's prepare.py alias fix (normalized_smiles). Output: final_model.pt + config_used.json,
# the files the ensemble notebook looks for.
import json, sys, time, hashlib, shutil, subprocess, threading
from pathlib import Path

T0 = time.time()
log = lambda *a: print(*a, flush=True)
def heartbeat():
    while True:
        time.sleep(60); log(f'HEARTBEAT {round(time.time() - T0)}s')
threading.Thread(target=heartbeat, daemon=True).start()

import torch
log('ENV python', sys.version.split()[0], '| torch', torch.__version__, '| cuda', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')
try:
    from rdkit import rdBase
except ImportError:
    wh = sorted(Path('/kaggle/input').rglob('rdkit-*.whl')); assert wh, 'rdkit wheel dataset not attached'
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links', str(wh[0].parent), 'rdkit==2026.03.3'], check=True)
    from rdkit import rdBase
assert rdBase.rdkitVersion == '2026.03.3', rdBase.rdkitVersion

hits = sorted(Path('/kaggle/input').rglob('casmi_spectrum_model_v1/train.py')); assert len(hits) == 1, hits
kit = hits[0].parent; stage = Path('/kaggle/working/kit_staged'); shutil.copytree(kit, stage, dirs_exist_ok=True)
prep = stage / 'prepare.py'; src = prep.read_text()
OLD, NEW = "'smiles':['smiles','canonical_smiles']", "'smiles':['smiles','canonical_smiles','normalized_smiles']"
if OLD in src:
    prep.write_text(src.replace(OLD, NEW)); log('KIT_DELTA applied: normalized_smiles alias')
sys.path.insert(0, str(stage))
import prepare, train

cfg = json.loads((kit / 'config.json').read_text())
comp = sorted(Path('/kaggle/input').rglob('train.parquet')); assert len(comp) == 1, comp
cfg.update(train_path=str(comp[0]), work='/kaggle/working/cache_v80', output='/kaggle/working/casmi_spectrum_model_ours_v80',
           epochs=80, holdout_hours=5.0, refit_hours=6.0, external_paths=[])
log('CFG', json.dumps({k: cfg[k] for k in ('seed', 'epochs', 'batch_size', 'steps_per_epoch', 'patience', 'holdout_hours', 'refit_hours', 'width', 'layers', 'heads')}))
audit = prepare.prepare(cfg)
work, out = Path(cfg['work']), Path(cfg['output']); out.mkdir(parents=True, exist_ok=True)
shutil.copy2(work / 'data_audit.json', out / 'data_audit.json'); log('PREP_DONE', round(time.time() - T0), 's')
result = train.run(cfg)
log('TRAIN_RESULT', json.dumps(result))
(out / 'training_result.json').write_text(json.dumps(result, indent=2))
(out / 'config_used.json').write_text(json.dumps(cfg, indent=2))
for name in ('model.py', 'features.py'):
    shutil.copy2(kit / name, out / name)
for p in sorted(out.iterdir()):
    log('ARTIFACT', p.name, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()[:16])
shutil.rmtree(work, ignore_errors=True)
log(f'SCORER_V80_DONE {round(time.time() - T0)}s')
