"""Candidate reranking from target-target spectra; original strong reference hits stay fixed.

Uses the publicly archived N1c function without changing its score arithmetic.
Only observations and a returned graph are added. No labels or new candidates.
"""
from pathlib import Path
from collections import Counter
import ast
import hashlib
import json
import shutil

CONFIG=dict(lam=.25,tau=.6,matched_peaks=6,protect_original_library=.9,
            protect_accepted_ab=True,scope='post_AB_original_candidates')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')


class Observe(ast.NodeTransformer):
    def __init__(self):self.sites=0
    def visit_Assign(self,node):
        node=self.generic_visit(node)
        if any(isinstance(t,ast.Name) and t.id=='o' for t in node.targets) and 'LAM' in ast.unparse(node.value):
            self.sites+=1
            return [node,ast.copy_location(ast.parse('_observe_network(m,lst,base,N,nb_,o)').body[0],node)]
        return node


def function(path,pin,observations):
    if sha(path)!=pin:raise ValueError('Pinned public network source changed')
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_n1c')
    observer=Observe();fn=observer.visit(fn)
    if observer.sites!=1:raise ValueError('Public score observation site changed')
    fn.body.append(ast.parse("return dict(graph=E,spectra_molecules=len(K),edges=sum(len(v) for v in E.values())//2)").body[0])
    def capture(mid,candidates,base,support,neighbors,order):
        observations[str(mid)]=dict(candidates=list(candidates),base=base.tolist(),support=support.tolist(),
                                   neighbors=[[str(m),float(w)] for m,w in neighbors],order=order.tolist())
    scope={'_observe_network':capture}
    ast.fix_missing_locations(fn)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'pinned_public_network','exec'),scope)
    return scope['_n1c']


def protections(root,base_audit,old):
    import pandas as pd
    runtime_path=root/'external_overlay_runtime.json'
    if sha(runtime_path)!=base_audit.get('runtime_report_sha256'):raise ValueError('Actual AB runtime unbound')
    runtime=read(runtime_path)
    if runtime.get('output_sha256')!=sha(root/'submission.csv'):raise ValueError('AB runtime final mismatch')
    invalid={str(r['molecule_id']) for r in runtime.get('details',[]) if r.get('validity_guard_preserved_control')}
    protected={str(r['molecule_id']) for r in runtime.get('actual_matches',[])
               if r.get('above_threshold') and str(r['molecule_id']) not in invalid}
    evidence=root/'frozen_candidate_evidence.parquet'
    pins={}
    if evidence.exists():
        v=pd.read_parquet(evidence,columns=['molecule_id','library_max'])
        protected.update(str(m) for m,s in v.groupby('molecule_id',sort=False).library_max.first().items() if float(s)>=.9)
        pins['library_evidence_sha256']=sha(evidence)
    pins['ab_runtime_sha256']=sha(runtime_path)
    return protected,pins


def run(root,input_root,test_path,is_rerun,sample_ids,base_audit,source,source_pin,branch,recipe_pin):
    import pandas as pd
    import external_library_overlay_20261109 as original
    root=Path(root);control=root/'submission_network_control.csv'
    try:
        if base_audit.get('status')!='passed' or base_audit.get('csv_sha256')!=sha(root/'submission.csv'):
            raise ValueError('Original champion AB output is unbound')
        if sha(source)!=source_pin:raise ValueError('Network source pin')
        shutil.copy2(root/'submission.csv',control)
        old=pd.read_csv(control,dtype=str,keep_default_na=False)
        if list(old.columns)!=['molecule_id','smiles'] or old.molecule_id.tolist()!=list(sample_ids) or not old.molecule_id.is_unique:
            raise ValueError('Original CSV IDs invalid')
        if not all(original.valid(s) for s in old.smiles):raise ValueError('Original official identities invalid')
        report=dict(status='fast_static_no_network',branch=branch,recipe_sha256=recipe_pin,configuration=CONFIG,
            control_sha256=sha(control),base_audit_csv_sha256=base_audit['csv_sha256'],
            public_function_sha256=source_pin,module_sha256=sha(__file__),observations={},accepted_ids=[],
            protected_ids=[],new_candidates=0,changed_queries=0,changed_top1=0,network_executed=False)
        if is_rerun:
            protected,pins=protections(root,base_audit,old)
            observations={};fn=function(source,source_pin,observations)
            work=root/'network_work';work.mkdir(exist_ok=False)
            shutil.copy2(control,work/'submission.csv')
            # Public function locates test.parquet recursively; pass only its explicit parent.
            if Path(test_path).name!='test.parquet':raise ValueError('Explicit test.parquet required')
            graph=fn(work=str(work),inp=str(Path(test_path).parent),LAM=CONFIG['lam'],TAU=CONFIG['tau'])
            proposed=pd.read_csv(work/'submission.csv',dtype=str,keep_default_na=False)
            if not proposed.molecule_id.equals(old.molecule_id):raise ValueError('Proposal query order changed')
            final=old.copy();accepted=[]
            for i,(mid,before,after) in enumerate(zip(old.molecule_id,old.smiles,proposed.smiles)):
                if mid in protected or after==before:continue
                if Counter(before.split(';'))!=Counter(after.split(';')) or not original.valid(after):
                    raise ValueError('Network candidate multiset changed')
                final.loc[i,'smiles']=after;accepted.append(mid)
            proposed.to_csv(root/'submission_network_proposed.csv',index=False)
            final.to_csv(root/'submission.csv',index=False)
            report.update(status='applied',network_executed=True,observations=observations,
                accepted_ids=accepted,protected_ids=sorted(protected),pins=pins,test_sha256=sha(test_path),
                graph=graph,changed_queries=int((final.smiles!=old.smiles).sum()),
                changed_top1=sum(a.split(';')[0]!=b.split(';')[0] for a,b in zip(old.smiles,final.smiles)))
        report['output_sha256']=sha(root/'submission.csv')
        save(root/'spectral_network_runtime.json',report)
        return report
    except BaseException:
        (root/'submission.csv').unlink(missing_ok=True)
        raise


def audit(root,is_rerun,sample_ids,base_audit,source,source_pin,branch,recipe_pin,module_pin):
    import numpy as np
    import pandas as pd
    import external_library_overlay_20261109 as original
    root=Path(root);r=read(root/'spectral_network_runtime.json')
    control=pd.read_csv(root/'submission_network_control.csv',dtype=str,keep_default_na=False)
    final=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
    checks=dict(base_ab_passed=base_audit.get('status')=='passed',control_bound=sha(root/'submission_network_control.csv')==base_audit['csv_sha256']==r['control_sha256'],
        final_bound=sha(root/'submission.csv')==r['output_sha256'],module_pin=sha(__file__)==module_pin==r['module_sha256'],
        public_source_pin=sha(source)==source_pin==r['public_function_sha256'],
        configuration_exact=r['configuration']==CONFIG,recipe_branch_bound=r['branch']==branch and r['recipe_sha256']==recipe_pin,
        sample_ids_exact=final.molecule_id.tolist()==list(sample_ids) and final.molecule_id.is_unique,
        candidate_multisets=all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(control.smiles,final.smiles)),
        official_identities=all(original.valid(s) for s in final.smiles))
    expected=control.copy()
    if is_rerun:
        protected=set(r['protected_ids'])
        for i,(mid,raw) in enumerate(zip(control.molecule_id,control.smiles)):
            observation=r['observations'].get(mid)
            if not observation or mid in protected:continue
            if observation['candidates']!=raw.split(';'):raise ValueError('Observed candidate order mismatch')
            base=np.asarray(observation['base']);support=np.asarray(observation['support'])
            exact_base=-np.log(np.arange(1,len(base)+1))
            if not np.array_equal(base,exact_base):raise ValueError('Network original rank scores differ')
            z=lambda x:(x-x.mean())/(x.std()+1e-9)
            order=np.argsort(-(z(base)+.25*z(support)),kind='stable')
            if order.tolist()!=observation['order']:raise ValueError('Actual network score not consumed')
            expected.loc[i,'smiles']=';'.join(observation['candidates'][int(j)] for j in order)
        checks.update(network_really_executed=r['network_executed'] is True,
            actual_score_consumption=expected.equals(final),reference_protection=all(a==b for mid,a,b in zip(control.molecule_id,control.smiles,final.smiles) if mid in protected),
            ab_runtime_pin=sha(root/'external_overlay_runtime.json')==r['pins']['ab_runtime_sha256'])
    else:checks['fast_no_network']=r['network_executed'] is False and expected.equals(final)
    if not all(checks.values()):
        (root/'submission.csv').unlink(missing_ok=True)
        raise ValueError('Spectral network output audit failed')
    result=dict(status='passed',branch=branch,recipe_sha256=recipe_pin,mode='hidden_full' if is_rerun else 'fast_static',
                checks=checks,csv_sha256=sha(root/'submission.csv'),runtime_sha256=sha(root/'spectral_network_runtime.json'),
                changed_queries=r['changed_queries'],changed_top1=r['changed_top1'],no_gain_claim=True)
    save(root/'spectral_network_audit.json',result);return result
