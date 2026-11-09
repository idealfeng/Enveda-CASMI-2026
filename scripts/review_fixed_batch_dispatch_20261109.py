"""Offline dispatcher state-machine checks with a filesystem mock engine."""
from pathlib import Path
import hashlib,json,tempfile,types,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import dispatch_fixed_batch_20261109 as dispatch

class FakeEngine:
    COMPETITION='fixture_competition'
    def __init__(self,root):
        self.root=root;self.events=[];self.api_calls=0;self.t=0.;self.allowed=5;self.cloud_status={};self.audit_fails=set();self.audit_returns_bad=set();self.read_fails=set();self.bad_launch=set();self.after_launch=None;self.mutate_source=False
        self.manifest=dict(schema_version=1,competition=self.COMPETITION,max_submissions=5,branches=[dict(name=f'b{i}',target=f'fixture/b{i}') for i in range(5)])
        self.path=root/'manifest.json';self.save(self.path,self.manifest)
        self.source=root/'source.txt';self.source.write_text('frozen');self.source_sha=self.sha(self.source)
    def inside(self,p):return Path(p)
    def load_manifest(self,p):return json.loads(Path(p).read_text())
    def local_preflight(self,m,b):
        if self.sha(self.source)!=self.source_sha:raise ValueError('Fixture source changed')
    def branch_state(self,m,b):return self.root/'state'/b['name']
    def sha(self,p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def now(self):return f'fixture-{self.t}'
    def safe_error(self,e):return dict(error_type=type(e).__name__)
    def save(self,p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v))
    def claim(self,p,v):
        Path(p).parent.mkdir(parents=True,exist_ok=True)
        with Path(p).open('x') as f:json.dump(v,f)
    def make_api(self):self.api_calls+=1;return self
    def competition_get_submission_limits(self,competition):self.api_calls+=1;return types.SimpleNamespace(num_allowed_now=self.allowed)
    def bound_receipt(self,m,b,name):return json.loads((self.branch_state(m,b)/name).read_text())
    def seed_cloud(self,index,status='run_requested',session='QUEUED'):
        b=self.manifest['branches'][index];self.save(self.branch_state(self.manifest,b)/'cloud.json',dict(status=status));self.cloud_status[b['name']]=session
    def seed_submit(self,index,status='accepted',ref=100):
        b=self.manifest['branches'][index];self.save(self.branch_state(self.manifest,b)/'submission.json',dict(status=status,submission_ref=ref))
    def live_binding(self,m,b,api=None):
        self.events.append(('read',b['name']))
        if b['name'] in self.read_fails:raise OSError('Fixture read error')
        return dict(session_status=self.cloud_status.get(b['name'],'QUEUED'),failure_message_present=False)
    def launch(self,m,b,api=None):
        self.events.append(('launch',b['name']));path=self.branch_state(m,b)/'cloud.json'
        status='request_outcome_unknown_no_retry' if b['name'] in self.bad_launch else 'run_requested'
        self.claim(path,dict(status=status));self.cloud_status.setdefault(b['name'],'QUEUED')
        if self.after_launch:self.after_launch(self,b)
        return dict(status=status)
    def audit_outputs(self,m,b,api=None):
        self.events.append(('audit',b['name']))
        if b['name'] in self.audit_fails:raise ValueError('Fixture bad audit')
        return dict(status='failed' if b['name'] in self.audit_returns_bad else 'passed')
    def submit(self,m,b,api=None):
        self.events.append(('submit',b['name']))
        if self.allowed<1:raise ValueError('Fixture quota exhausted')
        ref=1000+sum(k=='submit' for k,n in self.events);self.claim(self.branch_state(m,b)/'submission.json',dict(status='accepted',submission_ref=ref));self.allowed-=1
        return dict(status='accepted',submission_ref=ref)
    def clock(self):return self.t
    def sleep(self,seconds):self.t+=seconds
    def run(self,seconds=91):return dispatch.run(self.path,seconds,engine=self,clock=self.clock,sleeper=self.sleep)

def execute_case(name,configure,check,seconds=91):
    with tempfile.TemporaryDirectory(prefix='dispatch-fsm-',dir=ROOT/'.cache/tmp') as temp:
        e=FakeEngine(Path(temp));configure(e);r=e.run(seconds)
        return dict(passed=bool(check(e,r)),status=r['status'],events=e.events)

def main():
    cases={}
    with tempfile.TemporaryDirectory(prefix='dispatch-plan-',dir=ROOT/'.cache/tmp') as temp:
        e=FakeEngine(Path(temp));r=dispatch.plan(e.path,engine=e);cases['plan_no_network_or_writes']=dict(passed=r['status']=='plan_only_no_network' and e.api_calls==0 and not e.events and not (e.root/'state').exists())
    cases['fresh_batch_launches_only_two']=execute_case('fresh',lambda e:None,lambda e,r:len([x for x in e.events if x[0]=='launch'])==2 and not any(x[0]=='submit' for x in e.events))
    cases['two_preexisting_pending_prevent_third_push']=execute_case('existing',lambda e:(e.seed_cloud(0),e.seed_cloud(1)),lambda e,r:not any(x[0]=='launch' for x in e.events))
    cases['completed_existing_runs_audit_then_single_submit']=execute_case('complete',lambda e:(e.seed_cloud(0,session='COMPLETE'),e.seed_cloud(1,session='COMPLETE')),lambda e,r:all(e.events.count(('submit',f'b{i}'))==1 and e.events.index(('audit',f'b{i}'))<e.events.index(('submit',f'b{i}')) for i in (0,1)))
    cases['audit_exception_prevents_formal_submit']=execute_case('auditfail',lambda e:(e.seed_cloud(0,session='COMPLETE'),e.audit_fails.add('b0')),lambda e,r:('audit','b0') in e.events and ('submit','b0') not in e.events and r['branches']['b0']['terminal'])
    cases['failed_audit_return_prevents_formal_submit']=execute_case('auditbad',lambda e:(e.seed_cloud(0,session='COMPLETE'),e.audit_returns_bad.add('b0')),lambda e,r:('submit','b0') not in e.events)
    cases['unknown_cloud_claim_not_retried']=execute_case('cloudunknown',lambda e:e.seed_cloud(0,status='request_outcome_unknown_no_retry'),lambda e,r:('launch','b0') not in e.events and ('audit','b0') not in e.events and r['branches']['b0']['status']=='cloud_claimed_no_retry')
    cases['unknown_submission_claim_not_retried']=execute_case('subunknown',lambda e:e.seed_submit(0,status='request_outcome_unknown_no_retry',ref=None),lambda e,r:all(n!='b0' for k,n in e.events))
    cases['accepted_submission_not_repeated']=execute_case('accepted',lambda e:e.seed_submit(0),lambda e,r:all(n!='b0' for k,n in e.events) and r['branches']['b0']['status']=='submission_accepted')
    cases['zero_quota_prevents_all_writes']=execute_case('quota',lambda e:setattr(e,'allowed',0),lambda e,r:not any(k in ('launch','submit') for k,n in e.events) and r['status']=='quota_exhausted_no_more_writes')
    cases['five_claims_cap_no_actions']=execute_case('five',lambda e:[e.seed_submit(i,ref=200+i) for i in range(5)],lambda e,r:not e.events and all(x['terminal'] for x in r['branches'].values()))
    cases['failed_cloud_no_audit_submit']=execute_case('cloudfailed',lambda e:e.seed_cloud(0,session='ERROR'),lambda e,r:('audit','b0') not in e.events and ('submit','b0') not in e.events and r['branches']['b0']['status']=='cloud_failed_no_submission')
    cases['ten_consecutive_read_errors_stop_and_reserve_slot']=execute_case('readfail',lambda e:(e.seed_cloud(0),e.seed_cloud(1),e.read_fails.add('b0')),lambda e,r:r['branches']['b0']['status']=='ten_read_errors_no_submission' and r['branches']['b0']['reserved_cloud_slot'] and not any(k=='launch' for k,n in e.events),seconds=451)
    def mutate(e,b):e.path.write_text(e.path.read_text()+' ')
    cases['manifest_mutation_after_first_push_prevents_further_writes']=execute_case('mutate',lambda e:setattr(e,'after_launch',mutate),lambda e,r:len([x for x in e.events if x[0]=='launch'])==1)
    cases['source_mutation_after_first_push_prevents_further_writes']=execute_case('source',lambda e:setattr(e,'after_launch',lambda e,b:e.source.write_text('changed')),lambda e,r:len([x for x in e.events if x[0]=='launch'])==1)
    cases['unknown_launch_response_never_pushed_twice']=execute_case('badlaunch',lambda e:e.bad_launch.add('b0'),lambda e,r:e.events.count(('launch','b0'))==1 and ('submit','b0') not in e.events)
    def allcomplete(e):
        for i in range(5):e.cloud_status[f'b{i}']='COMPLETE'
    cases['five_successful_branches_each_submitted_once']=execute_case('allcomplete',allcomplete,lambda e,r:sum(k=='launch' for k,n in e.events)==5 and sum(k=='submit' for k,n in e.events)==5 and len({n for k,n in e.events if k=='submit'})==5 and all(x['terminal'] for x in r['branches'].values()),seconds=181)
    with tempfile.TemporaryDirectory(prefix='dispatch-lock-',dir=ROOT/'.cache/tmp') as temp:
        e=FakeEngine(Path(temp));lock=e.root/'state/.dispatcher.lock';e.claim(lock,dict(owner='other'))
        refused=False
        try:e.run()
        except FileExistsError:refused=True
        cases['exclusive_lock_prevents_second_dispatcher']=dict(passed=refused and e.api_calls==0 and json.loads(lock.read_text())['owner']=='other')
    out=ROOT/'reports/fixed_batch_dispatch_review_20261109';out.mkdir(exist_ok=True)
    checks={name:value['passed'] for name,value in cases.items()};result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,cases=cases,checks_passed=sum(checks.values()),checks_total=len(checks),no_network_or_cloud_calls=True,dispatcher_sha256=hashlib.sha256((ROOT/'scripts/dispatch_fixed_batch_20261109.py').read_bytes()).hexdigest())
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('status','checks_passed','checks_total','dispatcher_sha256')}));assert all(checks.values()),checks
if __name__=='__main__':main()
