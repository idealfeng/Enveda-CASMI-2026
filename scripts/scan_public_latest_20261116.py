"""Read current public CASMI notebooks; archive source only, never execute it."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import logging
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/public_review_20261116/notebooks'
sys.path.insert(0, str(ROOT/'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')


def fetch(ref):
    try:
        request = ApiGetKernelRequest()
        request.user_name, request.kernel_slug = ref.split('/')
        with make_api().build_kaggle_client() as client:
            response = client.kernels.kernels_api_client.get_kernel(request)
        raw = response.blob.source.encode('utf-8')
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('Source exceeds4MiB cap')
        folder = OUT/ref.replace('/', '__')
        folder.mkdir(exist_ok=False)
        (folder/'source.ipynb').write_bytes(raw)
        meta = response.metadata
        fields = ['id','ref','title','current_version_number','last_run_time','total_votes','is_private','enable_gpu','enable_internet',
                  'dataset_data_sources','kernel_data_sources','competition_data_sources','model_data_sources','docker_image','machine_shape']
        record = {k:getattr(meta,k,None) for k in fields}
        record.update(status='downloaded', source_sha256=hashlib.sha256(raw).hexdigest(), source_bytes=len(raw),
                      source_path=(folder/'source.ipynb').relative_to(ROOT).as_posix(), execution_performed=False)
        save(folder/'metadata.json', record)
        try:
            book = json.loads(raw)
            cells = folder/'cells'
            cells.mkdir()
            for i,cell in enumerate(book.get('cells', [])):
                source=cell.get('source',''); source=''.join(source) if isinstance(source,list) else source
                (cells/f'{i:02}.{"py" if cell["cell_type"] == "code" else "md"}').write_text(source, encoding='utf-8')
        except json.JSONDecodeError:
            pass
        return record
    except Exception as error:
        return dict(ref=ref,status='failed',error_type=type(error).__name__,http_status=getattr(getattr(error,'response',None),'status_code',None))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources', nargs='*')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.sources is None:
        api=make_api(); records={}
        for order in ('scoreDescending','dateRun'):
            dest=OUT/(order+'.json')
            if dest.exists():
                raise FileExistsError('Preserve inventory snapshot')
            rows=api.kernels_list(competition='enveda-CASMI26-molecule-id-mass-spectra',sort_by=order,page=1,page_size=100) or []
            values=[{k:getattr(r,k,None) for k in ('ref','title','last_run_time','total_votes','public_score','best_score')} for r in rows]
            save(dest,dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),read_only=True,records=values))
            records[order]=values
        print(json.dumps({k:v[:18] for k,v in records.items()},ensure_ascii=True,default=str))
        return
    if len(args.sources)>16:
        raise ValueError('Bounded at16 public source reads')
    with ThreadPoolExecutor(max_workers=3) as pool:
        records=list(pool.map(fetch,list(dict.fromkeys(args.sources))))
    save(OUT/'source_receipt.json',dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),sources=records,
                                      read_only=True,no_source_execution=True,no_model_downloads=True))
    print(json.dumps(records,ensure_ascii=True,default=str))


if __name__=='__main__':
    for name,relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        path=ROOT/relative;path.mkdir(parents=True,exist_ok=True);os.environ[name]=str(path)
    logging.disable(logging.CRITICAL)
    main()
