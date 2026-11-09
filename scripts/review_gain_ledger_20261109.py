"""Exercise gain recording in isolated D-drive fixtures, never the real ledger/API."""
from pathlib import Path
from contextlib import contextmanager
import copy,hashlib,json,sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import kaggle_batch as batch
import watch_batch_with_ledger_20261109 as ledger_module

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='gain-ledger-',dir=ROOT/'.cache/tmp') as name:
        root=Path(name);reports=root/'reports';reports.mkdir();stage=root/'stage';stage.mkdir()
        write(reports/'improvement_ledger.json',dict(schema_version=1,current_best=.482,records=[dict(ref=1001+i,after=.479+i*.001) for i in range(4)]))
        (reports/'IMPROVEMENT_LEDGER.md').write_text('# Fixture ledger\n',encoding='utf-8')
        write(stage/'notebook.ipynb',dict(cells=[dict(cell_type='code',source='assert True\n')],nbformat=4,nbformat_minor=5,metadata={}))
        write(stage/'kernel-metadata.json',dict(id='stormseye/review-gain-only',code_file='notebook.ipynb',is_private=True,enable_internet=False,enable_gpu=True,kernel_type='notebook',competition_sources=[batch.COMPETITION],dataset_sources=['owner/data/1'],kernel_sources=[]))
        write(stage/'recipe.json',dict(method='isolated fixture',new_training=False))
        spec=dict(name='mass_guarded_oldhead_p3',target='stormseye/review-gain-only',version=1,stage_dir='stage',description='isolated review only',notebook_sha256=sha(stage/'notebook.ipynb'),metadata_sha256=sha(stage/'kernel-metadata.json'),static_review_path='stage/static_review.json',validation_mode='fast_static',required_runtime_audits=[dict(name='fixture_audit.json',expected_fields=dict(branch='mass_guarded_oldhead_p3',recipe_sha256=sha(stage/'recipe.json')),required_true_checks=['fixture'])])
        write(stage/'static_review.json',dict(status='passed',target=spec['target'],version=1,notebook_sha256=spec['notebook_sha256'],checks=dict(fixture=True)))
        manifest=dict(schema_version=1,batch_id='gain_fixture',competition=batch.COMPETITION,max_submissions=5,baseline_public_score=.482,state_root='reports/state',branches=[spec])
        write(root/'manifest.json',manifest)
        state=root/'reports/state'/spec['name'];state.mkdir(parents=True)
        bound=dict(branch_sha256=batch.branch_sha(spec),target=spec['target'],actual_target=spec['target'],version=1)
        accepted=dict(bound,status='accepted',submission_ref=91000001,description=spec['description'],competition=batch.COMPETITION,output_file='submission.csv')
        score=dict(bound,status='COMPLETE',submission_ref=91000001,public_score=.483,public_score_available=True,error_description_present=False,checked_at_utc='2026-11-09T08:00:00+00:00')
        write(state/'submission.json',accepted);write(state/'score.json',score)
        row=dict(branch=spec['name'],target=spec['target'],actual_target=spec['target'],submission_ref=91000001,status='COMPLETE',public_score=.483,public_score_available=True,error_description_present=False)
        result=dict(branches=[row])
        with patch.object(ledger_module,'ROOT',root),patch.object(batch,'ROOT',root),patch.object(batch,'make_api',side_effect=AssertionError('No API permitted')):
            yield dict(root=root,stage=stage,state=state,manifest=manifest,result=result,row=row,score=score,accepted=accepted,ledger=reports/'improvement_ledger.json',md=reports/'IMPROVEMENT_LEDGER.md')


def blocked(mutator):
    with fixture() as f:
        before=(sha(f['ledger']),sha(f['md']));mutator(f)
        try:
            added=ledger_module.record_gains(f['manifest'],f['result'])
            blocked=not added
        except (ValueError,KeyError,FileNotFoundError,TypeError):blocked=True
        return blocked and before==(sha(f['ledger']),sha(f['md']))


def receipt_change(name,key,value):
    def change(f):
        p=f['state']/name;v=read(p);v[key]=value;write(p,v)
    return change


def main():
    real={name:sha(ROOT/'reports'/name) for name in ('improvement_ledger.json','IMPROVEMENT_LEDGER.md')}
    tests={}
    with fixture() as f:
        tests['plan_only_no_api']=False
        with patch.object(sys,'argv',['watch_batch_with_ledger_20261109.py','--manifest',str(f['root']/'manifest.json')]),patch.object(ledger_module,'snapshot',side_effect=AssertionError('No polling permitted')):
            plan=ledger_module.main();tests['plan_only_no_api']=plan['status']=='plan_only_no_network'
        original_preflight=batch.local_preflight;calls=[]
        def checked(m,b):calls.append(b['name']);return original_preflight(m,b)
        with patch.object(batch,'local_preflight',side_effect=checked):added=ledger_module.record_gains(f['manifest'],f['result'])
        data=read(f['ledger']);entry=data['records'][-1];prose=f['md'].read_text(encoding='utf-8')
        tests['valid_gain_recorded']=added==[91000001] and data['current_best']==.483 and len(data['records'])==5
        tests['source_preflight_used']=calls==['mass_guarded_oldhead_p3']
        tests['immutable_source_recipe_written']=entry['notebook_sha256']==f['manifest']['branches'][0]['notebook_sha256'] and entry['recipe_sha256']==sha(f['stage']/'recipe.json') and entry['recipe']==read(f['stage']/'recipe.json')
        tests['explicit_causal_scope']=bool(entry['source']) and bool(entry['attribution_limit']) and entry['private_gain_verified'] is False and entry['comparison_anchor_ref']==58129661
        tests['markdown_matches_json']='<!-- gain-ref: 91000001 -->' in prose and entry['source'] in prose and entry['attribution_limit'] in prose and entry['notebook_sha256'] in prose
        frozen=(sha(f['ledger']),sha(f['md']))
        tests['duplicate_idempotent']=ledger_module.record_gains(f['manifest'],f['result'])==[] and frozen==(sha(f['ledger']),sha(f['md']))
        # Simulate a process ending after JSON save, before the Markdown write.
        f['md'].write_text('# Fixture ledger\n',encoding='utf-8')
        tests['markdown_reconciled_from_json']=ledger_module.record_gains(f['manifest'],f['result'])==[] and '<!-- gain-ref: 91000001 -->' in f['md'].read_text(encoding='utf-8') and sha(f['ledger'])==frozen[0]
        # Equal score on another positive receipt is never a new best.
        receipt_change('submission.json','submission_ref',91000002)(f);receipt_change('score.json','submission_ref',91000002)(f);f['row']['submission_ref']=91000002
        tests['tie_no_gain']=ledger_module.record_gains(f['manifest'],f['result'])==[] and len(read(f['ledger'])['records'])==5
    tests['pending_normal_ignored']=blocked(lambda f:f['row'].update(status='PENDING',public_score_available=False,public_score=None))
    tests['pending_inconsistent_snapshot_rejected']=blocked(lambda f:f['row'].update(status='PENDING'))
    tests['error_inconsistent_snapshot_rejected']=blocked(lambda f:f['row'].update(status='ERROR'))
    tests['snapshot_error_ignored']=blocked(lambda f:f['row'].update(error_description_present=True))
    tests['score_error_rejected']=blocked(receipt_change('score.json','error_description_present',True))
    tests['score_pending_rejected']=blocked(receipt_change('score.json','status','PENDING'))
    tests['unknown_submission_rejected']=blocked(receipt_change('submission.json','status','request_outcome_unknown_no_retry'))
    tests['zero_submission_ref_rejected']=blocked(receipt_change('submission.json','submission_ref',0))
    tests['boolean_submission_ref_rejected']=blocked(receipt_change('submission.json','submission_ref',True))
    tests['receipt_ref_mismatch_rejected']=blocked(receipt_change('score.json','submission_ref',91000002))
    tests['snapshot_ref_mismatch_rejected']=blocked(lambda f:f['row'].update(submission_ref=91000002))
    tests['receipt_target_mismatch_rejected']=blocked(receipt_change('score.json','actual_target','stormseye/another-target'))
    tests['snapshot_target_mismatch_rejected']=blocked(lambda f:f['row'].update(actual_target='stormseye/another-target'))
    tests['branch_receipt_sha_mismatch_rejected']=blocked(receipt_change('score.json','branch_sha256','0'*64))
    tests['snapshot_score_mismatch_rejected']=blocked(lambda f:f['row'].update(public_score=.484))
    tests['nonfinite_score_rejected']=blocked(receipt_change('score.json','public_score',float('nan')))
    tests['below_best_not_recorded']=blocked(lambda f:(receipt_change('score.json','public_score',.481)(f),f['row'].update(public_score=.481)))
    tests['source_mutation_rejected']=blocked(lambda f:(f['stage']/'notebook.ipynb').write_text('{}',encoding='utf-8'))
    tests['metadata_mutation_rejected']=blocked(lambda f:(f['stage']/'kernel-metadata.json').write_text('{}',encoding='utf-8'))
    tests['recipe_mutation_rejected']=blocked(lambda f:write(f['stage']/'recipe.json',dict(method='tampered')))
    tests['real_ledgers_unchanged']=all(sha(ROOT/'reports'/name)==value for name,value in real.items())
    result=dict(status='passed' if all(tests.values()) else 'failed',checks=tests,source_sha256=sha(ROOT/'scripts/watch_batch_with_ledger_20261109.py'),no_network_used=True,real_ledgers_untouched=tests['real_ledgers_unchanged'],temporary_fixture_root='D:/Paper/casmi/.cache/tmp')
    out=ROOT/'reports/gain_ledger_review_20261109';out.mkdir(exist_ok=True)
    write(out/'verification.json',result)
    print(json.dumps(dict(status=result['status'],checks_passed=sum(tests.values()),checks_total=len(tests),failed=[k for k,v in tests.items() if not v])))
    if result['status']!='passed':raise ValueError('Gain ledger fixtures failed')

if __name__=='__main__':main()
