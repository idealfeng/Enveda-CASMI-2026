"""Consume actual production GL/ICE scores after champion head and AB output.

No labels, new candidates or model inference. Missing evidence stays missing.
"""
from pathlib import Path
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
import shutil

CONFIGS = {
    'gl_evidence_early': dict(protect_prefix=1, gl_weight=1., scope='same_formula_observed_slots',
        minimum_covered=2, minimum_coverage_fraction=.8, protect_library=.9, protect_AB=True),
    'dual_evidence_agreement': dict(protect_prefix=0, scope='swap_pairwise_dominant_same_formula_candidate_to_top1',
        minimum_covered=2, minimum_coverage_fraction=.8, maximum_winner_rank=10,
        minimum_standardized_advantage=.1, protect_library=.9, protect_AB=True),
}


def sha(path):
    with Path(path).open('rb') as handle: return hashlib.file_digest(handle, 'sha256').hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path, value): Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
def finite(value): return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def z(values):
    if len(values)<2: return [0.]*len(values)
    mean=sum(values)/len(values)
    sd=math.sqrt(sum((v-mean)**2 for v in values)/(len(values)-1))
    return [(v-mean)/sd for v in values] if sd>0 else [0.]*len(values)


@lru_cache(maxsize=100000)
def formula(smiles):
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    mol=Chem.MolFromSmiles(smiles)
    return rdMolDescriptors.CalcMolFormula(mol) if mol is not None else None


def resolve_scores(candidates, values, identity):
    """Original direct-string/key priority, then unambiguous official aliases.

    Never convert a missing, NaN, ambiguous alias, or absent prediction to zero.
    """
    aliases=defaultdict(list)
    for key, value in values.items():
        if not finite(value): continue
        if len(key)==14 and '-' not in key and key.isalpha():
            aliases[key].append(float(value))
        elif key not in candidates:
            ik=identity(key)
            if ik: aliases[ik].append(float(value))
    out=[]
    for smiles in candidates:
        direct=values.get(smiles)
        key=identity(smiles)
        fallback=values.get(key) if key else None
        if finite(direct): value=float(direct)
        elif finite(fallback): value=float(fallback)
        else:
            group=aliases.get(key, [])
            value=group[0] if group and max(group)-min(group)<=1e-8 else None
        out.append(value)
    return out


def rank_candidates(candidates, gl_values, ice_values, branch, identity):
    config=CONFIGS[branch]
    forms=[formula(s) for s in candidates]
    gl=resolve_scores(candidates, gl_values, identity)
    ice=resolve_scores(candidates, ice_values, identity)
    final=list(candidates); decisions=[]
    if branch=='gl_evidence_early':
        groups=defaultdict(list)
        for index, form in enumerate(forms):
            if index>=config['protect_prefix'] and form: groups[form].append(index)
        for form, slots in groups.items():
            observed=[i for i in slots if gl[i] is not None]
            if len(observed)<config['minimum_covered'] or len(observed)/len(slots)<config['minimum_coverage_fraction']: continue
            # Freeze unobserved slots and the original rank1. Scores only compete
            # among same-formula observed original positions.
            prior=z([-math.log(i+1) for i in observed]); evidence=z([gl[i] for i in observed])
            score=[a+config['gl_weight']*b for a,b in zip(prior,evidence)]
            order=sorted(range(len(observed)),key=lambda j:(-score[j],j))
            for dst, src in zip(observed,[observed[j] for j in order]): final[dst]=candidates[src]
            decisions.append(dict(formula=form, slots=observed, prior=prior, evidence=evidence,
                fused=score, source_slots=[observed[j] for j in order]))
    else:
        slots=[i for i,f in enumerate(forms) if f and f==forms[0]]
        common=[i for i in slots if gl[i] is not None and ice[i] is not None]
        if len(common)>=config['minimum_covered'] and len(common)/len(slots)>=config['minimum_coverage_fraction']:
            glz=z([gl[i] for i in common]); icez=z([ice[i] for i in common])
            if 0 in common:
                lead=common.index(0)
                advantages=[dict(index=i, gl=glz[j]-glz[lead], ice=icez[j]-icez[lead])
                            for j,i in enumerate(common)]
                eligible=[d for d in advantages if 0<d['index']<config['maximum_winner_rank']
                          and d['gl']>=config['minimum_standardized_advantage']
                          and d['ice']>=config['minimum_standardized_advantage']
                          and gl[d['index']]>0 and ice[d['index']]>0]
                winner=min(eligible,key=lambda d:(-(d['gl']+d['ice'])/2,d['index'])) if eligible else None
                if winner:
                    index=winner['index'];final[0],final[index]=final[index],final[0]
                decisions.append(dict(formula=forms[0],slots=common,gl=glz,ice=icez,
                    original_leader_slot=lead,pairwise_advantages=advantages,
                    eligible_candidates=eligible,promoted_from=winner['index'] if winner else None))
    return final, dict(candidates=list(candidates), formulas=forms, gl=gl, ice=ice,
                      decisions=decisions, proposed=final)


def protected_ids(root, base_audit, control):
    import pandas as pd
    runtime_path=root/'external_overlay_runtime.json'
    if sha(runtime_path)!=base_audit.get('runtime_report_sha256'): raise ValueError('AB runtime is unbound')
    runtime=read(runtime_path)
    if runtime.get('output_sha256')!=sha(control): raise ValueError('AB control differs')
    invalid={str(r['molecule_id']) for r in runtime.get('details',[]) if r.get('validity_guard_preserved_control')}
    result={str(r['molecule_id']) for r in runtime.get('actual_matches',[])
            if r.get('above_threshold') and str(r['molecule_id']) not in invalid}
    evidence=root/'frozen_candidate_evidence.parquet'
    if not evidence.exists(): raise ValueError('Production library evidence is required')
    table=pd.read_parquet(evidence,columns=['molecule_id','library_max'])
    result.update(str(m) for m,s in table.groupby('molecule_id',sort=False).library_max.max().items()
                  if finite(float(s)) and float(s)>=.9)
    return result, dict(ab_runtime_sha256=sha(runtime_path), library_evidence_sha256=sha(evidence))


def run(root, is_rerun, sample_ids, base_audit, branch, recipe_pin):
    import pandas as pd
    import external_library_overlay_20261109 as original
    root=Path(root);control=root/'submission_evidence_early_control.csv'
    try:
        if base_audit.get('status')!='passed' or base_audit.get('csv_sha256')!=sha(root/'submission.csv'):
            raise ValueError('Champion final AB output must be bound')
        shutil.copy2(root/'submission.csv',control)
        old=pd.read_csv(control,dtype=str,keep_default_na=False)
        if list(old.columns)!=['molecule_id','smiles'] or old.molecule_id.tolist()!=list(sample_ids) or not old.molecule_id.is_unique:
            raise ValueError('Actual sample schema or IDs differ')
        if not all(original.valid(s) for s in old.smiles): raise ValueError('Official identities invalid')
        report=dict(status='fast_static_no_evidence',branch=branch,recipe_sha256=recipe_pin,
            configuration=CONFIGS[branch],control_sha256=sha(control),observations={},protected_ids=[],
            changed_queries=0,changed_top1=0,evidence_executed=False,protected_queries=0,eligible_queries=0)
        if is_rerun:
            paths=dict(gl=root/'gl_work/gl_out.json',ice=root/'ice_work/ice_out.json')
            scores={k:read(p) for k,p in paths.items()}
            if any(not isinstance(v,dict) for v in scores.values()): raise ValueError('Actual score payload malformed')
            protected,pins=protected_ids(root,base_audit,control)
            final=old.copy();observations={}
            for index, (mid,raw) in enumerate(zip(old.molecule_id,old.smiles)):
                proposed,observed=rank_candidates(raw.split(';'),scores['gl'].get(mid,{}),scores['ice'].get(mid,{}),branch,original.identity)
                observations[mid]=observed
                if mid in protected: continue
                if not original.valid(';'.join(proposed)): raise ValueError('Proposed identities invalid')
                final.loc[index,'smiles']=';'.join(proposed)
            final.to_csv(root/'submission.csv',index=False)
            report.update(status='applied',evidence_executed=True,observations=observations,
                protected_ids=sorted(protected),pins=dict(pins,**{k+'_score_sha256':sha(p) for k,p in paths.items()}),
                changed_queries=int((old.smiles!=final.smiles).sum()),
                changed_top1=sum(a.split(';')[0]!=b.split(';')[0] for a,b in zip(old.smiles,final.smiles)),
                protected_queries=sum(mid in protected for mid in old.molecule_id),
                eligible_queries=sum(bool(o['decisions']) for mid,o in observations.items() if mid not in protected))
        report['output_sha256']=sha(root/'submission.csv')
        save(root/'evidence_early_runtime.json',report)
        return report
    except BaseException:
        (root/'submission.csv').unlink(missing_ok=True)
        raise


def audit(root, is_rerun, sample_ids, base_audit, branch, recipe_pin, module_pin):
    import pandas as pd
    import external_library_overlay_20261109 as original
    root=Path(root);r=read(root/'evidence_early_runtime.json')
    control=root/'submission_evidence_early_control.csv'
    old=pd.read_csv(control,dtype=str,keep_default_na=False)
    final=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
    checks=dict(base_ab_passed=base_audit.get('status')=='passed',
        control_bound=sha(control)==base_audit.get('csv_sha256')==r['control_sha256'],
        final_bound=sha(root/'submission.csv')==r['output_sha256'],module_pin=sha(__file__)==module_pin,
        configuration_exact=r['configuration']==CONFIGS[branch],recipe_branch_bound=r['branch']==branch and r['recipe_sha256']==recipe_pin,
        sample_ids_exact=final.molecule_id.tolist()==list(sample_ids) and final.molecule_id.is_unique,
        csv_schema=list(final.columns)==['molecule_id','smiles'],
        candidate_multisets=all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(old.smiles,final.smiles)),
        official_identities=all(original.valid(s) for s in final.smiles))
    expected=old.copy()
    if is_rerun:
        protected,pins=protected_ids(root,base_audit,control)
        scores={k:read(root/path) for k,path in [('gl','gl_work/gl_out.json'),('ice','ice_work/ice_out.json')]}
        pins.update({k+'_score_sha256':sha(root/path) for k,path in [('gl','gl_work/gl_out.json'),('ice','ice_work/ice_out.json')]})
        if r['protected_ids']!=sorted(protected) or r['pins']!=pins: raise ValueError('Evidence bindings changed')
        for index,(mid,raw) in enumerate(zip(old.molecule_id,old.smiles)):
            proposed,observed=rank_candidates(raw.split(';'),scores['gl'].get(mid,{}),scores['ice'].get(mid,{}),branch,original.identity)
            if observed!=r['observations'].get(mid): raise ValueError('Actual score consumption differs')
            if mid not in protected: expected.loc[index,'smiles']=';'.join(proposed)
        checks.update(actual_evidence_executed=r['evidence_executed'] is True,
            actual_score_consumption=expected.equals(final),actual_protected_set=True,
            reference_rows_exact=all(a==b for mid,a,b in zip(old.molecule_id,old.smiles,final.smiles) if mid in protected))
        if branch=='gl_evidence_early': checks['original_top1_fixed']=all(a.split(';')[0]==b.split(';')[0] for a,b in zip(old.smiles,final.smiles))
    else: checks['fast_no_evidence']=r['evidence_executed'] is False and expected.equals(final)
    if not all(checks.values()):
        (root/'submission.csv').unlink(missing_ok=True)
        raise ValueError('Actual evidence output audit failed')
    result=dict(status='passed',branch=branch,recipe_sha256=recipe_pin,mode='hidden_full' if is_rerun else 'fast_static',
        checks=checks,csv_sha256=sha(root/'submission.csv'),runtime_sha256=sha(root/'evidence_early_runtime.json'),
        changed_queries=r['changed_queries'],changed_top1=r['changed_top1'],protected_queries=r['protected_queries'],
        eligible_queries=r['eligible_queries'],no_new_model_or_gain_claim=True)
    save(root/'evidence_early_audit.json',result)
    return result
