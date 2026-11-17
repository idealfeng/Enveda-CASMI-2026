"""Read small public metadata/file inventories; no weight download or execution."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json,os,sys,logging

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/public_review_20261116/notebooks'
sys.path.insert(0,str(ROOT/'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
from kagglesdk.datasets.types.dataset_api_service import ApiGetDatasetRequest

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')

def full(ref):
    try:
        req=ApiGetKernelRequest();req.user_name,req.kernel_slug=ref.split('/')
        with make_api().build_kaggle_client() as client:
            response=client.kernels.kernels_api_client.get_kernel(req)
        path=OUT/ref.replace('/','__')/'api_metadata_full.json'
        if path.exists():raise FileExistsError('Preserve metadata')
        save(path,response.metadata.to_dict())
        return dict(ref=ref,status='saved_full_metadata')
    except Exception as e:
        return dict(ref=ref,status='failed',error_type=type(e).__name__,http_status=getattr(getattr(e,'response',None),'status_code',None))

def dataset(ref):
    result=dict(ref=ref,read_only=True,files_only=True,model_bytes_downloaded=0)
    api=make_api()
    try:
        response=api.dataset_list_files(ref,page_size=100)
        rows=response.files or []
        result.update(status='files_read',file_count=len(rows),files=[x.to_dict() for x in rows],
                      next_page_token_present=bool(getattr(response,'next_page_token',None)))
    except Exception as e:
        result.update(status='failed',error_type=type(e).__name__,http_status=getattr(getattr(e,'response',None),'status_code',None))
    try:
        req=ApiGetDatasetRequest();req.owner_slug,req.dataset_slug=ref.split('/')
        with api.build_kaggle_client() as client:
            view=client.datasets.dataset_api_client.get_dataset(req)
        result['dataset_view']=view.to_dict()
        result['current_version_number']=view.current_version_number
        result['is_private']=view.is_private
    except Exception as e:
        result['dataset_view_error']=dict(error_type=type(e).__name__,http_status=getattr(getattr(e,'response',None),'status_code',None))
    save(OUT/'dependency_inventory_v2'/(ref.replace('/','__')+'.json'),result)
    return result

def main():
    refs=['heliosli/casmi26-0-494-public-demo','mathleteutd/casmi26-0-492-test-set-network-rerank',
          'alexchilton/casmi26-0-492-what-moved-the-board-59-arms','rogersjohnson/casmi26-l4-lam035']
    datasets=['heliosli/casmi26-rr-v3','heliosli/casmi26-denovo-v3','heliosli/casmi26-frigid-e1',
              'heliosli/casmi26-joint-ranker','heliosli/casmi26-pxv2-deploy','heliosli/casmi26-rt-np',
              'sanpier/catalogue-experiment-saner','metric/rdkit-2026-3-3-wheel']
    with ThreadPoolExecutor(max_workers=3) as pool:
        metadata=[]
        assets=list(pool.map(dataset,datasets+['heliosli/casmi26-m5']))
    save(OUT/'dependency_inventory_v2_receipt.json',dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),metadata=metadata,assets=assets))
    print(json.dumps(dict(metadata=metadata,assets=[{k:v for k,v in a.items() if k!='files'} for a in assets])))

if __name__=='__main__':
    for k,v in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:os.environ[k]=str(ROOT/v)
    logging.disable(logging.CRITICAL)
    main()
