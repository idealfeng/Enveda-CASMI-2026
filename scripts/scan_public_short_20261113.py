"""Bounded official public Notebook inventory/source read; no execution or model download."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest


def save(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')


def main():
    out=ROOT/'reports/optimization_20261113/public_short'
    out.mkdir(parents=True,exist_ok=False)
    api=make_api();results={}
    for order in ['scoreDescending','dateRun']:
        rows=api.kernels_list(competition='enveda-CASMI26-molecule-id-mass-spectra',sort_by=order,page=1,page_size=30) or []
        values=[{k:getattr(r,k,None) for k in ['ref','title','last_run_time','total_votes','public_score','best_score']} for r in rows]
        save(out/(order+'.json'),values);results[order]=values
    refs=['ozertuu/casmi26-dual-neural-physical-isomer']
    refs += [v['ref'] for v in results['scoreDescending'][:5]]
    sources=[]
    for ref in list(dict.fromkeys(refs))[:5]:
        try:
            req=ApiGetKernelRequest();req.user_name,req.kernel_slug=ref.split('/')
            with api.build_kaggle_client() as client:r=client.kernels.kernels_api_client.get_kernel(req)
            raw=r.blob.source.encode('utf-8')
            if len(raw)>2*1024*1024:raise ValueError('Source cap')
            folder=out/ref.replace('/','__');folder.mkdir()
            (folder/'source.ipynb').write_bytes(raw)
            meta=r.metadata
            record={k:getattr(meta,k,None) for k in ['ref','title','current_version_number','last_run_time','dataset_data_sources','kernel_data_sources','is_private']}
            record.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            save(folder/'metadata.json',record);sources.append(dict(status='downloaded',**record))
        except Exception as e:sources.append(dict(status='failed',ref=ref,error_type=type(e).__name__,http_status=getattr(getattr(e,'response',None),'status_code',None)))
    save(out/'receipt.json',dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,no_execution=True))
    print(json.dumps(dict(top=results['scoreDescending'][:8],sources=sources),ensure_ascii=False,default=str))


if __name__=='__main__':
    for k,p in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:os.environ[k]=str(ROOT/p)
    logging.disable(logging.CRITICAL)
    try:main()
    except Exception as e:print(json.dumps(dict(status='read_failed',error_type=type(e).__name__)));raise SystemExit(1)
