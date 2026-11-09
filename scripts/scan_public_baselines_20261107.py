"""Read public competition notebook inventories and source snapshots. Never run or submit."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib, json, os, sys, logging

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from kaggle_first_submission import make_api

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')

def fetch(ref):
    try:
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
        api=make_api(); request=ApiGetKernelRequest(); request.user_name,request.kernel_slug=ref.split('/')
        with api.build_kaggle_client() as client:
            response=client.kernels.kernels_api_client.get_kernel(request)
        meta=response.metadata; raw=response.blob.source.encode('utf-8')
        if len(raw)>8*1024*1024:raise ValueError('Source size cap')
        folder=ROOT/'third_party'/('public_scan_'+ref.replace('/','__')+'_20261107')
        if folder.exists():raise FileExistsError('Preserve prior snapshot')
        folder.mkdir(parents=True)
        extension='.ipynb' if response.blob.kernel_type.lower()=='notebook' else '.py'
        (folder/('source'+extension)).write_bytes(raw)
        fields=['id','ref','title','current_version_number','last_run_time','total_votes','is_private','enable_gpu','enable_internet',
            'dataset_data_sources','kernel_data_sources','competition_data_sources','model_data_sources','docker_image','machine_shape']
        record={name:getattr(meta,name,None) for name in fields}
        record.update(source_sha256=hashlib.sha256(raw).hexdigest(),source_bytes=len(raw),source_path=str((folder/('source'+extension)).relative_to(ROOT)))
        save(folder/'metadata.json',record)
        return dict(status='downloaded',**record)
    except Exception as e:return dict(status='failed',ref=ref,error_type=type(e).__name__)

def main():
    for name,relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        p=ROOT/relative;p.mkdir(parents=True,exist_ok=True);os.environ[name]=str(p)
    logging.disable(logging.CRITICAL)
    dest=ROOT/'reports/public_baseline_scan_20261107'
    dest.mkdir(parents=True,exist_ok=True)
    api=make_api(); inventories={}
    for sort in ('scoreDescending','dateRun'):
        rows=api.kernels_list(competition='enveda-CASMI26-molecule-id-mass-spectra',sort_by=sort,page=1,page_size=100) or []
        records=[]
        for item in rows:
            records.append({key:getattr(item,key,None) for key in ['ref','title','current_version_number','last_run_time','total_votes','public_score','best_score']})
        inventories[sort]=records
        save(dest/(sort+'.json'),dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),records=records,score_values_exposed=any(x.get('public_score') is not None for x in records)))
        print(json.dumps(dict(sort=sort,top=[dict(ref=x['ref'],title=x['title'],last_run_time=str(x['last_run_time'])) for x in records[:12]]),ensure_ascii=False),flush=True)
    known=['romanrozen/0-482-casmi-from-peaks-to-structures','heliosli/casmi26-0-482','d1m4official/enveda-0480-ensemble-hardened','zz3t3rn41/casmi26-peaks-to-structures-v2','pablodiegoo/enveda-casmi26-starter-notebook']
    old=json.loads((ROOT/'reports/public_baseline_scan_20261106/scoreDescending_authenticated.json').read_text())['records']
    known.extend(x['ref'] for x in old if any(z in x['ref'] for z in ['flexonafft/','prvsiyan/']))
    oldrefs={x['ref'] for x in old}
    known.extend(x['ref'] for x in inventories['scoreDescending'][:12] if x['ref'] not in oldrefs)
    known.extend(x['ref'] for x in inventories['dateRun'][:8] if x['ref'] not in oldrefs)
    refs=list(dict.fromkeys(known))
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(fetch,refs):
            results.append(row)
            print(json.dumps({k:row.get(k) for k in ['status','ref','current_version_number','source_sha256','source_bytes','error_type']},ensure_ascii=False),flush=True)
    save(dest/'source_snapshots.json',dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),results=results,read_only=True,run_or_submission_performed=False))

if __name__=='__main__':main()
