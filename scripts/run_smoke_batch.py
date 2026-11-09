"""Run the three downloaded public pipelines sequentially, preserving run evidence."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time


ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--scheme',choices=['prvsiyan','canqiang','flexonafft'],action='append')
parser.add_argument('--tag',default='20261104')
args=parser.parse_args()
if sys.platform!='linux':
    parser.error('Run inside the project Linux environment after sourcing scripts/linux_env.sh')
schemes=args.scheme or ['prvsiyan','canqiang','flexonafft']
report_path=ROOT/'reports/smoke_batch_status.json'
report={'status':'running','visible_input_is_placeholder':True,'full_hidden_score_reproduced':False,'runs':[]}
def save():
    tmp=report_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2)+'\n')
    tmp.replace(report_path)
for scheme in schemes:
    work=ROOT/'runs'/f'{scheme}_smoke_{args.tag}'
    work.mkdir(parents=True,exist_ok=True)
    if scheme=='prvsiyan':
        command=[sys.executable,str(ROOT/'third_party/prvsiyan_analog/run_local_linux.py'),
                 '--input-root',str(ROOT/'runs/inputs/prvsiyan_v43'),'--work-root',str(work),
                 '--competition-root',str(ROOT/'enveda-CASMI26-molecule-id-mass-spectra'),
                 '--shared-spec-cache',str(ROOT/'runs/shared_spec_cache'),'--mmap-pool']
    elif scheme=='canqiang':
        command=[sys.executable,str(ROOT/'third_party/canqiang_e006/run_local_linux.py'),
                 '--input-root',str(ROOT/'assets/kaggle'),'--work-root',str(work),
                 '--competition-root',str(ROOT/'enveda-CASMI26-molecule-id-mass-spectra'),
                 '--input-mode','exact','--shared-spec-cache',str(ROOT/'runs/shared_spec_cache')]
    else:
        command=[sys.executable,str(ROOT/'third_party/flexonafft_evidence_gap/run_local.py'),
                 '--input-root',str(ROOT/'assets/kaggle'),'--work-root',str(work),
                 '--shared-spec-cache',str(ROOT/'runs/shared_spec_cache')]
    item={'scheme':scheme,'work_root':str(work),'command':command,'status':'running','log':str(work/'console.log')}
    report['runs'].append(item)
    save()
    print(json.dumps({'event':'start','scheme':scheme,'work_root':str(work)}),flush=True)
    started=time.monotonic()
    env=os.environ.copy()
    env['PYTHONUNBUFFERED']='1'
    with (work/'console.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        item['pid']=process.pid
        save()
        try:
            code=process.wait()
        except KeyboardInterrupt:
            process.send_signal(2)
            process.wait()
            item.update(status='interrupted',elapsed_seconds=round(time.monotonic()-started,3))
            report['status']='interrupted'
            save()
            raise
    item.update(status='process_complete' if code==0 else 'failed',exit_code=code,
                elapsed_seconds=round(time.monotonic()-started,3))
    if code!=0:
        item['log_tail']='\n'.join((work/'console.log').read_text(errors='replace').splitlines()[-28:])
    save()
    print(json.dumps({'event':'end','scheme':scheme,'exit_code':code,'seconds':item['elapsed_seconds']}),flush=True)
report['status']='processes_complete'
save()
if any(x['exit_code']!=0 for x in report['runs']):
    raise SystemExit(1)
