"""Audit cached forward coverage and prepare Na-only GL evidence, without inference.

Only the existing 48-query development run is read. Public pretrained exposure
is retained as an explicit limitation. Candidate scope never comes from truth.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PACKAGE = ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier'
EXPECTED_CKPT = '9192e4c2eeafe83317d5a2c2641e1fc4d68934488757a4faafeb66f2ab397a12'


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def finite(value): return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
def inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()): raise ValueError('All artifacts must stay in D: workspace')
    return path
def covered(spectrum):
    mode = spectrum.get('mode')
    positive = mode == 1 or isinstance(mode, str) and mode.lower() in ('positive', 'pos', '+', '1')
    return bool(positive and spectrum.get('adduct') in ('[M+H]+', '[M+Na]+'))
def spectrum_digest(spectrum):
    return hashlib.sha256(json.dumps(spectrum, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=ROOT/'runs/validation_flex_c2_20261105d')
    parser.add_argument('--output', type=Path, default=ROOT/'reports/forward_coverage_20261108')
    parser.add_argument('--with-dev-truth', action='store_true')
    parser.add_argument('--inspect-checkpoint', action='store_true', help='CPU weights-only metadata; no model instantiated')
    args = parser.parse_args()
    base, output = inside(args.run), inside(args.output)
    if output.exists() and any(output.iterdir()): raise FileExistsError('Choose a new empty output directory')
    import pyarrow as pa
    import pyarrow.parquet as pq
    from validation.metric import assert_official_rdkit, identity
    from rdkit import RDLogger
    RDLogger.DisableLog('rdApp.*')
    rdkit = assert_official_rdkit()
    paths = [base/name for name in ('validation_candidate_stages.parquet', 'frozen_candidate_evidence.parquet',
        'neural_candidate_features.parquet', 'outsider_evidence.parquet', 'effective_query_spectra.parquet',
        'validation_e1_candidates.jsonl', 'validation_e2_candidates.jsonl', 'submission.csv',
        'gl_work/gl_in.json', 'gl_work/gl_out.json', 'gl_work/gl_out.json.meta.json',
        'ice_work/ice_in.json', 'ice_work/ice_out.json', 'ice_work/ice_out.json.meta.json')]
    for path in paths:
        if not path.is_file(): raise FileNotFoundError(path)
    evidence = pq.read_table(base/'frozen_candidate_evidence.parquet').to_pylist()
    active = list(dict.fromkeys(str(row['molecule_id']) for row in evidence))
    if len(active) != 48: raise ValueError('This frozen audit must contain exactly the existing 48 dev queries')
    valid_ids = set(active)
    rows_by_query = defaultdict(list)
    for row in evidence: rows_by_query[str(row['molecule_id'])].append(row)
    stages = defaultdict(lambda: defaultdict(list))
    for row in pq.read_table(base/'validation_candidate_stages.parquet').to_pylist():
        if str(row['molecule_id']) not in valid_ids: raise ValueError('Unexpected query in stage file')
        stages[str(row['molecule_id'])][row['stage']].append(row['smiles'])
    for name in ('validation_e1_candidates.jsonl', 'validation_e2_candidates.jsonl'):
        with (base/name).open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if str(row['molecule_id']) not in valid_ids: raise ValueError('Unexpected query in retrieval file')
                stages[str(row['molecule_id'])][row['stage']].append(row['smiles'])
    inputs = {engine: {str(item['mid']): item for item in read(base/f'{engine}_work/{engine}_in.json')}
              for engine in ('gl', 'ice')}
    scores = {engine: read(base/f'{engine}_work/{engine}_out.json') for engine in ('gl', 'ice')}
    meta = {engine: read(base/f'{engine}_work/{engine}_out.json.meta.json') for engine in ('gl', 'ice')}
    for group in list(inputs.values())+list(scores.values()):
        if set(group)-valid_ids: raise ValueError('Unexpected query in forward artifacts')
    trace_input = ROOT/'runs/exp003_gl_trace_full_20261106/input.json'
    if sha(trace_input) != sha(base/'gl_work/gl_in.json'): raise ValueError('EXP003 GL input differs from this run')
    paths.append(trace_input)
    cache = read(ROOT/'runs/exp003_gl_trace_full_20261106/official_identities.json')
    for row in evidence + pq.read_table(base/'outsider_evidence.parquet').to_pylist():
        if row.get('metric_key'):
            if row['smiles'] in cache and cache[row['smiles']] != row['metric_key']:
                raise ValueError('Conflicting existing official identity')
            cache[row['smiles']] = row['metric_key']
    def key(smiles):
        if smiles not in cache: cache[smiles] = identity(smiles)
        return cache[smiles]
    def ids(smiles): return {key(s) for s in smiles if key(s)}
    input_ids = {engine: {mid: ids(item['cands']) for mid, item in group.items()} for engine, group in inputs.items()}
    score_ids = {engine: {mid: ids(s for s, value in group.items() if finite(value))
                         for mid, group in model_scores.items()} for engine, model_scores in scores.items()}
    observed = defaultdict(list)
    for row in pq.read_table(base/'effective_query_spectra.parquet',
            columns=['molecule_id', 'adduct', 'ionization_mode']).to_pylist():
        observed[str(row['molecule_id'])].append({'adduct': row['adduct'], 'mode': row['ionization_mode']})
    truth = {}
    if args.with_dev_truth:
        truth_path = ROOT/'runs/validation_pilot_v2_20261104/truth.parquet'
        truth_rows = pq.read_table(truth_path).to_pylist()
        if {str(r['molecule_id']) for r in truth_rows} != valid_ids: raise ValueError('Truth scope differs from the 48 active dev queries')
        truth = {str(row['molecule_id']): row.get('official_identity') or row.get('identity') or key(row['smiles'])
                 for row in truth_rows}
        paths.append(truth_path)
    with (base/'submission.csv').open(encoding='utf-8-sig', newline='') as stream:
        final = {row['molecule_id']: row['smiles'].split(';') for row in csv.DictReader(stream)}
    if set(final) != valid_ids: raise ValueError('Final predictions differ from active queries')
    def reason(engine, mid, smiles):
        if finite(scores[engine].get(mid, {}).get(smiles)): return 'scored_exact_smiles'
        if key(smiles) in score_ids[engine].get(mid, set()): return 'scored_official_alias'
        if not any(covered(s) for s in observed[mid]): return 'unsupported_observed_adduct'
        if mid not in inputs[engine]: return 'query_not_sent_despite_supported_observed_adduct'
        if key(smiles) not in input_ids[engine][mid]: return 'candidate_not_sent'
        if not any(covered(s) for s in inputs[engine][mid]['spectra']): return 'no_supported_spectrum_in_engine_input'
        return 'sent_but_no_finite_output_runtime_or_model_missing'
    query_rows, candidate_rows, gap_items, gap_sidecar = [], [], [], []
    global_reasons = {engine: Counter() for engine in ('gl', 'ice')}
    for query_index, mid in enumerate(active, 1):
        retrieved = list(dict.fromkeys(stages[mid].get('e1_ranked_all', []) + stages[mid].get('e2_mass_window', [])))
        main = sorted(rows_by_query[mid], key=lambda r: r['baseline_rank'])
        main_smiles = [r['smiles'] for r in main]
        retrieved_ids, main_ids = ids(retrieved), ids(main_smiles)
        record = dict(molecule_id=mid, panel=mid.split('_', 1)[0],
            e1_ranked_all_rows=len(stages[mid].get('e1_ranked_all', [])),
            e2_mass_window_rows=len(stages[mid].get('e2_mass_window', [])),
            retrieved_union_unique_smiles=len(retrieved), retrieved_union_official_identities=len(retrieved_ids),
            main_top25_rows=len(main), main_top25_official_identities=len(main_ids),
            observed_spectra=len(observed[mid]), observed_supported_spectra=sum(covered(s) for s in observed[mid]))
        for stage, smis in stages[mid].items(): record['stage_'+stage+'_rows'] = len(smis)
        for engine in ('gl', 'ice'):
            item = inputs[engine].get(mid, {'cands': [], 'spectra': []})
            out = scores[engine].get(mid, {})
            counts = Counter(reason(engine, mid, s) for s in main_smiles)
            global_reasons[engine].update(counts)
            record.update({engine+'_input_candidates': len(item['cands']),
                engine+'_input_unique_identities': len(input_ids[engine].get(mid, set())),
                engine+'_input_spectra': len(item['spectra']),
                engine+'_input_supported_spectra': sum(covered(s) for s in item['spectra']),
                engine+'_output_finite_candidates': sum(finite(v) for v in out.values()),
                engine+'_main25_missing_by_identity': sum(n for r, n in counts.items() if not r.startswith('scored_')),
                engine+'_main25_missing_exact_score': sum(not finite(out.get(s)) for s in main_smiles),
                engine+'_retrieved_not_sent_identities': len(retrieved_ids-input_ids[engine].get(mid, set())),
                engine+'_frozen_evidence_missing': sum(not finite(r.get(engine)) for r in main)})
            for category, count in counts.items(): record[engine+'_main25_'+category] = count
            if truth:
                target = truth[mid]
                record[engine+'_truth_in_input'] = target in input_ids[engine].get(mid, set())
                record[engine+'_truth_has_finite_score'] = target in score_ids[engine].get(mid, set())
        if truth:
            final_keys = [key(s) for s in final[mid]]
            record.update(truth_in_retrieved_union=truth[mid] in retrieved_ids,
                truth_in_main25=truth[mid] in main_ids, final_top1_correct=bool(final_keys and final_keys[0] == truth[mid]),
                final_truth_rank=next((i for i, k in enumerate(final_keys, 1) if k == truth[mid]), None))
        for s in retrieved:
            row = dict(molecule_id=mid, smiles=s, official_identity=key(s), in_main25=key(s) in main_ids)
            for engine in ('gl', 'ice'): row[engine+'_coverage'] = reason(engine, mid, s)
            candidate_rows.append(row)
        # ICE input preserves the runner's original spectrum schema and candidates.
        # Only missing Na observations are exported; never introduce a candidate.
        old_gl_spectra = Counter(spectrum_digest(s) for s in inputs['gl'].get(mid, {}).get('spectra', []))
        missing_na = []
        for spectrum in inputs['ice'].get(mid, {}).get('spectra', []):
            digest = spectrum_digest(spectrum)
            if old_gl_spectra[digest]: old_gl_spectra[digest] -= 1; continue
            if covered(spectrum) and spectrum['adduct'] == '[M+Na]+': missing_na.append(spectrum)
        record['gl_missing_na_spectra'] = len(missing_na)
        if missing_na:
            original = inputs['ice'][mid]
            gap_items.append(dict(mid=mid, spectra=missing_na, cands=list(original['cands'])))
            gap_sidecar.append(dict(molecule_id=mid, spectra=len(missing_na), candidates=len(original['cands']),
                original_ice_candidate_sha256=hashlib.sha256(json.dumps(original['cands'], separators=(',', ':')).encode()).hexdigest(),
                candidate_source='unchanged original ICE input candidate list',
                prior_gl_query_present=mid in inputs['gl'],
                **({name: record[name] for name in ('truth_in_main25', 'truth_in_retrieved_union', 'final_top1_correct', 'final_truth_rank')} if truth else {})))
        query_rows.append(record)
        print(json.dumps(dict(stage='coverage', queries=query_index, total=len(active))), flush=True)
    checkpoint = dict(path=str((PACKAGE/'ckpt/glacier.pt').relative_to(ROOT)),
                      sha256=sha(PACKAGE/'ckpt/glacier.pt'), inspected_tensors=False)
    if checkpoint['sha256'] != EXPECTED_CKPT: raise ValueError('Unexpected GL checkpoint')
    if args.inspect_checkpoint:
        import torch
        weights = torch.load(PACKAGE/'ckpt/glacier.pt', map_location='cpu', weights_only=True)
        hp = {str(k): v for k, v in weights['hyper_parameters'].items() if not str(k).startswith('_')}
        json.dumps(hp)
        adduct = weights['state_dict'].get('adduct_embedder')
        if adduct is None or adduct.shape[0] <= 1: raise ValueError('Actual GL checkpoint cannot index Na=1')
        checkpoint.update(inspected_tensors=True, hyper_parameters=hp,
            adduct_embedder_shape=list(adduct.shape), na_index=1,
            na_row_finite=bool(torch.isfinite(adduct[1]).all()),
            na_row_values=adduct[1].tolist(), model_instantiated=False, inference_performed=False)
        del weights
    output.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(query_rows), output/'query_coverage.parquet')
    pq.write_table(pa.Table.from_pylist(candidate_rows), output/'retrieved_candidate_coverage.parquet')
    columns = sorted({name for row in query_rows for name in row})
    with (output/'query_coverage.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader(); writer.writerows(query_rows)
    save(output/'gl_missing_na_input.json', gap_items)
    save(output/'gl_missing_na_fixed_candidates.json', gap_sidecar)
    save(output/'gl_missing_na_official_identities.json', {s: key(s) for item in gap_items for s in item['cands']})
    summary = dict(status='complete_no_model_inference', created_at_utc=datetime.now(timezone.utc).isoformat(),
        audit_script_sha256=sha(__file__), official_identity_rdkit=rdkit, queries=len(active),
        evaluation_label='existing reference-isolated development diagnostic with known pretrained exposure; not clean generalization',
        dev_truth_read=bool(truth), locked250_truth_or_queries_read=False,
        model_inference_performed=False, training_performed=False,
        artifact_inputs=[dict(path=str(p.relative_to(ROOT)), sha256=sha(p)) for p in paths],
        engine_runtime_metadata=meta, main25_reason_counts={k: dict(v) for k, v in global_reasons.items()},
        main25_missing_queries={engine: sum(row[engine+'_main25_missing_by_identity'] > 0 for row in query_rows) for engine in ('gl', 'ice')},
        retrieved_union_total_identities=sum(row['retrieved_union_official_identities'] for row in query_rows),
        retrieved_not_sent_total_identities={engine: sum(row[engine+'_retrieved_not_sent_identities'] for row in query_rows) for engine in ('gl', 'ice')},
        gl_missing_na=dict(queries=len(gap_items), spectra=sum(len(i['spectra']) for i in gap_items),
            candidate_rows=sum(len(i['cands']) for i in gap_items),
            candidate_spectrum_pairs=sum(len(i['cands'])*len(i['spectra']) for i in gap_items),
            new_gl_queries=sum(i['mid'] not in inputs['gl'] for i in gap_items),
            query_sidecar=gap_sidecar), checkpoint=checkpoint,
        support_evidence=dict(runner=str((PACKAGE/'gl_runner.py').relative_to(ROOT)), runner_sha256=sha(PACKAGE/'gl_runner.py'),
            runner_supported_adducts=['[M+H]+', '[M+Na]+'],
            na_mapping_source='src/ms_pred/common/chem_utils.py ion2onehot_pos maps [M+Na]+ to 1',
            actual_model_lookup='src/ms_pred/glacier/joint_model.py indexes adduct_embedder[adducts.long()]',
            caveat='Representable and accepted by code/checkpoint; accuracy on Na is not established until new inference/evaluation'),
        unknowns=['Retrieval logs are downstream logged candidate stages; these are not a complete enumeration of every original database row.',
            'Finite forward score coverage does not prove that later ranking consumes it or that more coverage improves ranks.',
            'Runtime/model missing is inferred only when a submitted candidate has eligible input spectrum and no finite score; no individual failure cause is invented.',
            'This audit is on the old Flex48 diagnostic run, not a full reproduction of the 0.481 hidden MASS execution.',
            'Checkpoint representability is not evidence about the number or quality of Na examples used in its pretraining.'])
    save(output/'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('status', 'queries', 'main25_reason_counts', 'main25_missing_queries',
        'retrieved_union_total_identities', 'retrieved_not_sent_total_identities', 'gl_missing_na')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    main()
