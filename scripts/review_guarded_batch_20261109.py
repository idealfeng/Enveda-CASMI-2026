"""Run staged guard functions/observers on synthetic scores; no model invocation."""
from pathlib import Path
import ast,copy,hashlib,importlib.util,json,sys,tempfile,types
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_guarded_batch_20261109 import source
BASELINE=ROOT/'runs/validation_flex_c2_20261105d/p2s_code/neural_scores.py'
BUNDLE=ROOT/'runs/guarded_tail_actual_canary_20261108/bundle'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')

def fixture(stage,scenario='valid',fast=False):
    nb=read(stage/'notebook.ipynb');recipe=read(stage/'recipe.json');cfg=recipe['configuration'];prefix=cfg['protected_prefix'];late=ast.parse(source(nb['cells'][-2]));observer=source(nb['cells'][-1])
    # Execute the actual installer and stop immediately before the real run.
    protected=['C','CC','CCC','CCCC','CCCCC','CCCCCC','CCCCCCC']
    tail=['CCCO','CCCCO','CC(O)C','CCC(O)C','CCOC','CCOCC','CCN','CNC','CCS','CSC']
    candidate=protected+tail
    with tempfile.TemporaryDirectory(prefix='guard1109-',dir=ROOT/'.cache/tmp-linux') as temp:
        root=Path(temp);code=root/'code';code.mkdir();(code/'neural_scores.py').write_bytes(BASELINE.read_bytes())
        before=pd.DataFrame([('q0',';'.join(candidate)),('bad',';'.join(candidate[:-1]+['badSMILES'])),('missing',';'.join(candidate)),('short',';'.join(candidate)),('duplicate',';'.join(candidate+['OCCC']))],columns=['molecule_id','smiles']);before.to_csv(root/'submission.csv',index=False)
        class Intercept:
            def run(self,*args,**kwargs):return None
        actual_import=__import__('importlib.util',fromlist=['util']);original_loader=actual_import.module_from_spec
        # AST slice preserves all installer statements but omits the final run.
        try_node=next(n for n in late.body if isinstance(n,ast.Try))
        run_index=next(i for i,n in enumerate(try_node.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GUARDED_TAIL_REPORT' for t in n.targets))
        install_tree=copy.deepcopy(late);next(n for n in install_tree.body if isinstance(n,ast.Try)).body=try_node.body[:run_index]
        scope=dict(ROOT=root,CODE=code);exec(compile(ast.fix_missing_locations(install_tree),'actual_install','exec'),scope);module=scope['_guarded_tail']
        q=pd.DataFrame([dict(molecule_id=mid,ms2_mzs=[20.,30.,40.],ms2_normalized_intensities=[1.,.7,.4],precursor_mz=100.,adduct='[M+H]+',ionization_mode='positive',collision_energy_ev='20') for mid in ['q0','bad','short','duplicate']])
        q.at[2,'ms2_mzs']=[20.];q.at[2,'ms2_normalized_intensities']=[1.]
        if scenario=='no_eligible':
            for i in q.index:q.at[i,'ms2_mzs']=[20.];q.at[i,'ms2_normalized_intensities']=[1.]
        q.to_parquet(root/'effective_query_spectra.parquet',index=False)
        base=dict(status='passed',csv_sha256=sha(root/'submission.csv'))
        if scenario=='bad_control':base['csv_sha256']='0'*64
        def fake(cmd,**kwargs):
            if scenario=='model_fail':return types.SimpleNamespace(returncode=1,stdout='fixture')
            e=pd.read_parquet(root/'guarded_tail_evidence.parquet');scores=e.copy();scores['neural_ok']=True;scores['neural_score']=scores.baseline_rank.astype(float);scores.to_parquet(root/'guarded_tail_scores.parquet',index=False)
            audit=dict(status='passed',role='learned_v2' if cfg['score_mode']=='learned_heads' else 'frozen_v2_mean',head_applied=cfg['score_mode']=='learned_heads',encoder_sha256=module.V2_SHA,heads=cfg['head_receipts'],evidence_sha256=sha(root/'guarded_tail_evidence.parquet'),queries_sha256=sha(root/'effective_query_spectra.parquet'),output_sha256=sha(root/'guarded_tail_scores.parquet'),input_rows=len(e),output_rows=len(scores),scored_candidate_rows=len(scores),scored_queries=int(scores.molecule_id.nunique()),errors=[]);write(root/'guarded_tail_scores.parquet.head_audit.json',audit)
            return types.SimpleNamespace(returncode=0,stdout='fixture synthetic scores, no model')
        module.subprocess=types.SimpleNamespace(run=fake,PIPE=-1,STDOUT=-2)
        try:report=module.run(root,code,BUNDLE,not fast,base,cfg,device='cpu')
        except (RuntimeError,ValueError):return dict(accepted=False,closed=not (root/'submission.csv').exists(),control=(root/'submission_guarded_tail_control.csv').exists())
        after=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
        direct=dict(prefix=all(a.split(';')[:prefix]==b.split(';')[:prefix] for a,b in zip(before.smiles,after.smiles)),bad=before.iloc[1].smiles==after.iloc[1].smiles,missing=before.iloc[2].smiles==after.iloc[2].smiles,short=before.iloc[3].smiles==after.iloc[3].smiles,duplicate=before.iloc[4].smiles==after.iloc[4].smiles,changed=fast or scenario=='no_eligible' or before.iloc[0].smiles!=after.iloc[0].smiles)
        if scenario in ('bad_prefix','bad_candidate','cross_formula','wrong_score_order'):
            parts=after.at[0,'smiles'].split(';')
            if scenario=='bad_prefix':parts[0],parts[-1]=parts[-1],parts[0]
            elif scenario=='bad_candidate':parts[-1]='CCCCCCCCO'
            elif scenario=='cross_formula':parts[7],parts[8]=parts[8],parts[7]
            else:parts[7],parts[9]=parts[9],parts[7]
            after.at[0,'smiles']=';'.join(parts);after.to_csv(root/'submission.csv',index=False);report['output_sha256']=sha(root/'submission.csv')
        elif scenario=='bad_config':report['configuration_sha256']='0'*64
        elif scenario=='bad_coverage':
            p=root/'guarded_tail_scores.parquet.head_audit.json';a=read(p);a['scored_candidate_rows']=0;write(p,a);report['head_audit_sha256']=sha(p)
        elif scenario=='bad_role':
            p=root/'guarded_tail_scores.parquet.head_audit.json';a=read(p);a['role']='wrong';write(p,a);report['head_audit_sha256']=sha(p)
        elif scenario=='bad_source':(code/'guarded_head_tail_20261109.py').write_bytes(b'bad')
        elif scenario=='bad_weights':(code/next(iter(cfg['payload_pins']))).write_bytes(b'bad')
        write(root/'guarded_tail_runtime.json',report)
        scope.update(pd=pd,Path=Path,BATCH_VARIANT_AUDIT=base,IS_RERUN=not fast,RUN_PIPELINE=not fast,PIPELINE_DONE=not fast,SAMPLE_IDS=before.molecule_id.tolist())
        try:exec(compile(observer,'actual_observer','exec'),scope);return dict(accepted=True,direct=direct,checks=scope['GUARDED_TAIL_AUDIT']['checks'])
        except (ValueError,AssertionError,KeyError):return dict(accepted=False,direct=direct)

def main():
    names=sys.argv[1:] or ['mass_guarded_oldhead_p3','mass_guarded_oldhead_p1','mass_guarded_v2mean_p7'];result={}
    for name in names:
        stage=ROOT/'submission/optimization_20261109'/name
        valid=fixture(stage);fast=fixture(stage,fast=True);empty=fixture(stage,'no_eligible');fail=fixture(stage,'model_fail');control=fixture(stage,'bad_control')
        rejected={n:fixture(stage,n) for n in ['bad_prefix','bad_candidate','cross_formula','wrong_score_order','bad_config','bad_coverage','bad_role','bad_source','bad_weights']}
        checks=dict(valid=valid['accepted'],fast=fast['accepted'],no_eligible=empty['accepted'],model_closed=fail.get('closed') and fail.get('control'),control_closed=control.get('closed') and control.get('control'),**valid['direct'],**{k+'_rejected':not v['accepted'] for k,v in rejected.items()})
        result[name]=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,source_sha256=sha(stage/'notebook.ipynb'),valid=valid,rejected=rejected)
    out=ROOT/'reports/guarded_batch_review_20261109';out.mkdir(parents=True,exist_ok=True);write(out/'verification.json',dict(status='passed' if all(v['status']=='passed' for v in result.values()) else 'failed',branches=result,no_real_model_calls=True))
    print(json.dumps({k:dict(status=v['status'],checks_passed=sum(bool(x) for x in v['checks'].values()),checks_total=len(v['checks'])) for k,v in result.items()}));assert all(v['status']=='passed' for v in result.values())
if __name__=='__main__':main()
