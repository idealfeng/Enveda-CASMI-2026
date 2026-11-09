"""Verify Na score/count merging using real recorded pairs and synthetic missingness."""
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import types

import numpy as np
from gl_counted_runner import install_counts
from forward_trace_runner import score_code,self_test
from mass_gl_na_counted_hook import merge_scores,select_items

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def observed(path):
    values=defaultdict(lambda:defaultdict(list))
    for line in Path(path).open():
        row=json.loads(line)
        if row['event']=='candidate_spectrum_score' and row['score'] is not None and math.isfinite(row['score']):
            values[row['mid']][row['candidate_smiles']].append(row['score'])
    return values


def main():
    old=ROOT/'runs/validation_flex_c2_20261105d'
    hs=read(old/'gl_work/gl_out.json')
    ns=read(ROOT/'runs/gl_na_probe_20261108/gl_out.json')
    hp=observed(ROOT/'runs/exp003_gl_trace_full_20261106/trace/per_spectrum.jsonl')
    npairs=observed(ROOT/'runs/gl_na_probe_20261108/per_spectrum.jsonl')
    hc={m:{s:len(v) for s,v in d.items()} for m,d in hp.items()}
    nc={m:{s:len(v) for s,v in d.items()} for m,d in npairs.items()}
    combined=merge_scores(hs,ns,hc,nc)
    checks={}
    differences=[]
    for m,d in combined.items():
        for s,v in d.items():
            vals=hp.get(m,{}).get(s,[])+npairs.get(m,{}).get(s,[])
            wanted=statistics.mean(vals) if vals else None
            if wanted is None:assert v is None
            else:differences.append(abs(v-wanted))
    checks['real_pairs_reconstruct_weighted_means']=max(differences,default=0.)<1e-12
    checks['non_na_values_preserved_exactly']=all(combined[m]==d for m,d in hs.items() if m not in ns)
    # This intentionally has different per-candidate counts despite one query.
    a={'q':{'a':.4,'b':.7,'c':.2},'unchanged':{'d':.1234567890123}}
    b={'q':{'a':.9,'b':.3,'c':None},'new':{'e':.8}}
    ac={'q':{'a':2,'b':1,'c':3},'unchanged':{'d':1}}
    bc={'q':{'a':1,'b':2,'c':0},'new':{'e':4}}
    c=merge_scores(a,b,ac,bc)
    checks['per_candidate_counts_not_input_spectrum_count']=(c['q']['a']==(.4*2+.9)/3 and c['q']['b']==(.7+.3*2)/3)
    checks['missing_na_keeps_h']=c['q']['c']==a['q']['c']
    checks['new_na_only_query_supported']=c['new']['e']==.8
    checks['unaffected_query_exact']=c['unchanged']==a['unchanged']
    invalid=0
    for wrong in [dict(q=dict(a=0,b=2,c=0)),dict(q=dict(a=1.,b=2,c=0)),dict(q=dict(a=-1,b=2,c=0))]:
        try:merge_scores(a,b,ac,wrong)
        except ValueError:invalid+=1
    checks['invalid_actual_counts_rejected']=invalid==3
    source=(ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier/gl_runner.py').read_text()
    checks['score_ast_observer_equivalence']=self_test(source)['status']=='passed'
    # Exercise the actual count installer against original score code with a tiny cache.
    module=types.ModuleType('count_fixture')
    module.np=np;module.SUM_CE=(20.,40.,60.)
    for k,v in dict(FLOOR=.002,TOPK=256,POWER=1.,ENTW=True,TOL=.01,PPM=20.).items():setattr(module,k,v)
    module.prep_query=lambda a,b,*args:(a,b)
    module.entropy_sim=lambda qm,qp,pm,pp,*args:qm+pm
    module.merge=lambda parts:(sum(p[0] for p in parts),None)
    module.molecule_plan=lambda mol:mol['plan']
    _,original=score_code(source)
    import ast
    exec(compile(ast.Module([original],type_ignores=[]),'original-score-fixture','exec'),module.__dict__)
    counts=install_counts(module,source)
    plan=module.molecule_plan(dict(mid='fixture',plan=[(1.,None,'H','Q',20.),(2.,None,'H','Q',30.)]))
    result=module.score_molecule(plan,['x','y'],{('x','H','Q',20.):(.2,None),('x','H','Q',30.):(.4,None),('y','H','Q',20.):(.7,None)})
    checks['actual_count_installer_variable_counts']=counts=={'fixture':{'x':2,'y':1}} and math.isclose(result['x'],1.8,abs_tol=1e-15) and result['y']==1.7
    out=ROOT/'runs/gl_na_counted_merge_20261108';out.mkdir(exist_ok=True)
    (out/'combined_scores.json').write_text(json.dumps(combined)+'\n')
    (out/'h_finite_counts.json').write_text(json.dumps(hc)+'\n')
    (out/'na_finite_counts.json').write_text(json.dumps(nc)+'\n')
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
        actual_h_queries=len(hs),actual_na_queries=len(ns),combined_queries=len(combined),
        combined_candidate_rows=sum(len(d) for d in combined.values()),max_mean_error=max(differences,default=0.),
        original_h_output_sha256=sha(old/'gl_work/gl_out.json'),combined_sha256=sha(out/'combined_scores.json'),
        no_truth_read=True,no_models_loaded=True,no_new_training=True,no_new_submission=True)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
