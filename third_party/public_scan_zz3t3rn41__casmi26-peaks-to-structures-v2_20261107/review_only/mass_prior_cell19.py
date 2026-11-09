# ── v8 · mass prior table (MASS_PEN / MASS_PPM; empty when off) ──────────────────────────────────────────────────
import json, traceback
MASS_PEN, MASS_PPM, MASS_REPORT = {}, {}, dict(status='off in this preset')
try:
    if MASS_ON and globals().get('PIPELINE_DONE'):
        from rdkit import Chem, RDLogger
        from rdkit.Chem import Descriptors
        RDLogger.DisableLog('rdApp.*')
        # neutral mass from the competition's own precursor m/z and adduct, with the constants the band was measured with
        _ADD = {'[M+H]+': 1.007276, '[M-H]-': -1.007276, '[M+Na]+': 22.989218, '[M+NH4]+': 18.033823,
                '[M+K]+': 38.963158, '[M+CH2O2-H]-': 44.998201, '[M+Cl]-': 34.969402}
        _eq = pd.read_parquet(COMP / 'test.parquet', columns=['molecule_id', 'precursor_mz', 'adduct'])
        _eq['nm'] = pd.to_numeric(_eq.precursor_mz, errors='coerce') - _eq.adduct.map(_ADD)
        _eq = _eq[np.isfinite(_eq.nm) & (_eq.nm > 50)]
        _nm = {str(k): float(v) for k, v in _eq.groupby('molecule_id').nm.median().items()}
        _nf = pd.read_parquet(ROOT / 'neural_candidate_features.parquet', columns=['molecule_id', 'smiles'])
        _mass, _n_pen = {}, 0
        for _mid, _g in _nf.groupby('molecule_id', sort=False):
            _mid = str(_mid)
            nm = _nm.get(_mid)
            if not nm:
                continue
            pens, ppms = {}, {}
            for s in _g.smiles.astype(str):
                if s not in _mass:
                    m = Chem.MolFromSmiles(s)
                    _mass[s] = float(Descriptors.ExactMolWt(m)) if m is not None else None
                if _mass[s] is None:
                    continue
                ppm = (_mass[s] - nm) / nm * 1e6
                ppms[s] = ppm
                d = abs(ppm - MASS_CENTER)
                if d > MASS_FREE:
                    pens[s] = -MASS_W * min(1.0, (d - MASS_FREE) / (MASS_FULL - MASS_FREE))
                    _n_pen += 1
            MASS_PPM[_mid] = ppms
            if pens:
                MASS_PEN[_mid] = pens
        _all = [abs(v - MASS_CENTER) for d in MASS_PPM.values() for v in d.values()]
        MASS_REPORT = dict(status='on', molecules=len(MASS_PPM), candidates=len(_all), penalised=_n_pen,
                           beyond_5ppm=int(sum(x > 5 for x in _all)), lists_touched=len(MASS_PEN))
    elif MASS_ON:
        MASS_REPORT = dict(status='off: no pipeline answer in this run')
except Exception as exc:
    traceback.print_exc()
    MASS_PEN, MASS_PPM, MASS_REPORT = {}, {}, dict(status='off after an error', exception=repr(exc)[:300])
print('V8', V8, '| mass prior', json.dumps(MASS_REPORT))