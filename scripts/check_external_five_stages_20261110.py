"""Execute frozen final cells against real A/B/E references; no GPU or Kaggle.

This is an interface canary with constructed pre-external audit bindings. It does
not run or evaluate the full upstream MASS pipeline and makes no MRR claim.
"""
from pathlib import Path
import argparse,ast,base64,copy,hashlib,json,sys,time,zlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def read(p):return json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def src(cell):return ''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')

def inputs(out):
    old=ROOT/'runs/external_overlay_actual_canary_20261109'
    e=ROOT/'runs/enveda_matching_canary_20261110'
    a_control=pd.read_csv(old/'hidden_actual/submission_external_control.csv',dtype=str,keep_default_na=False)
    a_query=pd.read_parquet(old/'input/enveda-CASMI26-molecule-id-mass-spectra/test.parquet')
    e_control=pd.read_csv(e/'submission_control.csv',dtype=str,keep_default_na=False)
    e_query=pd.read_parquet(e/'queries.parquet')
    e_control['molecule_id']='E_'+e_control.molecule_id.astype(str)
    e_query['molecule_id']='E_'+e_query.molecule_id.astype(str)
    control=pd.concat([a_control,e_control],ignore_index=True)
    query=pd.concat([a_query,e_query],ignore_index=True)
    if not control.molecule_id.is_unique:raise ValueError('Canary IDs overlap')
    inp=out/'input';comp=inp/'enveda-CASMI26-molecule-id-mass-spectra';comp.mkdir(parents=True)
    query.to_parquet(comp/'test.parquet',index=False)
    recipe=read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/recipe.json')
    files=list(recipe['files'])+[dict(ref='egehseyinca/enveda180-casmi26-reference-ccby4',version=1,file='enveda180_hplus_hminus_references.parquet')]
    for item in files:
        target=ROOT/'assets/kaggle'/item['ref']/('v'+str(item['version']))/item['file']
        link=inp/item['ref'].split('/')[1]/item['file'];link.parent.mkdir(exist_ok=True)
        link.symlink_to(target)
    evidence=pd.read_parquet(old/'hidden_actual/frozen_candidate_evidence.parquet')
    e_rows=[dict(molecule_id=str(mid),library_max=0.) for mid in e_control.molecule_id]
    evidence=pd.concat([evidence,pd.DataFrame(e_rows)],ignore_index=True)
    return inp,comp,control,evidence

def scope_for(work,inp,comp,control,evidence,full):
    work.mkdir();code=work/'code';code.mkdir();control.to_csv(work/'submission.csv',index=False)
    evidence.to_parquet(work/'frozen_candidate_evidence.parquet',index=False)
    base=dict(status='passed',csv_sha256=sha(work/'submission.csv'))
    return dict(Path=Path,pd=pd,ROOT=work,INPUT=inp,COMP=comp,CODE=code,IS_RERUN=full,
        SAMPLE_IDS=control.molecule_id.tolist(),GUARDED_TAIL_AUDIT=base),base

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',default='final');p.add_argument('--branches',nargs='+');a=p.parse_args()
    names=a.branches or [x['name'] for x in read(ROOT/'reports/optimization_20261110/submission_plan.json')['branches']]
    out=ROOT/'runs'/('external_five_stages_canary_20261110_'+a.tag);out.mkdir(exist_ok=False)
    inp,comp,control,evidence=inputs(out);results={}
    for name in names:
        stage=ROOT/'submission/optimization_20261110'/name;book=read(stage/'notebook.ipynb');recipe=read(stage/'recipe.json');source=src(book['cells'][-1]);book_pin=sha(stage/'notebook.ipynb')
        for full in (False,True):
            mode='hidden' if full else 'fast';work=out/(name+'_'+mode);scope,base=scope_for(work,inp,comp,control,evidence,full)
            started=time.monotonic();exec(compile(source,'exact_staged_final_cell','exec'),scope)
            report=scope['EXTERNAL_VARIANTS_REPORT'];audit=scope['EXTERNAL_VARIANTS_AUDIT'];final=pd.read_csv(work/'submission.csv',dtype=str,keep_default_na=False)
            checks=dict(actual_stage_passed=audit['status']=='passed',actual_installed_source_pins=audit['installed_payload_pins']==recipe['payload_pins'],
                all_observer_checks=all(x is True for x in audit['checks'].values()),query_ids_exact=final.molecule_id.tolist()==control.molecule_id.tolist(),
                actual_preinstall_control_bound=sha(work/'submission_external_preinstall_control.csv')==base['csv_sha256'],
                original_source_control_bound=report['control_sha256']==base['csv_sha256'],matching_mode=report['library_matching_performed'] is full,
                frozen_notebook_unchanged=sha(stage/'notebook.ipynb')==book_pin)
            if full:
                selected=set(recipe['configuration']['sources'])-{'E'}
                checks['selected_sources_actual']=all(report['selected_reference_counts'].get(k,0)==({'A':200724,'B':124160}[k] if k in selected else 0) for k in ('A','B'))
                checks['actual_scored_order_consumed']=audit['checks']['actual_scores_consumed'] is True
                checks['trusted_bprec_actual_scope']=report['bprec_corrected_count']==(1281 if recipe['configuration']['trusted_bprec'] else 0)
                if 'E' in recipe['configuration']['sources']:
                    ea=report['enveda_audit'];checks['actual_e_scoring']=ea['status']=='passed' and ea['source_rows_total']==730252 and ea['scored_pairs']>0 and ea['returned_hits']>0
            else:checks['fast_exact_control']=final.equals(control)
            results[name+'_'+mode]=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,seconds=time.monotonic()-started,notebook_sha256=book_pin)
            if not all(checks.values()):raise ValueError('Staged final cell checks failed: '+repr(checks))
            print(json.dumps(dict(branch=name,mode=mode,status='passed',seconds=time.monotonic()-started)),flush=True)
        # An actual corrupted installed payload must fail before model/matching
        # and remove final output while retaining the preinstall control.
        work=out/(name+'_bad_payload');scope,base=scope_for(work,inp,comp,control,evidence,False)
        tree=ast.parse(source);assignment=next(x for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_variant_payloads' for t in x.targets))
        packed=ast.literal_eval(assignment.value);packed[next(iter(packed))]=base64.b64encode(zlib.compress(b'bad')).decode();assignment.value=ast.parse(repr(packed),mode='eval').body;ast.fix_missing_locations(tree)
        try:exec(compile(tree,'corrupted_payload_fixture','exec'),scope);closed=False
        except AssertionError:closed=not (work/'submission.csv').exists() and sha(work/'submission_external_preinstall_control.csv')==base['csv_sha256']
        results[name+'_bad_payload']=dict(status='passed' if closed else 'failed',checks=dict(actual_bad_payload_fails_closed=closed),notebook_sha256=book_pin)
        if not closed:raise ValueError('Corrupt payload did not fail closed')
    result=dict(status='passed',branches=results,upstream_MASS_pipeline_executed=False,known_pretrained_exposure=True,
        real_reference_selfmatch_interface_canary=True,gpu_used=False,cloud_or_submission_writes=False,efficacy_or_MRR_evaluation=False)
    write(out/'verification.json',result)
    summary=ROOT/'reports/external_five_stages_canary_20261110.json';write(summary,dict(status='passed',actual_report=str((out/'verification.json').relative_to(ROOT)),branches={k:v['status'] for k,v in results.items()},full_upstream_inference=False))
    print(json.dumps(dict(status='passed',actual_staged_cases=len(results),report=str(out/'verification.json'))))

if __name__=='__main__':main()
