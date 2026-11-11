"""Archive public source/metadata only; do not execute or download model assets."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')


def main():
    refs = ['ozertuu/casmi26-dual-neural-physical-isomer',
            'ozertuu/0-500-casmi26-dual-neural-physical-isomer']
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = ROOT / 'reports/public_update_20261111' / ('ozertuu_refresh_' + stamp)
    folder.mkdir(parents=True, exist_ok=False)
    api = make_api()
    results = []
    for index, ref in enumerate(refs):
        try:
            req = ApiGetKernelRequest()
            req.user_name, req.kernel_slug = ref.split('/')
            with api.build_kaggle_client() as client:
                response = client.kernels.kernels_api_client.get_kernel(req)
            meta = response.metadata
            raw = response.blob.source.encode('utf-8')
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('Source-only size limit exceeded')
            notebook = json.loads(raw)
            if not isinstance(notebook.get('cells'), list):
                raise ValueError('Expected Notebook source')
            dest = folder / str(index)
            dest.mkdir()
            (dest / 'source.ipynb').write_bytes(raw)
            fields = ['id', 'ref', 'title', 'current_version_number', 'last_run_time',
                      'is_private', 'enable_gpu', 'enable_internet', 'dataset_data_sources',
                      'kernel_data_sources', 'competition_data_sources', 'model_data_sources',
                      'docker_image', 'machine_shape', 'public_score', 'best_score']
            record = {key: getattr(meta, key, None) for key in fields}
            record.update(requested_ref=ref, checked_at_utc=datetime.now(timezone.utc).isoformat(),
                          source_sha256=hashlib.sha256(raw).hexdigest(), source_bytes=len(raw),
                          executed=False, model_assets_downloaded=False)
            save(dest / 'metadata.json', record)
            review = []
            for i, cell in enumerate(notebook['cells']):
                source = cell.get('source', '')
                if isinstance(source, list):
                    source = ''.join(source)
                review.append(f"\n# ---- {cell.get('cell_type')} cell {i} ----\n{source}")
            (dest / 'source_review.txt').write_text('\n'.join(review), encoding='utf-8')
            results.append(dict(status='downloaded', path=str(dest.relative_to(ROOT)), **record))
        except Exception as error:
            results.append(dict(status='failed', requested_ref=ref, error_type=type(error).__name__,
                                http_status=getattr(getattr(error, 'response', None), 'status_code', None)))
    save(folder / 'receipt.json', dict(source_only=True, results=results))
    print(json.dumps(dict(folder=str(folder.relative_to(ROOT)), results=results), indent=2, default=str))


if __name__ == '__main__':
    for key, rel in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'),
                     ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        os.environ[key] = str(ROOT / rel)
    logging.disable(logging.CRITICAL)
    main()
