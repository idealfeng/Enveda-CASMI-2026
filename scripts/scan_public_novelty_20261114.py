"""Read bounded public CASMI Notebook metadata/source; never execute it."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, logging, os, sys, time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/discussion_review_20261114/notebooks'
sys.path.insert(0,str(ROOT/'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest

def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')

def safe(e):return dict(error_type=type(e).__name__,http_status=getattr(getattr(e,'response',None),'status_code',None))

def read_retry(fn):
    for attempt in range(3):
        try:return fn()
        except Exception as e:
            if type(e).__name__ not in ('ConnectionError','ReadTimeout','Timeout','ConnectTimeout') or attempt==2:raise
            time.sleep(2)

def main():
    p=argparse.ArgumentParser();p.add_argument('--sources',nargs='*');a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    api=make_api()
    if a.sources is None:
        results={}
        for order in ['scoreDescending','dateRun']:
            rows=read_retry(lambda:api.kernels_list(competition='enveda-CASMI26-molecule-id-mass-spectra',sort_by=order,page=1,page_size=40)) or []
            values=[{k:getattr(r,k,None) for k in ['ref','title','last_run_time','total_votes','public_score','best_score']} for r in rows]
            save(OUT/(order+'.json'),values);results[order]=values
        save(OUT/'inventory_receipt.json',dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),read_only=True,no_source_execution=True))
        print(json.dumps(results,ensure_ascii=False,default=str));return
    if len(a.sources)>6:raise ValueError('At most six source downloads')
    receipts=[]
    for ref in a.sources:
        try:
            req=ApiGetKernelRequest();req.user_name,req.kernel_slug=ref.split('/')
            def fetch():
                with api.build_kaggle_client() as client:return client.kernels.kernels_api_client.get_kernel(req)
            response=read_retry(fetch);raw=response.blob.source.encode('utf-8')
            if len(raw)>2*1024*1024:raise ValueError('Public source size exceeds bounded cap')
            folder=OUT/ref.replace('/','__');folder.mkdir(exist_ok=False)
            (folder/'source.ipynb').write_bytes(raw);meta=response.metadata
            record={k:getattr(meta,k,None) for k in ['ref','title','current_version_number','last_run_time','dataset_data_sources','kernel_data_sources','is_private']}
            record.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),status='downloaded',read_only=True,no_execution=True)
            save(folder/'metadata.json',record)
            try:
                book=json.loads(raw);cells=folder/'cells';cells.mkdir()
                for i,cell in enumerate(book.get('cells',[])):
                    source=cell.get('source','');source=''.join(source) if isinstance(source,list) else source
                    (cells/f'{i:02}.{"py" if cell["cell_type"]=="code" else "md"}').write_text(source,encoding='utf-8')
            except json.JSONDecodeError:pass
            receipts.append(record)
        except Exception as e:receipts.append(dict(ref=ref,status='failed',**safe(e)))
    save(OUT/'source_receipt.json',dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),sources=receipts,no_execution=True,no_model_assets_downloaded=True))
    print(json.dumps(receipts,ensure_ascii=False,default=str))

if __name__=='__main__':
    for k,v in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:os.environ[k]=str(ROOT/v)
    logging.disable(logging.CRITICAL)
    try:main()
    except Exception as e:print(json.dumps(dict(status='read_failed',**safe(e))));raise SystemExit(1)
