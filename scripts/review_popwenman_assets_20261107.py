"""Read public training outputs and bounded required assets; no model execution or Kaggle writes."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import json,hashlib,logging,os,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from kaggle_first_submission import make_api
from scan_public_baselines_20261107 import fetch,save

def main():
    logging.disable(logging.CRITICAL)
    for name,relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        p=ROOT/relative;p.mkdir(parents=True,exist_ok=True);os.environ[name]=str(p)
    target='popwenman/casmi26-scorer-train-v80'
    meta=fetch(target);print(json.dumps(meta,default=str),flush=True)
    if meta.get('status')!='downloaded' or meta.get('is_private') is not False:raise ValueError('Expected public training kernel')
    version=meta['current_version_number'];api=make_api()
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
    out=ROOT/'assets/kaggle/popwenman/casmi26-scorer-train-v80'/('v'+str(version))
    out.mkdir(parents=True,exist_ok=True)
    files={};token=None
    with api.build_kaggle_client() as client:
        for page in range(40):
            req=ApiListKernelSessionOutputRequest();req.user_name,req.kernel_slug=target.split('/');req.version_label=api._kernel_version_label(str(version));req.page_size=100
            if token:req.page_token=token
            listing=client.kernels.kernels_api_client.list_kernel_session_output(req)
            for item in listing.files or []:
                if item.file_name in files:raise ValueError('Duplicate listed file')
                files[item.file_name]=item
            token=listing.next_page_token
            if not token:break
        else:raise ValueError('Pagination cap')
    inventory=[dict(name=name,size=getattr(item,'total_bytes',getattr(item,'size',None))) for name,item in files.items()]
    save(out/'output_inventory.json',dict(target=target,version=version,is_private=False,files=inventory))
    print(json.dumps(dict(target=target,version=version,files=inventory)),flush=True)
    import requests
    required=[name for name in files if PurePosixPath(name).name in ('final_model.pt','config_used.json','training_result.json','MANIFEST.json','manifest.json')]
    receipts=[]
    for name in required:
        relative=PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:raise ValueError('Unsafe output name')
        destination=(out/name).resolve()
        if not destination.is_relative_to(out) or destination.exists():raise ValueError('Existing or unsafe output path')
        limit=100<<20 if relative.name=='final_model.pt' else 4<<20
        destination.parent.mkdir(parents=True,exist_ok=True)
        digest=hashlib.sha256();size=0;temp=destination.with_suffix(destination.suffix+'.partial')
        with requests.get(files[name].url,stream=True,timeout=(15,45)) as response:
            response.raise_for_status()
            length=response.headers.get('Content-Length')
            if length and int(length)>limit:raise ValueError('Size cap')
            with temp.open('xb') as stream:
                for block in response.iter_content(1<<20):
                    size+=len(block)
                    if size>limit:raise ValueError('Stream size cap')
                    stream.write(block);digest.update(block)
        temp.replace(destination)
        row=dict(path=str(destination.relative_to(ROOT)),source_file=name,bytes=size,sha256=digest.hexdigest())
        receipts.append(row);print(json.dumps(row),flush=True)
    record=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),status='downloaded',target=target,version=version,is_private=False,
        files=receipts,signed_urls_persisted=False,kaggle_write_performed=False,model_executed=False)
    save(out/'download_receipt.json',record)
    # Public data cards, metadata only. Do not persist download URLs.
    cards=[]
    for ref in ['sanpier/catalogue-experiment-saner','metric/rdkit-2026-3-3-wheel']:
        try:
            response=requests.get('https://www.kaggle.com/api/v1/datasets/view/'+ref,timeout=(15,45));response.raise_for_status()
            d=response.json(); row={k:d.get(k) for k in ['title','currentVersionNumber','isPrivate','licenseName','totalBytes','lastUpdated']};row['ref']=ref
            row['files']=[{k:f.get(k) for k in ['name','totalBytes','fileSize']} for f in d.get('resources',d.get('files',[]))]
            cards.append(row)
        except Exception as exc:cards.append(dict(ref=ref,error_type=type(exc).__name__))
    save(ROOT/'reports/public_baseline_scan_20261107/extra_dataset_cards.json',cards)
    print(json.dumps(dict(dataset_cards=cards),default=str),flush=True)

if __name__=='__main__':main()
