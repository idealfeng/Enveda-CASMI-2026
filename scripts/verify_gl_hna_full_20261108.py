"""Verify the actual joint H+/Na+ run against original frozen inputs, no labels."""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics

from mass_gl_na_hook import record_report, select_items

ROOT=Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())


def main():
    work=ROOT/'runs/gl_hna_full_20261108'
    old=ROOT/'runs/validation_flex_c2_20261105d'
    original=read(old/'ice_work/ice_in.json')
    actual=read(work/'input.json')
    selected=select_items(original)
    out=read(work/'gl_out.json')
    meta=read(work/'gl_out.json.meta.json')
    trace=read(work/'gl_out.json.trace_run.json')
    scores=defaultdict(list)
    pairs=set()
    for line in (work/'per_spectrum.jsonl').open():
        row=json.loads(line)
        if row['event']=='candidate_spectrum_score':
            item=(row['mid'],row['candidate_smiles'],row['spectrum_index'])
            if item in pairs: raise ValueError('Duplicate candidate-spectrum pair')
            pairs.add(item)
            if row['status']!='scored' or not math.isfinite(row['score']): raise ValueError('Invalid score')
            scores[item[:2]].append(row['score'])
    expected_pairs={(str(i['mid']),s,j) for i in selected for s in i['cands'] for j in range(len(i['spectra']))}
    differences=[abs(statistics.mean(values)-out[mid][s]) for (mid,s),values in scores.items()]
    old_input=read(old/'gl_work/gl_in.json')
    old_out=read(old/'gl_work/gl_out.json')
    no_na=[i for i in selected if all(s['adduct']=='[M+H]+' for s in i['spectra'])]
    before={str(i['mid']):i for i in old_input}
    unchanged_inputs=all(i==before[str(i['mid'])] for i in no_na)
    no_na_max=max((abs(v-old_out[str(i['mid'])][s]) for i in no_na
                  for s,v in out[str(i['mid'])].items()),default=0.)
    checks=dict(exact_selected_input=actual==selected,
        exact_original_candidate_lists=all(i['cands']==next(x['cands'] for x in original if x['mid']==i['mid']) for i in actual),
        real_adducts_preserved=all(s['adduct'] in ('[M+H]+','[M+Na]+') for i in actual for s in i['spectra']),
        full_runtime_success=meta['status']=='ok' and not meta['errors'] and trace['status']=='complete',
        exact_query_and_output_sets=set(out)=={str(i['mid']) for i in actual}
            and all(set(out[str(i['mid'])])==set(i['cands']) for i in actual),
        all_output_scores_finite=all(math.isfinite(v) for d in out.values() for v in d.values()),
        all_actual_pairs_exact=pairs==expected_pairs,
        exact_actual_means=max(differences,default=0.)<1e-12,
        no_na_query_inputs_unchanged=unchanged_inputs,
        no_na_query_scores_numerically_unchanged=no_na_max<1e-6,
        original_h_input_unchanged=sha(old/'gl_work/gl_in.json')=='a5a4d57be73820dcb841c8b5bd180f6f204ef0b4713a8b6a2fa8d6c141c0cd0a',
        original_h_output_unchanged=sha(old/'gl_work/gl_out.json')=='424ffecab17f571a858da452c27a6f1ce2dda64d01549b0854d1ce1c0b0c62d9')
    shutil.copyfile(work/'input.json',work/'gl_in.json')
    report=record_report(ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier',
        original,actual,out,work,work/'gl_na_runtime.json')
    checks['actual_deployed_runtime_report_passed']=report['status']=='passed'
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
        queries=len(actual),spectra=sum(len(i['spectra']) for i in actual),candidates=sum(len(i['cands']) for i in actual),
        candidate_spectrum_pairs=len(pairs),max_mean_error=max(differences,default=0.),
        no_na_query_count=len(no_na),no_na_query_max_score_difference=no_na_max,
        runtime=meta,output_sha256=sha(work/'gl_out.json'),no_truth_or_locked250_read=True,
        ranking_changed=False,training_performed=False,competition_submission_performed=False)
    (work/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not all(checks.values()): raise SystemExit(1)


if __name__=='__main__': main()
