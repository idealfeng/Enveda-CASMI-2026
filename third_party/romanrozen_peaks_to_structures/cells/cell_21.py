LIB_MAX = {}
# ── Variant M: rank 1 from fragment check on V2, ranks 2-25 from CUSTOM + DocPrior + In-Pool Dedup ────────
import os, json, shutil, hashlib, traceback, glob
from pathlib import Path
from functools import lru_cache
import pandas as pd
import numpy as np


def _load_pop_prior(root, input_root):
    """Load PubChem documentation prior and spectral annotations for InChIKey14 lookups."""
    pop_map, spec_map, np_map = {}, {}, {}
    try:
        hits = sorted(glob.glob(str(input_root / '**/pool_popularity.csv'), recursive=True))
        if hits:
            cols = ['inchikey14', 'pop', 'src_spectral_library', 'np_coconut', 'np_lotus', 'src_natural_product']
            p_df = pd.read_csv(hits[0], usecols=cols)
            pop_map = dict(zip(p_df['inchikey14'], p_df['pop']))
            spec_map = dict(zip(p_df['inchikey14'], p_df['src_spectral_library']))
            np_map = dict(zip(p_df['inchikey14'], (p_df['np_coconut'] | p_df['np_lotus'] | p_df['src_natural_product']).astype(int)))
            print(f'Documentation Prior: loaded {len(p_df)} pool records from {Path(hits[0]).name}')
    except Exception as e:
        print(f'Note: pool_popularity lookup exception ({e}); proceeding with neutral prior.')
    return pop_map, spec_map, np_map


def pxm_merge(physical, v2, custom, pop_map=None, spec_map=None, np_map=None, nf_evidence=None):
    """physical, v2, custom: molecule_id, smiles frames in the same row order. Returns (frame, counts)."""
    assert list(physical.columns) == list(v2.columns) == list(custom.columns) == ['molecule_id', 'smiles']
    assert physical.molecule_id.tolist() == v2.molecule_id.tolist() == custom.molecule_id.tolist(), 'row order differs'
    rows = []
    counts = dict(rows=0, merged=0, leader_moves=0, ranks_reordered=0, skipped={}, skipped_leader_moves=0, moved_ids=[])
    
    pop_map = pop_map or {}
    spec_map = spec_map or {}
    np_map = np_map or {}
    evidence_by_mid = nf_evidence or {}

    for mid, ps, vs, cs in zip(custom.molecule_id, physical.smiles, v2.smiles, custom.smiles):
        p, v, c = ps.split(';'), vs.split(';'), cs.split(';')
        counts['rows'] += 1
        
        # Variant M Leader Rule (Strictly Locked Rank 1):
        # If the fragment check on V2 identified a superior physical bond cleavage leader (p[0] != v[0]):
        # Place p[0] at Rank 1, followed by the high-resolution CUSTOM order.
        if p[0] != v[0]:
            leader = p[0]
            rest = [s for s in c if s != p[0]]
            counts['merged'] += 1
            counts['leader_moves'] += 1
            counts['moved_ids'].append(mid)
        else:
            leader = c[0]
            rest = c[1:]
            counts['merged'] += 1

        # Re-rank Ranks 2–25 by Documentation Prior + Spectral Library + Natural Product Bonus
        cinfo = evidence_by_mid.get(str(mid), {})
        lib_hit = float(LIB_MAX.get(str(mid), 0.0)) >= LIB_HIT_GATE
        if rest and cinfo:
            def _score_cand(s):
                if s in cinfo:
                    br, nr, k14 = cinfo[s]
                    p_val = float(pop_map.get(k14, 0.0))
                    s_val = float(spec_map.get(k14, 0.0))
                    np_val = float(np_map.get(k14, 0.0))
                    return 1.0 / (3.0 + br) + 0.75 / (3.0 + nr) + POP_W * (p_val / 20.0) + (SPEC_W if lib_hit else 0.0) * s_val + NP_W * np_val + TAX_BONUS.get(str(mid), {}).get(s, 0.0)   # v4: taxonomic consistency (0.0 when off)
                idx = c.index(s) if s in c else 25
                return 1.0 / (3.0 + idx + 1)
            
            old_rest = list(rest)
            rest.sort(key=_score_cand, reverse=True)
            if rest != old_rest:
                counts['ranks_reordered'] += 1
            
        if PIN_OLD_LEADER and p[0] != v[0] and v[0] in rest and rest[0] != v[0]:
            rest = [v[0]] + [x for x in rest if x != v[0]]
            counts['old_leader_pinned'] = counts.get('old_leader_pinned', 0) + 1
        rows.append((mid, [leader] + rest))
    return rows, counts


# ---- run (everything above is definitions) ----
def _pxm_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _pxm_main():
    rep = dict(status='disabled')
    if not globals().get('FRAG_ON_V2', False):
        return rep
    assert not globals().get('PROVENANCE', False), 'variant M is defined without the provenance reranker'
    sub_path = ROOT / 'submission.csv'
    v_path, c_path = ROOT / 'variants/submission_V2.csv', ROOT / 'variants/submission_CUSTOM.csv'
    rep['input_sha256'] = dict(physical_v2=_pxm_sha(sub_path), v2=_pxm_sha(v_path), custom=_pxm_sha(c_path))
    diag = globals().get('PARALLAX_DIAGNOSTICS') or {}
    rep['overlay'] = {k: diag[k] for k in ('status', 'error', 'control_sha256', 'submission_sha256', 'changed_rows',
                                           'top1_changed', 'tail_changed', 'adjacent_swaps') if k in diag}
    if diag.get('control_sha256'):
        assert diag['control_sha256'] == rep['input_sha256']['v2'], 'the fragment check did not read the V2 file'
    if diag.get('submission_sha256'):
        assert diag['submission_sha256'] == rep['input_sha256']['physical_v2'], \
            'submission.csv is not the file the fragment check wrote'
    frames = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in (sub_path, v_path, c_path)]
    for f in frames:
        assert list(f.columns) == ['molecule_id', 'smiles'] and f.molecule_id.tolist() == SAMPLE_IDS, \
            'an input file differs from sample_submission'

    from rdkit import Chem

    from rdkit.Chem.MolStandardize import rdMolStandardize
    _TAUT = rdMolStandardize.TautomerEnumerator()
    _IDMAP = identity_map()

    @lru_cache(maxsize=100000)
    def _to_k14(s):
        k = _IDMAP.get(s)
        if isinstance(k, str) and k:
            return k
        try:
            m = Chem.MolFromSmiles(str(s))
            if m is None:
                return ''
            Chem.RemoveStereochemistry(m)
            return Chem.MolToInchiKey(_TAUT.Canonicalize(m))[:14]
        except Exception:
            return ''

    global LIB_MAX
    LIB_MAX = {}
    out_by_mid = {}
    try:
        _nf = pd.read_parquet(ROOT / 'neural_candidate_features.parquet', columns=['molecule_id', 'library_max'])
        LIB_MAX = {str(m): float(v) for m, v in _nf.groupby('molecule_id', sort=False).library_max.max().items()}
        _op = ROOT / 'outsider_neural_features.parquet'
        if OUTSIDER_FILL and _op.is_file():
            _of = pd.read_parquet(_op)
            _sc = pd.to_numeric(_of.neural_score, errors='coerce')
            _of = _of[_of.neural_ok.astype(bool) & np.isfinite(_sc)].assign(_s=_sc)
            for _m, _g in _of.groupby('molecule_id', sort=False):
                out_by_mid[str(_m)] = _g.sort_values('_s', ascending=False, kind='stable').smiles.astype(str).tolist()
    except Exception as e:
        print(f'Note: final-layer inputs exception ({e}); gate off, no outsider fill')
    rep['lib_hit_molecules'] = int(sum(v >= LIB_HIT_GATE for v in LIB_MAX.values()))

    # Load documentation prior and candidate evidence
    pop_map, spec_map, np_map = _load_pop_prior(ROOT, INPUT)
    evidence_by_mid = {}
    nf_path = ROOT / 'neural_candidate_features.parquet'
    if nf_path.is_file():
        try:
            nf = pd.read_parquet(nf_path)
            for mid, g in nf.groupby('molecule_id', sort=False):
                order = np.argsort(-g['neural_score'].to_numpy(), kind='stable')
                nranks = np.empty(len(g), dtype=int)
                nranks[order] = np.arange(1, len(g) + 1)
                cand_info = {}
                for s, br, nr, mk in zip(g['smiles'], g['baseline_rank'], nranks, g['metric_key']):
                    k14 = mk if (isinstance(mk, str) and len(mk) == 14) else _to_k14(s)
                    cand_info[s] = (int(br), int(nr), k14)
                evidence_by_mid[str(mid)] = cand_info
        except Exception as e:
            print(f'Note: neural evidence indexing exception ({e})')

    merged_tuples, counts = pxm_merge(*frames, pop_map=pop_map, spec_map=spec_map, np_map=np_map, nf_evidence=evidence_by_mid)

    # In-Pool InChIKey14 Skeletal Deduplication
    reclaimed_smiles = []
    dedup_swaps = 0
    outsider_fills = 0
    for (mid, prim_list), c_s, v_s in zip(merged_tuples, frames[2].smiles, frames[1].smiles):
        seen_k = set()
        res = []
        # 1. Primary order (Variant M merged + DocPrior reordered ranks 2-25)
        for s in prim_list:
            if not s: continue
            k = _to_k14(s)
            if not k or k not in seen_k:
                if k: seen_k.add(k)
                res.append(s)
                if len(res) >= 25: break

        # 2. In-pool backfill strictly from c and v (no outside distractors)
        if len(res) < 25:
            for extra in (c_s, v_s):
                for s in extra.split(';'):
                    if not s or s in res: continue
                    k = _to_k14(s)
                    if not k or k not in seen_k:
                        if k: seen_k.add(k)
                        res.append(s)
                        dedup_swaps += 1
                        if len(res) >= 25: break
                if len(res) >= 25: break

        # 2b. Empty slots: scored outside candidates with a new metric identity, best neural score first
        if len(res) < 25:
            for s in out_by_mid.get(str(mid), []):
                if s in res:
                    continue
                k = _to_k14(s)
                if not k or k in seen_k:
                    continue
                seen_k.add(k)
                res.append(s)
                outsider_fills += 1
                if len(res) >= 25:
                    break

        # 3. Fallback fill if still < 25
        if len(res) < 25:
            for extra in (prim_list, c_s.split(';'), v_s.split(';')):
                for s in extra:
                    if s and s not in res:
                        res.append(s)
                        if len(res) >= 25: break
                if len(res) >= 25: break

        reclaimed_smiles.append(';'.join(res[:25]))

    new = pd.DataFrame({'molecule_id': [m for m, _ in merged_tuples], 'smiles': reclaimed_smiles})
    rep['dedup_swaps'] = dedup_swaps
    rep['outsider_fills'] = outsider_fills
    rep['old_leader_pinned'] = counts.get('old_leader_pinned', 0)
    print(f'Final layer: outsider fills {outsider_fills}, old leader pinned {rep["old_leader_pinned"]}, '
          f'library-hit molecules {rep.get("lib_hit_molecules")}, POP_W {POP_W}, NP_W {NP_W}')
    rep['ranks_reordered'] = counts['ranks_reordered']
    print(f'InChIKey14 Deduplication: reclaimed {dedup_swaps} redundant isomer slots!')
    print(f'Documentation Prior: reordered secondary ranks in {counts["ranks_reordered"]} / {counts["rows"]} rows.')

    assert new.molecule_id.tolist() == SAMPLE_IDS
    assert new.smiles.str.split(';').map(len).between(1, 25).all()
    assert new.smiles.str.split(';').map(lambda a: all(bool(s) for s in a) and len(set(a)) == len(a)).all()
    tmp = ROOT / 'submission.merge.tmp'
    new.to_csv(tmp, index=False)
    out_sha = _pxm_sha(tmp)
    os.replace(tmp, sub_path)
    rep.update(status='applied', **counts, output_sha256=out_sha,
               output_equals_custom=out_sha == rep['input_sha256']['custom'])
    return rep


try:
    if not PIPELINE_DONE and not IS_RERUN and COMMIT_MODE == 'fast':
        MERGE_REPORT = {'status': 'skipped_fast_commit'}
    else:
        MERGE_REPORT = _pxm_main()
except Exception as exc:
    traceback.print_exc()
    MERGE_REPORT = dict(status='restored_custom_after_error', exception=repr(exc)[:600])
    try:
        _tmp = ROOT / 'submission.merge.tmp'
        shutil.copyfile(ROOT / 'variants/submission_CUSTOM.csv', _tmp)
        os.replace(_tmp, ROOT / 'submission.csv')
        MERGE_REPORT['output_sha256'] = _pxm_sha(ROOT / 'submission.csv')
    except Exception as exc2:
        traceback.print_exc()
        MERGE_REPORT['restore_error'] = repr(exc2)[:300]
try:
    _tmp = ROOT / 'merge_report.json.tmp'
    _tmp.write_text(json.dumps(MERGE_REPORT, indent=2, default=str))
    os.replace(_tmp, ROOT / 'merge_report.json')
except Exception:
    traceback.print_exc()

final = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
assert list(final.columns) == ['molecule_id', 'smiles']
assert final.molecule_id.tolist() == SAMPLE_IDS and final.molecule_id.is_unique
assert final.smiles.str.split(';').map(len).between(1, 25).all()
assert final.smiles.str.split(';').map(lambda a: all(bool(s) for s in a) and len(set(a)) == len(a)).all()
print('SUBMISSION READY:', ROOT / 'submission.csv', 'molecules', len(final), 'MERGE', json.dumps(
    {k: MERGE_REPORT.get(k) for k in ('status', 'rows', 'merged', 'leader_moves', 'ranks_reordered', 'dedup_swaps',
                                      'output_equals_custom', 'outsider_fills', 'old_leader_pinned', 'lib_hit_molecules', 'output_sha256', 'exception') if k in MERGE_REPORT},
    default=str))
