# ── Variant M: rank 1 from the fragment check on the V2 order, ranks 2-25 from CUSTOM (busyaprime experiment) ────────
# Fragment check: Roman Tamrazov's Spectral Parallax, https://www.kaggle.com/code/romantamrazov/casmi-2026-spectral-parallax
# (cell 5 here is his, unpatched: it reads variants/submission_V2.csv, the input of his V17, the version with 0.472).
# CUSTOM 0.25/0.75: alex chilton, https://www.kaggle.com/code/alexchilton/casmi26-lb-0-472-leader-safe-ranks-2-25-at-0-75
# Rule, per molecule: P = submission.csv as the fragment check wrote it (V2 + physical), V = the V2 file, C = the CUSTOM
# file. A list is merged only when V[0] == C[0] and P holds the same candidates as C. If the check moved the leader
# (P[0] != V[0]), the answer is [P[0], V[0]] + the rest of C in C's order; otherwise it is C exactly. The check's
# adjacent swaps and lists it changed in any other way are dropped. On any error the CUSTOM file is restored.
# Merge rule from the judge panel of workflow wf_9745b485 (busyaprime, 2026-10-28).
import os, json, shutil, hashlib, traceback
import pandas as pd


def pxm_merge(physical, v2, custom):
    """physical, v2, custom: molecule_id, smiles frames in the same row order. Returns (frame, counts)."""
    assert list(physical.columns) == list(v2.columns) == list(custom.columns) == ['molecule_id', 'smiles']
    assert physical.molecule_id.tolist() == v2.molecule_id.tolist() == custom.molecule_id.tolist(), 'row order differs'
    rows = []
    counts = dict(rows=0, merged=0, leader_moves=0, skipped={}, skipped_leader_moves=0, moved_ids=[])
    for mid, ps, vs, cs in zip(custom.molecule_id, physical.smiles, v2.smiles, custom.smiles):
        p, v, c = ps.split(';'), vs.split(';'), cs.split(';')
        counts['rows'] += 1
        text = cs
        if v[0] != c[0]:
            reason = 'v2_custom_leader_differs'
        elif sorted(p) != sorted(c):
            reason = 'candidate_set_differs'
        else:
            reason = None
        if reason:
            counts['skipped'][reason] = counts['skipped'].get(reason, 0) + 1
            counts['skipped_leader_moves'] += int(p[0] != v[0])
        else:
            counts['merged'] += 1
            if p[0] != v[0]:
                new = [p[0], v[0]] + [s for s in c if s not in (p[0], v[0])]
                assert sorted(new) == sorted(c) and len(set(new)) == len(new), mid
                text = ';'.join(new)
                counts['leader_moves'] += 1
                counts['moved_ids'].append(mid)
        rows.append((mid, text))
    return pd.DataFrame(rows, columns=['molecule_id', 'smiles']), counts


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
    new, counts = pxm_merge(*frames)
    assert new.molecule_id.tolist() == SAMPLE_IDS
    assert new.smiles.str.split(';').map(len).between(1, 25).all()
    assert new.smiles.str.split(';').map(lambda a: all(bool(s) for s in a) and len(set(a)) == len(a)).all()
    tmp = ROOT / 'submission.merge.tmp'
    if new.smiles.tolist() == frames[2].smiles.tolist():
        shutil.copyfile(c_path, tmp)              # final = C exactly: the CUSTOM bytes, not a re-serialisation
    else:
        new.to_csv(tmp, index=False)
    out_sha = _pxm_sha(tmp)
    os.replace(tmp, sub_path)
    rep.update(status='applied', **counts, output_sha256=out_sha,
               output_equals_custom=out_sha == rep['input_sha256']['custom'])
    return rep


try:
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
    {k: MERGE_REPORT.get(k) for k in ('status', 'rows', 'merged', 'leader_moves', 'skipped', 'skipped_leader_moves',
                                      'output_equals_custom', 'output_sha256', 'exception') if k in MERGE_REPORT},
    default=str))
