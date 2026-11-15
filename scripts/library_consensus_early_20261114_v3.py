"""Fixed multi-spectrum measured-library support on the original candidate slots.

The original Alex V12 loaders, precursor windows and cosine arithmetic are used
verbatim. Its whole-query library-confidence skip is disabled in this second
pass; the original winner is not consumed. Actual per-reference pair scores are
observed and aggregated over distinct query spectra for existing candidates.
"""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import ast
import hashlib
import json
import math
import shutil

CONFIG = dict(pair_min_cosine=.60, pair_min_peaks=4, minimum_support_spectra=2,
              rank_weight=1., support_weight=1., protected_prefix=0,
              protect_accepted_ab=True, same_formula_slots=True,
              source_reference_algorithm='Alex V12 original precursor window and cosine')
SOURCE_PIN = '9ceaa95ddda0fb304758c9acd7dd1f256c528fcb4a8304c0152f8b6d8e3e3e76'
GUARD_PIN = 'a31c55a2958139cbeea948ea4d11fa32eb40e3d3d7b0bac157f6d0fdc51025db'


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f, 'sha256').hexdigest()


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')


@lru_cache(maxsize=100000)
def formula(smiles):
    from rdkit import Chem
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula
    mol=Chem.MolFromSmiles(smiles)
    return CalcMolFormula(mol) if mol is not None else None


class Instrument(ast.NodeTransformer):
    def __init__(self):self.query_sites=0;self.pair_sites=0;self.guard_sites=0;self.reference_sites=0
    def visit_Assign(self,node):
        node=self.generic_visit(node)
        names=[x.id for t in node.targets for x in ast.walk(t) if isinstance(x,ast.Name)]
        if names==['lib_max'] and isinstance(node.value,ast.Dict):
            self.query_sites+=1
            call=ast.parse('_observe_queries(queries)').body[0]
            return [ast.copy_location(call,node),node]
        if names==['cos','n_matched']:
            self.pair_sites+=1
            call=ast.parse('_observe_pair(mid,q,ref,cos,n_matched)').body[0]
            return [node,ast.copy_location(call,node)]
        return node
    def visit_If(self,node):
        node=self.generic_visit(node)
        if ast.unparse(node.test)=='lib_max.get(mid, 0.0) >= LIB_TAU':
            self.guard_sites+=1;node.test=ast.Constant(value=False)
        return node
    def visit_Expr(self,node):
        node=self.generic_visit(node);c=node.value
        if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and isinstance(c.func.value,ast.Name) and c.func.value.id=='refs' and c.func.attr=='append':
            self.reference_sites+=1
            label='A' if any(isinstance(x,ast.Name) and x.id=='key' for x in ast.walk(c.args[0])) else 'B'
            call=ast.parse('_observe_reference('+repr(label)+',refs[-1])').body[0]
            return [node,ast.copy_location(call,node)]
        return node


def observed_function(source,callbacks):
    if sha(source)!=SOURCE_PIN:raise ValueError('Original library source pin changed')
    tree=ast.parse(Path(source).read_text(encoding='utf-8'))
    mod=Instrument();tree=mod.visit(tree);ast.fix_missing_locations(tree)
    sites=dict(queries=mod.query_sites,pairs=mod.pair_sites,whole_query_skip_disabled=mod.guard_sites,references=mod.reference_sites)
    if sites!=dict(queries=1,pairs=1,whole_query_skip_disabled=1,references=2):raise ValueError('Original pair observation sites changed')
    scope=dict(callbacks);exec(compile(tree,'actual_library_pair_observer','exec'),scope)
    return scope['_apex_extlib_overlay'],sites


def protected_ids(root,base):
    runtime=root/'external_overlay_runtime.json'
    if sha(runtime)!=base.get('runtime_report_sha256'):raise ValueError('AB runtime unbound')
    r=read(runtime)
    if r.get('output_sha256')!=base.get('csv_sha256'):raise ValueError('AB output unbound')
    invalid={str(x['molecule_id']) for x in r.get('details',[]) if x.get('validity_guard_preserved_control')}
    return {str(x['molecule_id']) for x in r.get('actual_matches',[]) if x.get('above_threshold') and str(x['molecule_id']) not in invalid}


def reorder(raw,values):
    """Pure, fixed ranking policy; stable order breaks equal scores."""
    guesses=raw.split(';');groups={}
    for i,s in enumerate(guesses):
        f=formula(s)
        if i>=CONFIG['protected_prefix'] and f is not None:groups.setdefault(f,[]).append(i)
    final=list(guesses);observations=[]
    for f,slots in groups.items():
        if len(slots)<2:continue
        eligible=[i for i in slots if values[i]['supported_spectra']>=CONFIG['minimum_support_spectra']]
        if not eligible:continue
        scores={i:-math.log(i+1)*CONFIG['rank_weight']+values[i]['consensus']*CONFIG['support_weight'] for i in slots}
        order=sorted(slots,key=lambda i:(-scores[i],i))
        for dst,src in zip(slots,order):final[dst]=guesses[src]
        observations.append(dict(formula=f,slots=slots,source_order=order,scores=[scores[i] for i in slots]))
    return ';'.join(final),observations


def run(root,input_root,test_path,is_rerun,sample_ids,base,source,files,branch,recipe_pin):
    import numpy as np
    import pandas as pd
    import external_library_overlay_20261109 as guard
    root=Path(root);source=Path(source);control=root/'submission_library_consensus_control.csv'
    try:
        if sha(Path(guard.__file__))!=GUARD_PIN:raise ValueError('Official guard source changed')
        if base.get('status')!='passed' or base.get('csv_sha256')!=sha(root/'submission.csv'):raise ValueError('Parent AB output unbound')
        sources=guard.resolve_sources(input_root,files,test_path)
        if sha(source)!=SOURCE_PIN:raise ValueError('Library pair source pin')
        shutil.copy2(root/'submission.csv',control)
        old=pd.read_csv(control,dtype=str,keep_default_na=False)
        if list(old.columns)!=['molecule_id','smiles'] or old.molecule_id.tolist()!=list(sample_ids) or not old.molecule_id.is_unique:raise ValueError('Actual parent IDs invalid')
        if not all(guard.valid(s) for s in old.smiles):raise ValueError('Actual parent identities invalid')
        r=dict(status='fast_static_no_pair_matching',branch=branch,recipe_sha256=recipe_pin,configuration=CONFIG,
               control_sha256=sha(control),output_sha256=sha(root/'submission.csv'),source_sha256=SOURCE_PIN,
               module_sha256=sha(__file__),libraries=sources,pair_matching_executed=False,
               protected_ids=[],query_rows=[],reference_counts={},changed_queries=0,changed_top1=0,new_candidates=0)
        if is_rerun:
            # Read only actual official spectrum columns. No target structure labels.
            query=pd.read_parquet(test_path,columns=['molecule_id','spectrum_id','ms2_mzs','ms2_normalized_intensities','adduct','precursor_mz','ionization_mode'])
            if set(query.molecule_id.astype(str))!=set(sample_ids):raise ValueError('Actual test identity scope differs')
            protected=protected_ids(root,base)
            rowmap={str(mid):raw.split(';') for mid,raw in old.itertuples(index=False,name=None)}
            keymap={mid:{guard.identity(s):i for i,s in enumerate(arr)} for mid,arr in rowmap.items()}
            qmap={};qcounts={};best={};pair_count=0;qualified=0;reference_counts=Counter()
            def observe_queries(queries):
                for mid,qs in queries.items():
                    # Repeated exact spectra do not count as independent support.
                    seen={}
                    for q in qs:
                        token=(q['mode'],q['prec'],np.asarray(q['mz'],dtype=np.float64).tobytes(),np.asarray(q['it'],dtype=np.float64).tobytes())
                        if token not in seen:seen[token]=len(seen)
                        qmap[id(q)]=(mid,seen[token])
                    qcounts[mid]=len(seen)
            def observe_reference(label,row):reference_counts[label]+=1
            def observe_pair(mid,q,ref,cos,peaks):
                nonlocal pair_count,qualified
                pair_count+=1
                if mid in protected or peaks<CONFIG['pair_min_peaks'] or not math.isfinite(float(cos)) or cos<CONFIG['pair_min_cosine']:return
                mid=str(mid);key=guard.identity(ref[5]);candidate=keymap[mid].get(key)
                if candidate is None:return
                qmid,index=qmap[id(q)]
                if qmid!=mid:raise ValueError('Observed spectrum/molecule scope differs')
                qualified+=1;indexkey=(mid,candidate,index)
                best[indexkey]=max(best.get(indexkey,0.),float(cos))
            fn,sites=observed_function(source,dict(_observe_queries=observe_queries,_observe_reference=observe_reference,_observe_pair=observe_pair))
            work=root/'library_consensus_pair_work';work.mkdir(exist_ok=False)
            shutil.copy2(control,work/'submission.csv')
            # The private second-pass winner CSV is deliberately never applied.
            fn(work=str(work),inp=str(input_root))
            if reference_counts!=Counter(A=200724,B=124160):raise ValueError('Actual original reference scope changed')
            if set(qcounts)!=set(sample_ids):raise ValueError('Observed actual spectrum scope changed')
            final=old.copy();rows=[]
            for i,(mid,raw) in enumerate(old.itertuples(index=False,name=None)):
                arr=rowmap[mid];n=qcounts[mid];values=[]
                for j,s in enumerate(arr):
                    support=[best.get((mid,j,k),0.) for k in range(n)]
                    count=sum(v>=CONFIG['pair_min_cosine'] for v in support)
                    consensus=.5*sum(support)/max(n,1)+.5*count/max(n,1)
                    values.append(dict(smiles=s,per_spectrum_max=support,supported_spectra=count,consensus=consensus))
                new,groups=(raw,[]) if mid in protected else reorder(raw,values)
                if Counter(raw.split(';'))!=Counter(new.split(';')) or not guard.valid(new):raise ValueError('Consensus altered candidate identities')
                final.loc[i,'smiles']=new
                rows.append(dict(molecule_id=mid,query_spectra=n,protected=mid in protected,changed=new!=raw,
                                 candidate_support=values,formula_groups=groups))
            final.to_csv(root/'submission.csv',index=False)
            r.update(status='applied',pair_matching_executed=True,protected_ids=sorted(protected),query_rows=rows,
                     reference_counts=dict(reference_counts),observation_sites=sites,test_sha256=sha(test_path),
                     pairs_observed=pair_count,qualified_candidate_pairs=qualified,actual_test_spectra=len(query),
                     eligible_queries=sum(any(v['supported_spectra']>=CONFIG['minimum_support_spectra'] for v in row['candidate_support'][1:]) and not row['protected'] for row in rows),
                     changed_queries=int((final.smiles!=old.smiles).sum()),changed_top1=sum(a.split(';')[0]!=b.split(';')[0] for a,b in zip(old.smiles,final.smiles)),
                     output_sha256=sha(root/'submission.csv'))
        save(root/'library_consensus_runtime.json',r);return r
    except BaseException:
        (root/'submission.csv').unlink(missing_ok=True);raise


def audit(root,is_rerun,sample_ids,base,source,branch,recipe_pin,module_pin):
    import pandas as pd
    import external_library_overlay_20261109 as guard
    root=Path(root);r=read(root/'library_consensus_runtime.json')
    old=pd.read_csv(root/'submission_library_consensus_control.csv',dtype=str,keep_default_na=False)
    final=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
    checks=dict(parent_AB_passed=base.get('status')=='passed',control_bound=sha(root/'submission_library_consensus_control.csv')==base.get('csv_sha256')==r['control_sha256'],
                final_bound=sha(root/'submission.csv')==r['output_sha256'],source_pin=sha(source)==SOURCE_PIN==r['source_sha256'],
                module_pin=sha(__file__)==module_pin==r['module_sha256'],recipe_branch_bound=r['branch']==branch and r['recipe_sha256']==recipe_pin,
                actual_configuration=r['configuration']==CONFIG,exact_ids_schema=list(final.columns)==['molecule_id','smiles'] and final.molecule_id.tolist()==old.molecule_id.tolist()==list(sample_ids),
                original_candidate_multisets=all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(old.smiles,final.smiles)),
                official_identity_validity=all(guard.valid(s) for s in final.smiles),configured_prefix_preserved=all(a.split(';')[:CONFIG['protected_prefix']]==b.split(';')[:CONFIG['protected_prefix']] for a,b in zip(old.smiles,final.smiles)))
    if is_rerun:
        rows={x['molecule_id']:x for x in r['query_rows']};expected=[]
        for mid,raw in old.itertuples(index=False,name=None):
            row=rows[mid];new,groups=(raw,[]) if row['protected'] else reorder(raw,row['candidate_support'])
            if groups!=row['formula_groups']:raise ValueError('Actual fixed score order not consumed')
            expected.append(new)
        checks.update(actual_pair_matching=r['status']=='applied' and r['pair_matching_executed'] is True,
                      actual_reference_counts=r['reference_counts']==dict(A=200724,B=124160),
                      actual_scores_consumed=final.smiles.tolist()==expected,
                      strong_AB_protected=all(a==b for mid,a,b in zip(old.molecule_id,old.smiles,final.smiles) if mid in set(r['protected_ids'])),
                      all_queries_observed=set(rows)==set(sample_ids))
    else:checks['fast_no_pair_matching']=r['pair_matching_executed'] is False and final.equals(old)
    if not all(checks.values()):raise ValueError('Consensus observer failed '+repr(checks))
    report=dict(status='passed',branch=branch,recipe_sha256=recipe_pin,mode='hidden_full' if is_rerun else 'fast_static',
                checks=checks,csv_sha256=sha(root/'submission.csv'),runtime_report_sha256=sha(root/'library_consensus_runtime.json'),
                changed_queries=r['changed_queries'],changed_top1=r['changed_top1'])
    save(root/'library_consensus_audit.json',report);return report
