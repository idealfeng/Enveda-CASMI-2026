# ===== heliosli: FRIGID + E1 on the second T4 (reports/c3_design_v0.md 11.20) =====
# Background only; the base below runs exactly as before on the first GPU. A watcher waits for the pinned pipeline's
# export (execution_receipt.json + submission.csv), takes each ranked molecule's rank-1 formula and runs frigid_runner.py
# with CUDA_VISIBLE_DEVICES=1 until FRIGID_DEADLINE: E1 fingerprint (mean over the molecule's positive spectra) ->
# FRIGID-base generation with the formula filter, one JSON line per molecule in frigid_e1.jsonl. The merge cell at the end
# reads whatever is finished. FRIGID's Python dependencies come as wheels in the dataset and go into their own site;
# torch, numpy, pandas and RDKit are the session's.
import subprocess, tarfile, textwrap
# The dataset's mount path depends on the image (v1: /kaggle/input/<slug>; this one mounts the competition under
# /kaggle/input/competitions/...), so it is found by its runner file, as the base finds its own files with rglob.
# Folders uploaded in tar mode may arrive as <name>.tar: those are unpacked into the working directory.
FRIGID_DS = ROOT / 'frigid_assets'
FRIGID_SITE = ROOT / 'frigid_site'
FRIGID_OUT = ROOT / 'frigid_e1.jsonl'
FRIGID_LOG = ROOT / 'frigid_e1.log'
FRIGID_DEADLINE = NB_T0 + 8.2 * 3600
FRIGID_PROC = None
try:
    _src = next(p.parent for p in Path('/kaggle/input').rglob('frigid_runner.py') if (p.parent / 'DLM.ckpt').exists())
    FRIGID_DS.mkdir(exist_ok=True)
    for _f in _src.iterdir():
        _dst = FRIGID_DS / _f.name
        if _f.suffix == '.tar' and _f.stem in ('wheels313', 'frigid_src', 'safes', 'patches'):
            with tarfile.open(_f) as _t:
                _t.extractall(FRIGID_DS)
        elif not _dst.exists():
            _dst.symlink_to(_f)
    print('[frigid] dataset at', _src, '->', sorted(p.name for p in FRIGID_DS.iterdir()))
    _whl = sorted(str(p) for p in (FRIGID_DS / 'wheels313').glob('*.whl'))
    assert _whl, 'no wheels in ' + str(FRIGID_DS / 'wheels313')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', '--quiet', '--target',
                    str(FRIGID_SITE)] + _whl, check=True)
    shutil.copy2(FRIGID_DS / 'patches/safe__init__.py', FRIGID_SITE / 'safe/__init__.py')
    shutil.copytree(FRIGID_DS / 'safes', ROOT / 'frigid_safes', dirs_exist_ok=True)   # the HF cache must be writable
    # Kaggle stores the cache's snapshot symlinks as 0-byte files (v2 died on an empty tokenizer.json): restore each one
    # from the blob it pointed to in the bundle.
    _hf = ROOT / 'frigid_safes/models--datamol-io--safe-gpt'
    for _n, _b in (('config.json', '5ddeb0c57ef8aefeeb6891293106c1ab0849113e'),
                   ('generation_config.json', 'de09b1521f1d2e98b57d8c1e1fa9f2587aaf5ef5'),
                   ('tokenizer.json', 'a7e35ca3822494f507c15f135dbaaf9f4be2a386')):
        _p = _hf / 'snapshots/3d5fa0988383e898d5ac5db7cd52bf715bc37061' / _n
        if not _p.exists() or _p.stat().st_size == 0:
            _p.unlink(missing_ok=True)
            shutil.copyfile(_hf / 'blobs' / _b, _p)
    _test = next(p for p in (COMP / 'test.parquet', Path('/kaggle/input/enveda-CASMI26-molecule-id-mass-spectra/test.parquet'),
                             Path('/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra/test.parquet')) if p.exists())
    (ROOT / 'frigid_watch.py').write_text(textwrap.dedent(f"""
        import importlib, json, subprocess, sys, time
        from pathlib import Path
        root, ds, deadline = Path({str(ROOT)!r}), Path({str(FRIGID_DS)!r}), {FRIGID_DEADLINE!r}
        while not (root / 'execution_receipt.json').exists():
            if time.time() > deadline:
                sys.exit('no pipeline export before the deadline')
            time.sleep(20)
        time.sleep(15)
        importlib.invalidate_caches()
        import pandas as pd
        from rdkit import Chem
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        sub = pd.read_csv(root / 'submission.csv')
        rows = []
        for m, s in zip(sub.molecule_id, sub.smiles):
            c = str(s).split(';')
            mol = Chem.MolFromSmiles(c[0]) if len(c) > 1 else None
            if mol is not None:
                rows.append((m, CalcMolFormula(mol)))
        pd.DataFrame(rows, columns=['molecule_id', 'formula']).to_csv(root / 'frigid_formulas.tsv', sep='\\t', index=False)
        print(json.dumps(dict(event='formulas', molecules=len(rows), t=round(time.time(), 1))), flush=True)
        sys.exit(subprocess.run([sys.executable, str(ds / 'frigid_runner.py'), '--test', {str(_test)!r},
                                 '--formulas', str(root / 'frigid_formulas.tsv'), '--out', {str(FRIGID_OUT)!r},
                                 '--assets', str(ds), '--deadline', str(deadline)]).returncode)
    """))
    _env = dict(os.environ, CUDA_VISIBLE_DEVICES='1', PYTHONPATH=str(FRIGID_SITE), HF_HUB_OFFLINE='1',
                HF_HUB_CACHE=str(ROOT / 'frigid_safes'))
    FRIGID_PROC = subprocess.Popen([sys.executable, str(ROOT / 'frigid_watch.py')], env=_env,
                                   stdout=open(FRIGID_LOG, 'w'), stderr=subprocess.STDOUT)
    print('[frigid] watcher started, pid', FRIGID_PROC.pid, '| deadline at %.2f h' % ((FRIGID_DEADLINE - NB_T0) / 3600))
except Exception as exc:
    print('[frigid] not started:', repr(exc)[:300])
