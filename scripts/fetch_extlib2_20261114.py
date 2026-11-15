"""Acquire a fixed public reference-library version; never load arrays or execute assets."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import hashlib, json, logging, os, stat, sys, time, zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest

REF='nakhun/casmi26-extlib2'
VERSION=1
DEST=ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1'
REPORT=ROOT/'reports/discussion_review_20261114/notebooks/extlib2_download_receipt.json'
INVENTORY=ROOT/'reports/discussion_review_20261114/notebooks/supplementary_assets.json'
MAX_ARCHIVE=192*1024*1024


def now():return datetime.now(timezone.utc).isoformat()
def sha(p):
    with Path(p).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8');tmp.replace(p)


def main():
    import requests
    expected=json.loads(INVENTORY.read_text(encoding='utf-8'))[REF]
    assert expected['current_version_number']==VERSION and len(expected['files'])==7
    files={x['name']:x['bytes'] for x in expected['files']}
    assert sum(files.values())==128947012
    assert DEST.resolve().is_relative_to(ROOT.resolve())
    DEST.mkdir(parents=True,exist_ok=True)
    receipt=dict(status='downloading',ref=REF,version=VERSION,started_at_utc=now(),expected_files=files,
        expected_total_bytes=sum(files.values()),license_name=expected['license_name'],description=expected['description'],
        permission_boundary='Public read/acquisition only; downstream source licensing not established by this receipt.',
        model_or_array_loaded=False,asset_code_executed=False,signed_urls_persisted=False,files=[])
    save(REPORT,receipt)
    cache=ROOT/'.cache/tmp';cache.mkdir(parents=True,exist_ok=True)
    archive=cache/('extlib2_v1_'+str(int(time.time()))+'.zip.part')
    assert archive.resolve().is_relative_to(ROOT.resolve())
    api=make_api();q=ApiDownloadDatasetRequest();q.owner_slug,q.dataset_slug=REF.split('/');q.dataset_version_number=VERSION
    with api.build_kaggle_client() as client:redirect=client.datasets.dataset_api_client.download_dataset(q)
    started=time.monotonic();total=0
    with requests.get(redirect.request.url,stream=True,timeout=(15,60)) as response:
        response.raise_for_status()
        with archive.open('xb') as handle:
            for block in response.iter_content(1024*1024):
                total+=len(block)
                if total>MAX_ARCHIVE:raise ValueError('Library response exceeded fixed archive limit')
                handle.write(block)
    receipt.update(archive_bytes=total,archive_sha256=sha(archive),download_seconds=round(time.monotonic()-started,3))
    with zipfile.ZipFile(archive) as z:
        entries=[x for x in z.infolist() if not x.is_dir()]
        if len(entries)!=len(files) or {x.filename for x in entries}!=set(files):raise ValueError('Archive member inventory differs')
        if sum(x.file_size for x in entries)!=sum(files.values()):raise ValueError('Archive total length differs')
        for entry in entries:
            name=PurePosixPath(entry.filename)
            if name.is_absolute() or '..' in name.parts or (entry.external_attr>>16)&0o170000==stat.S_IFLNK:
                raise ValueError('Unsafe archive member')
            if entry.file_size!=files[entry.filename]:raise ValueError('Archive member length differs')
            target=DEST.joinpath(*name.parts)
            if not target.resolve().is_relative_to(DEST.resolve()):raise ValueError('Archive target escaped version directory')
            if target.exists():raise FileExistsError('Preserve existing fixed-version asset')
            target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(target.name+'.part');count=0
            with z.open(entry) as source,temporary.open('xb') as handle:
                while True:
                    block=source.read(1024*1024)
                    if not block:break
                    count+=len(block)
                    if count>files[entry.filename]:raise ValueError('Extraction length overflow')
                    handle.write(block)
            if count!=files[entry.filename]:raise ValueError('Extracted length mismatch')
            temporary.replace(target)
            row=dict(name=entry.filename,bytes=count,sha256=sha(target),path=target.relative_to(ROOT).as_posix())
            receipt['files'].append(row);save(REPORT,receipt)
    receipt.update(status='complete_version_size_and_sha_recorded',finished_at_utc=now(),total_bytes=sum(x['bytes'] for x in receipt['files']),
        archive_cache_path=archive.relative_to(ROOT).as_posix(),all_seven_members_verified=True,
        source_metadata_sha256=sha(INVENTORY),content_overlap_not_measured=True,hidden_gain_not_measured=True)
    save(REPORT,receipt);save(DEST/'download_receipt.json',receipt)
    print(json.dumps(dict(status=receipt['status'],version=VERSION,files=len(receipt['files']),total_bytes=receipt['total_bytes'],report=REPORT.relative_to(ROOT).as_posix())))


if __name__=='__main__':
    for k,v in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:os.environ[k]=str(ROOT/v)
    logging.disable(logging.CRITICAL)
    try:main()
    except Exception as e:
        result=dict(status='acquisition_failed',checked_at_utc=now(),error_type=type(e).__name__,http_status=getattr(getattr(e,'response',None),'status_code',None),no_model_or_array_load=True,signed_urls_persisted=False)
        if REPORT.exists():
            result['prior_receipt']=json.loads(REPORT.read_text(encoding='utf-8'))
        save(REPORT,result);print(json.dumps(result)[:2000]);raise SystemExit(1)
