"""Read public FRNet metadata and tiny code/config files; never fetch or execute weights."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
import os
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.datasets.types.dataset_api_service import ApiGetDatasetRequest,ApiDownloadDatasetRequest


def main():
    import requests
    api=make_api()
    ref='agentili/casmi26-fr-reranker-blend'
    req=ApiGetDatasetRequest();req.owner_slug,req.dataset_slug=ref.split('/')
    with api.build_kaggle_client() as client:
        view=client.datasets.dataset_api_client.get_dataset(req)
    fields=['ref','title','subtitle','total_bytes','is_private','license_name','description','current_version_number','last_updated']
    metadata={k:getattr(view,k,None) for k in fields}
    version=metadata['current_version_number']
    listing=api.dataset_list_files(ref+'/'+str(version),page_size=100)
    if listing.next_page_token:
        raise ValueError('Unexpectedly large file inventory')
    files=[dict(name=f.name,bytes=f.total_bytes) for f in listing.files or []]
    metadata.update(files=files,read_at_utc=datetime.now(timezone.utc).isoformat())
    dest=ROOT/'assets/kaggle'/ref/('v'+str(version))
    report=ROOT/'reports/optimization_20261113/massbank_frnet_public_metadata.json'
    records=[]
    for file in files:
        name=file['name'];rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Unsafe public filename')
        # Content and preprocessing only: no model tensors, pickle or data arrays.
        if rel.suffix.lower() not in ('.py','.json','.md','.yaml','.yml','.txt') or file['bytes']>2*1024*1024:
            continue
        target=dest.joinpath(*rel.parts)
        if target.exists():
            raw=target.read_bytes();state='present'
        else:
            req=ApiDownloadDatasetRequest();req.owner_slug,req.dataset_slug=ref.split('/')
            req.dataset_version_number=version;req.file_name=name
            with api.build_kaggle_client() as client:
                redirect=client.datasets.dataset_api_client.download_dataset(req)
            with requests.get(redirect.request.url,stream=True,timeout=(15,45)) as response:
                response.raise_for_status();chunks=[];size=0
                for block in response.iter_content(65536):
                    size+=len(block)
                    if size>4*1024*1024:raise ValueError('Code-only response limit')
                    chunks.append(block)
                raw=b''.join(chunks)
            if raw.startswith(b'PK\x03\x04'):
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    matches=[entry for entry in z.infolist() if not entry.is_dir() and PurePosixPath(entry.filename).name==rel.name]
                    if len(matches)!=1 or matches[0].file_size>2*1024*1024:raise ValueError('Unexpected archive content')
                    raw=z.read(matches[0])
            if len(raw)!=file['bytes']:raise ValueError('Public source length differs')
            raw.decode('utf-8')
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(raw)
            state='downloaded'
        records.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),state=state,path=target.relative_to(ROOT).as_posix()))
    metadata.update(downloaded_code=records,weights_downloaded=False,code_executed=False,signed_urls_persisted=False)
    report.write_text(json.dumps(metadata,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in metadata.items() if k!='description'},indent=2,default=str))


if __name__=='__main__':
    for key,rel in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        os.environ[key]=str(ROOT/rel)
    logging.disable(logging.CRITICAL)
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='read_failed',error_type=type(error).__name__,http_status=getattr(getattr(error,'response',None),'status_code',None))))
        raise SystemExit(1)
