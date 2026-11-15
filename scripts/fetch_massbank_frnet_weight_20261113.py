"""Public FRNet weight and source-card investigation; no Torch import or inference."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,logging,os,re,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.datasets.types.dataset_api_service import ApiGetDatasetRequest,ApiDownloadDatasetRequest


def main():
    import requests
    api=make_api();ref='agentili/casmi26-fr-reranker-blend';dest=ROOT/'assets/kaggle'/ref/'v2'
    rpt=ROOT/'reports/optimization_20261113';req=ApiGetDatasetRequest();req.owner_slug,req.dataset_slug=ref.split('/')
    with api.build_kaggle_client() as c:v=c.datasets.dataset_api_client.get_dataset(req)
    expected='21f70d461564a1db09ce7e181a138538b8efcef2f05c67050f042c607560ff7e'
    name='fr_model.pt';p=dest/name
    if not p.exists():
        req=ApiDownloadDatasetRequest();req.owner_slug,req.dataset_slug=ref.split('/');req.dataset_version_number=2;req.file_name=name
        with api.build_kaggle_client() as c:redirect=c.datasets.dataset_api_client.download_dataset(req)
        with requests.get(redirect.request.url,stream=True,timeout=(15,45)) as r:
            r.raise_for_status();data=bytearray()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data)>4*1024*1024:raise ValueError('Weight size cap')
        if len(data)!=3100917 or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Weight pin differs')
        with p.open('xb') as f:f.write(data)
    if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('Existing weight pin differs')
    record=dict(ref=ref,version=2,file=name,bytes=p.stat().st_size,sha256=expected,model_executed=False,downloaded_at_utc=datetime.now(timezone.utc).isoformat(),signed_urls_persisted=False)
    p.with_name(p.name+'.receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    meta=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),api_fields=list(v.to_dict()),
              license_name=v.license_name,description=v.description,weight=record,public_page={})
    # Normal public HTML, not browser session state; retain raw card only if served.
    url='https://www.kaggle.com/datasets/'+ref
    try:
        response=requests.get(url,timeout=(15,30));response.raise_for_status()
        if len(response.content)>8*1024*1024:raise ValueError('Page cap')
        text=response.text
        (rpt/'massbank_frnet_public_page.html').write_bytes(response.content)
        meta['public_page']=dict(status=response.status_code,bytes=len(response.content),has_dataset_description='datasetDescription' in text,
            has_description_text=bool(v.description),has_nist_word=bool(re.search(r'\bNIST\b',text,re.I)),has_license_text='Creative Commons' in text)
    except Exception as e:meta['public_page']=dict(status='unavailable',error_type=type(e).__name__)
    refs=[]
    try:
        rows=api.kernels_list(user='agentili',search='casmi',page=1,page_size=100) or []
        for r in rows:refs.append(dict(ref=getattr(r,'ref',None),title=getattr(r,'title',None),last_run_time=str(getattr(r,'last_run_time',None))))
        meta['public_author_notebooks']=refs
    except Exception as e:meta['author_notebooks']=dict(status='unavailable',error_type=type(e).__name__)
    (rpt/'massbank_frnet_license_investigation.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
    print(json.dumps(meta,indent=2,ensure_ascii=False,default=str))


if __name__=='__main__':
    for k,r in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:os.environ[k]=str(ROOT/r)
    logging.disable(logging.CRITICAL)
    try:main()
    except Exception as e:
        print(json.dumps(dict(status='failed',error_type=type(e).__name__,http_status=getattr(getattr(e,'response',None),'status_code',None))))
        raise SystemExit(1)
