"""Real pinned-reference parity and source-gate checks; no GPU or cloud calls."""
from pathlib import Path
import copy,json,sys,time
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import external_library_overlay_20261109 as old
import external_library_variants_20261110 as new

def main():
    original=ROOT/'runs/external_overlay_actual_canary_20261109'
    out=ROOT/'runs'/('external_core_actual_canary_20261110'+('_'+sys.argv[1] if len(sys.argv)>1 else ''));out.mkdir(exist_ok=False)
    inp=original/'input';test=inp/'enveda-CASMI26-molecule-id-mass-spectra/test.parquet';source=original/'alex_function.py'
    recipe=json.loads((ROOT/'submission/optimization_20261109/mass_guarded_extlib/recipe.json').read_text());files=recipe['files']
    control=pd.read_csv(original/'hidden_actual/submission_external_control.csv',dtype=str,keep_default_na=False)
    evidence=pd.read_parquet(original/'hidden_actual/frozen_candidate_evidence.parquet')
    checks={};summaries={};actual={}
    for name,sources,trusted in [('ab',['A','B'],False),('a',['A'],False),('b',['B'],False),('trusted',['A','B'],True)]:
        work=out/name;work.mkdir();control.to_csv(work/'submission.csv',index=False);evidence.to_parquet(work/'frozen_candidate_evidence.parquet',index=False)
        config=dict(sources=sources,e_policy='none',trusted_bprec=trusted,old_helper_sha256=new.sha(ROOT/'scripts/external_library_overlay_20261109.py'),e_helper_sha256=None,enveda_file=None)
        args=(work,inp,test,True,control.molecule_id.tolist(),dict(status='passed',csv_sha256=new.sha(work/'submission.csv')),source,new.sha(source),files,config)
        started=time.monotonic();runtime=new.run(*args);audit=new.audit(*args,name,'actual_fixture');elapsed=time.monotonic()-started
        final=pd.read_csv(work/'submission.csv',dtype=str,keep_default_na=False)
        checks[name+'_actual_passed']=audit['status']=='passed'
        checks[name+'_source_counts']=all(runtime['selected_reference_counts'].get(k,0)==(new.REFERENCE_COUNTS[k] if k in sources else 0) for k in ['A','B'])
        checks[name+'_protected']=final.smiles.iloc[2]==control.smiles.iloc[2]
        checks[name+'_duplicate_guard']=final.smiles.iloc[3]==control.smiles.iloc[3]
        checks[name+'_missing_query']=final.smiles.iloc[4]==control.smiles.iloc[4]
        if name=='ab':
            reference=pd.read_csv(original/'hidden_actual/submission.csv',dtype=str,keep_default_na=False)
            oldruntime=json.loads((original/'hidden_actual/external_overlay_runtime.json').read_text())
            checks['ab_csv_exact_old']=final.equals(reference)
            checks['ab_csv_bytes_exact_old']=new.sha(work/'submission.csv')==new.sha(original/'hidden_actual/submission.csv')
            lookup={m['molecule_id']:m for m in oldruntime['actual_matches']}
            checks['ab_actual_scores_exact_old']=all((v['cosine'],v['matched_peaks'],v['smiles'])==(lookup[k]['cosine'],lookup[k]['matched_peaks'],lookup[k]['smiles']) for k,v in runtime['actual_matches'].items()) and set(lookup)==set(runtime['actual_matches'])
        checks[name+'_correction_scope']=runtime['bprec_corrected_count']==(1281 if trusted else 0)
        summaries[name]=dict(seconds=elapsed,selected_reference_counts=runtime['selected_reference_counts'],bprec_corrected_count=runtime['bprec_corrected_count'],changed_top1=runtime['changed_top1'])
        actual[name]=dict(args=args,runtime=runtime)
        print(json.dumps(dict(branch=name,status='passed',**summaries[name])),flush=True)
    # Direct real identity-guard composition fixtures isolate the critical cases.
    frame=pd.DataFrame([('q','C;CC;CCC')],columns=['molecule_id','smiles'])
    ab={'q':dict(source='A',cosine=.9,matched_peaks=4,smiles='C',above_threshold=True)}
    em={'q':dict(source='E',cosine=.99,matched_peaks=4,smiles='O',adduct='[M+H]+')}
    gap,gd,_,_=new.compose(frame,ab,em,'gap_fill',old)
    comp,cd,_,_=new.compose(frame,ab,em,'compete',old)
    checks['confirmed_unchanged_leader_blocks_gap']=gap.smiles.iloc[0]=='C;CC;CCC' and gd[0]['ab_hit_accepted']
    checks['higher_e_competes']=comp.smiles.iloc[0]=='O;C;CC;CCC' and cd[0]['e_selected']
    tied=copy.deepcopy(em);tied['q']['cosine']=.9
    checks['ab_tie_preserved']=new.compose(frame,ab,tied,'compete',old)[0].equals(frame)
    # Ethane with an alternate atom mapping has the same metric identity.
    invalid_e=copy.deepcopy(em);invalid_e['q']['smiles']='[CH3:1][CH3:2]'
    checks['invalid_e_keeps_ab']=new.compose(frame,ab,invalid_e,'compete',old)[0].equals(frame)
    invalid_ab=copy.deepcopy(ab);invalid_ab['q']['smiles']='[CH3:1][CH3:2]'
    inv,detail,_,_=new.compose(frame,invalid_ab,em,'gap_fill',old)
    checks['invalid_ab_allows_e_gap']=not detail[0]['ab_hit_accepted'] and detail[0]['e_selected']
    # Tampering only a score/policy must be rejected by actual output reconstruction.
    sample=actual['ab'];path=Path(sample['args'][0])/'external_variants_runtime.json';saved=new.read(path);bad=copy.deepcopy(saved)
    key=next(k for k,v in bad['actual_matches'].items() if v['above_threshold']);bad['actual_matches'][key]['above_threshold']=False;new.write(path,bad)
    try:new.audit(*sample['args'],'ab','actual_fixture');checks['tampered_match_rejected']=False
    except ValueError:checks['tampered_match_rejected']=True
    new.write(path,saved)
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,summaries=summaries,core_sha256=new.sha(ROOT/'scripts/external_library_variants_20261110.py'),no_gpu_or_cloud_calls=True,efficacy_evaluation=False)
    new.write(out/'verification.json',report)
    print(json.dumps(dict(status=report['status'],checks=checks),indent=2));assert all(checks.values())

if __name__=='__main__':main()
