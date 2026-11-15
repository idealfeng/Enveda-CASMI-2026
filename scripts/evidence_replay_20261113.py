"""Replay the frozen metric-fusion stage and the preregistered CE-support perturbation.

This reads existing cached evidence only. It does not claim a complete .488 rerun.
"""
from pathlib import Path
from collections import defaultdict
from types import SimpleNamespace
import ast
import csv
import hashlib
import importlib.util
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
WORK=ROOT/'runs/validation_flex_c2_20261105d'
TRACE=ROOT/'runs/exp003_gl_trace_full_20261106'
OUT=ROOT/'reports/optimization_20261113/evidence_replay_v2'
WEIGHT=.10


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def functions(source,wanted,scope):
    tree=ast.parse(source)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in nodes}==set(wanted)
    exec(compile(ast.Module(nodes,type_ignores=[]),'original_frozen_functions','exec'),scope)


def main():
    if OUT.exists():raise FileExistsError('Preserve the first fixed replay')
    OUT.mkdir(parents=True)
    frozen=read(ROOT/'reports/optimization_20261113/evidence_frozen_source.json')
    source=lambda i:''.join(frozen['cells'][i]['source'])
    from functools import lru_cache
    from rdkit import Chem,RDLogger
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize
    RDLogger.DisableLog('rdApp.*')
    identity_scope=dict(lru_cache=lru_cache,Chem=Chem,RDLogger=RDLogger,rdMolStandardize=rdMolStandardize)
    exec(compile(source(47),'frozen_identity','exec'),identity_scope)
    fusion_scope={}
    functions(source(49),['metric_fusion'],fusion_scope)
    pkg=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9'
    glue=load('_evidence_original_gl_glue',pkg/'casmi26-glacier/gl_fuse.py')
    ice=load('_evidence_original_ice_glue',pkg/'casmi26-iceberg/fuse.py')
    chem=load('_evidence_original_chem',pkg/'casmi26-v4b-models/code/casmi/chem.py')
    ids=read(TRACE/'official_identities.json')
    assert sha(TRACE/'official_identities.json')=='7f05e2c54fd87a49ee3b80dbe79a4997b7b6dcf1616f90595d6e1a2b8980a09c'
    # Verified same-version official identity sidecar is a memo table, not a
    # replacement identity policy. Unknown strings still use the frozen code.
    original_identity=identity_scope['canonicalize_smiles_to_ik14']
    identity_scope['canonicalize_smiles_to_ik14']=lru_cache(maxsize=30000)(
        lambda s: ids[s] if s in ids else original_identity(s))
    chem.score_key=lru_cache(maxsize=30000)(chem.score_key)
    inputs=read(WORK/'e004_candidate_inputs.json')
    gs=read(WORK/'gl_work/gl_out.json')
    ice_scores=read(WORK/'ice_work/ice_out.json')
    reference={r['molecule_id']:r['smiles'].split(';') for r in csv.DictReader((WORK/'submission_reference.csv').open())}
    expected={r['molecule_id']:r['smiles'].split(';') for r in csv.DictReader((WORK/'submission_e004_control.csv').open())}
    metric_identity=identity_scope['metric_identity']
    formula=lru_cache(maxsize=20000)(lambda s:rdMolDescriptors.CalcMolFormula(Chem.MolFromSmiles(s)))
    scope=dict(ENG=inputs['engine2'],PREFUSION_LISTS=inputs['prefusion'],metric_fusion=fusion_scope['metric_fusion'],
        metric_identity=metric_identity,ALPHA=.6,KRR=3.,chem=chem,ICE_SCORES=ice_scores,gl_of=lambda m:gs.get(m,{}),
        _form2=formula,gl_fuse=glue,ICE_LAM=1.,GL_LAM=1.,safe_extend=identity_scope['safe_extend'],ice_fuse=ice,N1_GL_MIDS=set())
    # Exact original nested row function, without running the notebook/driver.
    outer=ast.parse(source(52)).body[0]
    nodes=[n for n in outer.body if isinstance(n,ast.FunctionDef) and n.name in ('_finite_coverage','rerank_row')]
    original_scope={'math':__import__('math')}
    exec(compile(ast.Module(nodes,type_ignores=[]),'frozen_factorial_row','exec'),original_scope)
    params=dict(weight=WEIGHT,scope='Fixed top1; only original ranks2-25 with control leader formula; same candidate set',
                original_full_formula_T0=True,no_truth_used_for_policy=True,claimed_full_488=False,
                gl_glue_sha256=sha(pkg/'casmi26-glacier/gl_fuse.py'),
                feature_design_sha256=sha(ROOT/'reports/EXP003_FEATURE_DESIGN_2026-11-06.md'))
    save(OUT/'frozen_policy.json',params)
    originals={str(i['mid']):i for i in read(TRACE/'input.json')}
    coverage=[];score_events={}
    for line in (TRACE/'trace/per_spectrum.jsonl').open(encoding='utf-8'):
        e=json.loads(line)
        if e.get('event')=='spectrum_coverage':coverage.append(e)
        if e.get('event')=='candidate_spectrum_score':score_events[(str(e['mid']),e['spectrum_index'],e['candidate_smiles'])]=e
    exporter=load('_evidence_ce_derivation',ROOT/'scripts/export_gl_support_features.py')
    controls={};treatments={};audit=[];feature_rows=[]
    for seq,(mid,item) in enumerate(originals.items(),1):
        print(f'Reconstructing actual stage {seq}/{len(originals)} {mid}',flush=True)
        c,a=original_scope['rerank_row'](scope,mid,reference[mid],window=40,ice_fallback=False,processed=True)
        if c!=expected[mid]:raise ValueError('Original actual-stage reconstruction mismatch: '+mid)
        controls[mid]=c
        cs,bs,_=scope['metric_fusion'](inputs['prefusion'][mid],inputs['engine2'][mid]['smiles'],metric_identity,alpha=.6,offset=3.,limit=40)
        keys=[chem.score_key(s) or s for s in cs];forms=[formula(s) for s in cs]
        order=glue.rerank_multi(cs,keys,bs,forms,[{},gs[mid]],[1.,1.],top_n=len(cs)) if ice_scores.get(mid) and gs.get(mid) else list(range(len(cs)))
        # Freeze the competition set to the exact fusion top40, not all runner candidates.
        small=dict(item,cands=cs)
        cov=[e for e in coverage if str(e['mid'])==mid]
        events=[];missing=0
        for e in cov:
            if not e.get('covered'):continue
            for s in cs:
                key=(mid,e['spectrum_index'],s)
                if key in score_events:events.append(score_events[key])
                else:
                    missing+=1
                    events.append(dict(e,event='candidate_spectrum_score',candidate_smiles=s,
                        candidate_official_identity=ids.get(s),score=None,status='not_in_original_GL_input'))
        all_ids=dict(ids)
        for s in cs:
            if s not in all_ids:
                identity=metric_identity(s);all_ids[s]=identity[0] if identity else None
        for e in events:
            if e.get('candidate_official_identity') is None:e['candidate_official_identity']=all_ids.get(e['candidate_smiles'])
        rows,derived=exporter.derive([small],all_ids,cov,events,formula)
        feature_rows.extend(rows)
        features={r['candidate_smiles']:r['candidate_support_centered'] for r in rows}
        h=[i for i,f in enumerate(forms) if f==formula(c[0])]
        current=[cs[i] for i in order]
        movable=[j for j,s in enumerate(current[:25]) if j>0 and formula(s)==formula(c[0])]
        eligible=bool(h) and len(movable)>=2 and all(features.get(cs[i]) is not None for i in h)
        changed=list(c);zero_matches=True
        if eligible:
            basez=glue._z([bs[i] for i in h]);glz=glue._z([glue._clean(gs[mid].get(cs[i],gs[mid].get(keys[i]))) for i in h])
            t0={cs[i]:basez[k]+glz[k] for k,i in enumerate(h)}
            ordered_movable=[current[j] for j in movable]
            zero_order=sorted(ordered_movable,key=lambda s:-t0[s])
            zero_matches=zero_order==ordered_movable
            if not zero_matches:raise ValueError('Zero coefficient did not recover original full-group scoring')
            new_order=sorted(ordered_movable,key=lambda s:-(t0[s]+WEIGHT*features[s]))
            for j,s in zip(movable,new_order):changed[j]=s
        if set(changed)!=set(c) or changed[0]!=c[0]:raise ValueError('Fixed candidate/top1 contract broken')
        treatments[mid]=changed
        audit.append(dict(mid=mid,actual_control_reconstructed=True,candidate_count=len(cs),original_formula_count=len(h),
            common_observation_missing_pairs=missing,movable_slots=len(movable),eligible=eligible,
            zero_recovers_control=zero_matches,changed=changed!=c,changed_top1=changed[0]!=c[0],
            original_gl_candidates=len(item['cands']),feature_groups=derived['groups']))
    with (OUT/'candidate_evidence_features.jsonl').open('x',encoding='utf-8') as stream:
        for row in feature_rows:stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    save(OUT/'stage_predictions.json',dict(control=controls,treatment=treatments))
    save(OUT/'stage_audit.json',audit)
    # Evaluation labels are read only after fixed-policy predictions have been saved.
    evaluation=read(ROOT/'reports/validation_flex_c2_20261105d/evaluation_report.json')
    truth={r['molecule_id']:r['identity'] for r in evaluation['predictions']['final']['rows']}
    def scores(table):
        ranks={m:next((i for i,s in enumerate(values,1) if metric_identity(s)[0]==truth[m]),None) for m,values in table.items()}
        return ranks,sum(1/r for r in ranks.values() if r is not None and r<=25)/len(ranks)
    cr,cm=scores(controls);tr,tm=scores(treatments)
    result=dict(status='completed_stage_replay_only',queries=len(controls),exact_controls=len(controls),
        eligible_queries=sum(a['eligible'] for a in audit),changed_queries=sum(a['changed'] for a in audit),
        top1_fixed=True,candidate_set_fixed=True,weight=WEIGHT,control_mrr25=cm,treatment_mrr25=tm,
        paired_delta=tm-cm,per_query_rank=[dict(mid=m,control=cr[m],treatment=tr[m]) for m in cr],
        selection_policy_frozen_before_label_read=True,no_gpu_or_model_run=True,no_produre_rerun=True,
        exact_488_full_pipeline=False,production_wrapper_prepared=False,
        limitations=['Old exposed panel, not clean CV or hidden test.',
          'Fusion stage only; later physical/MASS/neural/head/AB not rerun.',
          'Evidence missing from original GL input stays explicitly unobserved, not zero.',
          'A source hash and nonconstant evidence do not prove final ranking gain.'])
    save(OUT/'summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='per_query_rank'},indent=2))


if __name__=='__main__':main()
