"""PubChem-only channel for the final submission (runs in its own process so its casmi package
(S1 snapshot, FPNet A+B) never collides with the v1 engine's casmi package).

Per molecule: z = z_AB + 0.5 * mean(z_fold0..z_fold4), with the unchanged molecule views;
best_pool_fz = max f.z over the pool window (+-10 ppm, fallback 30 ppm) with the same z (as P1 logits.py);
PubChem-only list = probe_core2.probe_one (top 25 by f.z, keys not in the pool) with f.z values and score keys.
Writes a json {molecule_id: {pc, pc_fz, pc_keys, best_pool_fz, target}}.
usage: python pc_runner.py <v3_code_dir> <v3_models_dir> <pool_dir> <pubchem_dir> <test_parquet> <out_json> <n_workers> [max_mols]
"""
import os, sys, json, time
import numpy as np, pandas as pd

if __name__ == '__main__':
    V3CODE, V3MOD, POOL_DIR, PC_DIR, TEST, OUT, NW = sys.argv[1:8]
    MAXM = int(sys.argv[8]) if len(sys.argv) > 8 else 0
    NW = int(NW)
    sys.path.insert(0, V3CODE); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import torch, glob
    import probe_core2 as pc
    from casmi import fpnet, chem
    T0 = time.time()
    models = sorted(glob.glob(os.path.join(V3MOD, 'fpnet_*.pt')))
    assert len(models) == 2, models
    fold0 = os.environ['CASMI_FPNET_FOLD0']
    assert os.path.isfile(fold0), fold0
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    folds = json.loads(os.environ['CASMI_FPNET_FOLDS'])
    pinned_hashes = {'fpnet_fold0.pt': 'ddf6eaaa8e541a16e3f0357ed30f0346e529054f75d5619aedb6024dcb1bd7f0', 'fpnet_fold1.pt': '1739d5683fa94fd73fe3b37db98ac364cb5dfdc22ad5bea9789be9c48d7cadc4', 'fpnet_fold2.pt': '257062cb6ece333226027de6e313792e7b364517adf42a05e0df950b8e27bbe2', 'fpnet_fold3.pt': 'ac61125ef34415d857d58a115e017e0af2aede044e3a5d524029dd1364cbd58c', 'fpnet_fold4.pt': 'ad0b2a43343287f7deb4334c4ad766e8aa236d7f0bbeb91e3702910ee49aabe7'}
    assert len(folds) == 5 and [os.path.basename(p) for p in folds] == list(pinned_hashes), folds
    assert all(os.path.isfile(p) for p in folds), folds
    import hashlib
    stage = os.path.dirname(fold0)
    manifest = json.load(open(os.path.join(stage, 'MANIFEST_FIVEFOLD.json')))
    validation = json.load(open(os.path.join(stage, 'FIVEFOLD_VALIDATION.json')))
    assert manifest['complete'] and manifest['updates_per_fold'] == 82855 and manifest['bits'] == 10226
    assert validation['passed'] and validation['recipe_replay']['passed'] and validation['fold0_metric_replay']['passed']
    hashes = {item['file']: item['sha256'] for item in manifest['files']}
    for k, path in enumerate(folds):
        assert json.load(open(os.path.join(stage, f'check_inputs_fold{k}.json')))['passed']
        h = hashlib.sha256()
        with open(path, 'rb') as checkpoint_file:
            for chunk in iter(lambda: checkpoint_file.read(4 << 20), b''):
                h.update(chunk)
        assert h.hexdigest() == hashes[os.path.basename(path)] == pinned_hashes[os.path.basename(path)], path
    # Explicit groups: z_AB + 0.5 * mean(z_fold0, ..., z_fold4).
    # Keep the original A+B coefficient and original 150/600 raw-margin units.
    class ResidualBank:
        def __init__(self):
            self.ab = fpnet.ModelBank(models, device=dev)
            self.folds = fpnet.ModelBank(folds, device=dev)
            self.nbits = self.ab.nbits
            assert self.nbits == self.folds.nbits
        def logits_el(self, items):
            za, _ = self.ab.logits_el(items)
            zf, _ = self.folds.logits_el(items)
            return za + 0.5 * zf, None
    bank = ResidualBank()
    for k, path in enumerate(folds):
        print('FPNET_FOLD_LOADED', k, os.path.basename(path), 'sha256=' + pinned_hashes[os.path.basename(path)], flush=True)
    print('FPNET_ENSEMBLE_LOADED ab_models=2 fold_models=5 rule=z_AB+0.5*mean(z_fold0..z_fold4)', flush=True)
    bits = np.load(os.path.join(POOL_DIR, 'fp_bits.npy')); nbits = len(bits)
    assert bank.nbits == nbits, (bank.nbits, nbits)
    assert np.array_equal(bits, np.load(os.path.join(os.path.dirname(fold0), 'fp_bits.npy'))), 'Fingerprint bit order differs'
    for checkpoint in folds:
        assert np.array_equal(bits, np.load(os.path.join(os.path.dirname(checkpoint), 'fp_bits.npy'))), checkpoint
    pmass = pd.read_parquet(os.path.join(POOL_DIR, 'pool_meta.parquet'), columns=['mass']).mass.values.astype(np.float64)
    assert np.all(np.diff(pmass) >= 0), 'pool not mass-sorted'
    pfp = np.load(os.path.join(POOL_DIR, 'pool_fp.npy'), mmap_mode='r')
    te = pd.read_parquet(TEST)
    te['nm'] = chem.neutral_mass(te.precursor_mz.values.astype(np.float64), te.adduct.values)
    tasks, extra = [], {}
    groups = list(te.groupby('molecule_id', sort=False))
    if MAXM:
        groups = groups[:MAXM]
    for mid, sub in groups:
        nms = sub.nm.values[np.isfinite(sub.nm.values)]
        if not len(nms):
            continue
        target = float(np.median(nms))
        spectra = []
        for r in sub.itertuples():
            ce = r.collision_energy_ev
            ce_arr = np.atleast_1d(np.asarray(ce, dtype=float)) if ce is not None else np.zeros(0)
            spectra.append(dict(mz=np.asarray(r.ms2_mzs, np.float64), it=np.asarray(r.ms2_normalized_intensities, np.float64),
                                mode=1 if r.ionization_mode == 'positive' else -1, adduct=r.adduct,
                                prec=float(r.precursor_mz), ce=float(ce_arr.mean()) if len(ce_arr) else np.nan,
                                ce_n=int(len(ce_arr)) if len(ce_arr) else 1))
        spectra = spectra[:16]
        try:
            z = pc.molecule_logits(bank, spectra)
        except Exception as e:
            print('ERROR logits', mid, repr(e), flush=True); z = None
        if z is None:
            continue
        tol = target * 10e-6
        a = np.searchsorted(pmass, target - tol, 'left'); b = np.searchsorted(pmass, target + tol, 'right')
        if b <= a:
            tol = target * 30e-6
            a = np.searchsorted(pmass, target - tol, 'left'); b = np.searchsorted(pmass, target + tol, 'right')
        if b > a:
            F = np.unpackbits(np.asarray(pfp[a:b]), axis=1)[:, :nbits].astype(np.float64)
            best = float((F @ z.astype(np.float64)).max())
        else:
            best = float('nan')
        extra[mid] = dict(best_pool_fz=best, target=target)
        tasks.append((mid, target, z))
    del bank; torch.cuda.empty_cache()
    print(f'logits for {len(tasks)} molecules {time.time()-T0:.0f}s', flush=True)
    res = {}
    import multiprocessing as mp
    ctx = mp.get_context('fork' if sys.platform != 'win32' else 'spawn')
    with ctx.Pool(NW, initializer=pc.init_worker, initargs=(PC_DIR, os.path.join(POOL_DIR, 'fp_bits.npy'),
                                                            os.path.join(POOL_DIR, 'pool_meta.parquet'), V3CODE)) as P:
        for k, (mid, smis, fzs, keys, d) in enumerate(P.imap_unordered(pc.probe_one, tasks, chunksize=1)):
            res[mid] = dict(pc=smis, pc_fz=fzs, pc_keys=keys, fz_top=d.get('fz_top'), S=d.get('S'), top_pop=d.get('top_pop', 0.0), **extra[mid])
            if (k + 1) % 25 == 0 or k + 1 == len(tasks):
                print(f'  pubchem {k+1}/{len(tasks)} {time.time()-T0:.0f}s', flush=True)
    json.dump(res, open(OUT, 'w'))
    print('pc_runner done', len(res), f'{time.time()-T0:.0f}s', flush=True)
