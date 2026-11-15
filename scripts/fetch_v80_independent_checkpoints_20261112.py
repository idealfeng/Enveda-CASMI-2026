"""Read bounded, versioned public output files. No model execution or cloud writes."""
from pathlib import Path
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest


def main():
    import requests
    api = make_api()
    target = 'popwenman/casmi26-scorer-train-v80'
    folder = ROOT / 'assets/kaggle' / target / 'v1'
    report = ROOT / 'reports/optimization_20261112/v80_checkpoint_download.json'
    records = []
    wanted = ['casmi_spectrum_model_ours_v80/' + name for name in
              ['best_validation_model.pt', 'last_validation_model.pt', 'model.py', 'features.py']]
    with api.build_kaggle_client() as client:
        files = {}
        token = None
        for _ in range(20):
            req = ApiListKernelSessionOutputRequest()
            req.user_name, req.kernel_slug = target.split('/')
            req.version_label = 'v1'
            req.page_size = 100
            if token:
                req.page_token = token
            listing = client.kernels.kernels_api_client.list_kernel_session_output(req)
            for item in listing.files or []:
                files[item.file_name.replace('\\', '/')] = item
            token = listing.next_page_token
            if not token:
                break
        if token:
            raise ValueError('Output listing exceeded bounded pages')
    total = 0
    for name in wanted:
        if name not in files:
            records.append(dict(file=name, status='not_in_public_v1'))
            continue
        dest = folder / name
        if dest.exists():
            raw = dest.read_bytes()
            records.append(dict(file=name, status='already_present', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            continue
        limit = 16 * 1024 * 1024 if name.endswith('.pt') else 1024 * 1024
        chunks = []
        count = 0
        with requests.get(files[name].url, stream=True, timeout=(15, 45)) as response:
            response.raise_for_status()
            for block in response.iter_content(65536):
                count += len(block)
                if count > limit or total + count > 40 * 1024 * 1024:
                    raise ValueError('Public download size limit exceeded')
                chunks.append(block)
        raw = b''.join(chunks)
        total += len(raw)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(raw)
        receipt = dict(ref=target, version=1, source_file=name, bytes=len(raw),
                       sha256=hashlib.sha256(raw).hexdigest(), downloaded_at_utc=datetime.now(timezone.utc).isoformat(),
                       signed_urls_persisted=False, model_executed=False)
        dest.with_name(dest.name + '.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        records.append(dict(file=name, status='downloaded', bytes=len(raw), sha256=receipt['sha256']))
    author = dict(ref='ozertuu/casmi26-our-scorer-v80-model')
    try:
        from kagglesdk.datasets.types.dataset_api_service import ApiGetDatasetRequest
        req = ApiGetDatasetRequest()
        req.owner_slug, req.dataset_slug = author['ref'].split('/')
        with api.build_kaggle_client() as client:
            view = client.datasets.dataset_api_client.get_dataset(req)
        author.update(status='readable', current_version=getattr(view, 'current_version_number', None),
                      is_private=getattr(view, 'is_private', None))
    except Exception as error:
        author.update(status='unavailable', error_type=type(error).__name__,
                      http_status=getattr(getattr(error, 'response', None), 'status_code', None))
    record = dict(read_only=True, total_new_bytes=total, files=records, author_third_checkpoint=author,
                  no_model_executed=True, no_cloud_write=True)
    report.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    for key, sub in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'), ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        os.environ[key] = str(ROOT / sub)
    logging.disable(logging.CRITICAL)
    main()
