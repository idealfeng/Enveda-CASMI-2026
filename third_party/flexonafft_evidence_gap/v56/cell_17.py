# ── Final layer: documentation prior on ranks 2-25, metric-exact dedup, outsider fill ─────────
# Weights and prior table follow baidalinadilzhan's MIDX notebook; unlike MIDX it runs *after* the unchanged m1
# merge, so m1's guards (shared V2/CUSTOM leader, same candidate set) stay in force, and it never re-adds a
# duplicate metric identity.
import os, glob, json, shutil, hashlib, traceback
from functools import lru_cache
import numpy as np
import pandas as pd


def _fl_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _fl_prior():
    pop, spec, nat = {}, {}, {}
    hits = sorted(glob.glob(str(INPUT / '**/pool_popularity.csv'), recursive=True))
    if hits:
        cols = ['inchikey14', 'pop', 'src_spectral_library', 'np_coconut', 'np_lotus', 'src_natural_product']
        p = pd.read_csv(hits[0], usecols=cols)
        pop = dict(zip(p.inchikey14, p['pop'].astype(float)))
        spec = dict(zip(p.inchikey14, p.src_spectral_library.astype(float)))
        nat = dict(zip(p.inchikey14, (p.np_coconut.astype(bool) | p.np_lotus.astype(bool)
                                      | p.src_natural_product.astype(bool)).astype(int)))
    return pop, spec, nat, (hits[0] if hits else None)


def _final_layer():
    rep = dict(status='disabled')
    if not FINAL_LAYER:
        return rep
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    taut = rdMolStandardize.TautomerEnumerator()
    idmap = identity_map()

    @lru_cache(maxsize=200000)
    def k14(s):
        k = idmap.get(s)
        if isinstance(k, str) and len(k) >= 14:
            return k[:14]
        try:
            m = Chem.MolFromSmiles(str(s))
            if m is None:
                return ''
            Chem.RemoveStereochemistry(m)
            return Chem.MolToInchiKey(taut.Canonicalize(m))[:14]
        except Exception:
            return ''

    sub = ROOT / 'submission.csv'
    cur = pd.read_csv(sub, dtype=str, keep_default_na=False)
    cus = pd.read_csv(ROOT / 'variants/submission_CUSTOM.csv', dtype=str, keep_default_na=False)
    assert cur.molecule_id.tolist() == cus.molecule_id.tolist() == SAMPLE_IDS
    rep['input_sha256'] = _fl_sha(sub)

    nf = pd.read_parquet(ROOT / 'neural_candidate_features.parquet')
    lib_max = {str(m): float(v) for m, v in nf.groupby('molecule_id', sort=False).library_max.max().items()}
    info = {}
    for mid, g in nf.groupby('molecule_id', sort=False):
        # Same molecules and tie order as consensus.build_variants; inactive rows keep the CUSTOM (= baseline) order.
        g = g.sort_values('baseline_rank', kind='stable')
        if not (g.neural_ok.astype(bool).all() and ('processed' not in g or bool(g.processed.iloc[0]))):
            continue
        sc = pd.to_numeric(g.neural_score, errors='coerce').to_numpy()
        if not np.isfinite(sc).all():
            continue
        order = np.argsort(-sc, kind='stable')
        nr = np.empty(len(g), dtype=int)
        nr[order] = np.arange(1, len(g) + 1)
        info[str(mid)] = {s: (int(br), int(n)) for s, br, n in zip(g.smiles, g.baseline_rank, nr)}
    outs = {}
    op = ROOT / 'outsider_neural_features.parquet'
    if OUTSIDER_FILL and op.is_file():
        of = pd.read_parquet(op)
        s = pd.to_numeric(of.neural_score, errors='coerce')
        of = of[of.neural_ok.astype(bool) & np.isfinite(s)].assign(_s=s)
        for m, g in of.groupby('molecule_id', sort=False):
            outs[str(m)] = g.sort_values('_s', ascending=False, kind='stable').smiles.astype(str).tolist()
    pop, spec, nat, prior_file = _fl_prior()
    rep['prior_file'] = prior_file
    w_mid = float(CUSTOM['w_mid'])

    counts = dict(rows=0, reordered=0, pinned=0, dup_removed=0, outsider_fills=0, top1_changed=0)
    out = []
    for mid, cs, ccs in zip(cur.molecule_id, cur.smiles, cus.smiles):
        lst, c = cs.split(';'), ccs.split(';')
        counts['rows'] += 1
        leader, rest = lst[0], lst[1:]
        pinned = []
        if leader != c[0] and c[0] in rest:      # leader moved: keep the CUSTOM leader at rank 2
            pinned = [c[0]]
            rest = [x for x in rest if x != c[0]]
            counts['pinned'] += 1
        ci = info.get(str(mid), {})
        hit = lib_max.get(str(mid), 0.0) >= LIB_HIT_GATE
        if ci and len(rest) > 1:
            pos = {s: i for i, s in enumerate(rest)}

            def score(s):
                if s in ci:
                    br, nr = ci[s]
                    k = k14(s)
                    return (1.0 / (3.0 + br) + w_mid / (3.0 + nr) + POP_W * float(pop.get(k, 0.0)) / 20.0
                            + (SPEC_W if hit else 0.0) * float(spec.get(k, 0.0)) + NP_W * float(nat.get(k, 0.0)))
                return 1.0 / (3.0 + len(pinned) + 2 + pos[s])   # unknown evidence: its current position
            new_rest = sorted(rest, key=lambda s: (-score(s), pos[s]))
            counts['reordered'] += int(new_rest != rest)
            rest = new_rest
        res, seen = [], set()
        for s in [leader] + pinned + rest:
            k = k14(s) or ('raw:' + s)
            if not s or k in seen:
                counts['dup_removed'] += int(bool(s))
                continue
            seen.add(k)
            res.append(s)
        for s in outs.get(str(mid), []):
            if len(res) >= 25:
                break
            k = k14(s)
            if not k or k in seen or s in res:
                continue
            seen.add(k)
            res.append(s)
            counts['outsider_fills'] += 1
        res = res[:25]
        assert res[0] == leader and len(set(res)) == len(res) >= 1, mid
        out.append((mid, ';'.join(res)))
    new = pd.DataFrame(out, columns=['molecule_id', 'smiles'])
    assert new.molecule_id.tolist() == SAMPLE_IDS
    assert new.smiles.str.split(';').map(lambda a: 1 <= len(a) <= 25 and all(a) and len(set(a)) == len(a)).all()
    tmp = ROOT / 'submission.final.tmp'
    new.to_csv(tmp, index=False)
    os.replace(tmp, sub)
    rep.update(status='applied', **counts, changed_rows=int((new.smiles != cur.smiles).sum()),
               output_sha256=_fl_sha(sub))
    return rep


shutil.copy2(ROOT / 'submission.csv', ROOT / 'submission_before_final_layer.csv')
try:
    if not PIPELINE_DONE and not IS_RERUN and COMMIT_MODE == 'fast':
        FINAL_REPORT = {'status': 'skipped_fast_commit'}
    else:
        FINAL_REPORT = _final_layer()
except Exception as exc:
    traceback.print_exc()
    shutil.copy2(ROOT / 'submission_before_final_layer.csv', ROOT / 'submission.csv')
    FINAL_REPORT = {'status': 'restored_after_error', 'exception': repr(exc)[:600]}
(ROOT / 'final_layer_report.json').write_text(json.dumps(FINAL_REPORT, indent=2, default=str))

final = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
assert list(final.columns) == ['molecule_id', 'smiles']
assert final.molecule_id.tolist() == SAMPLE_IDS and final.molecule_id.is_unique
assert final.smiles.str.split(';').map(lambda a: 1 <= len(a) <= 25 and all(a) and len(set(a)) == len(a)).all()
print('SUBMISSION READY', ROOT / 'submission.csv', 'FINAL LAYER', json.dumps(FINAL_REPORT, default=str))
