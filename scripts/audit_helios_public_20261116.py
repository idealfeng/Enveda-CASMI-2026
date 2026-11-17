"""Read-only Helios public-demo source/dependency reproducibility audit."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import logging
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'reports/public_review_20261116/notebooks/heliosli__casmi26-0-494-public-demo'
OUT = ROOT / 'reports/public_review_20261116/helios_audit'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    record = dict(checked_at_utc=datetime.now(timezone.utc).isoformat(), external_read_only=True,
                  model_bytes_downloaded=0, source_executed=False,
                  source_path=str((SOURCE / 'source.ipynb').relative_to(ROOT)),
                  source_sha256=sha(SOURCE / 'source.ipynb'),
                  metadata_sha256=sha(SOURCE / 'metadata.json'))
    book = json.loads((SOURCE / 'source.ipynb').read_text(encoding='utf-8'))
    metadata = json.loads((SOURCE / 'metadata.json').read_text(encoding='utf-8'))
    record.update(version=metadata['current_version_number'], public_title_claim='.494',
                  title_score_is_not_official_submission_readback=True,
                  dataset_refs=metadata['dataset_data_sources'])
    code = {}
    for index, cell in enumerate(book['cells']):
        if cell['cell_type'] != 'code':
            continue
        text = cell['source']; text = ''.join(text) if isinstance(text, list) else text
        compile(text, 'helios_public_source_only', 'exec')
        code[index] = text
    record['source_cells_compile'] = True
    record['static_findings'] = dict(
        all_runtime_new_models_optional_skip=True,
        M5_required_dataset_not_in_metadata='heliosli/casmi26-m5' not in metadata['dataset_data_sources'],
        M5_package_manifest_required='m5_manifest.json' in code[27],
        M5_current_mode='swap', M5_probe_mode_active=False,
        rr3_cfg_required='rr3_config.json', frigid_requires_second_gpu=True,
        frigid_hidden_deadline_hours=8.2, visible_default='smoke12',
        CV_joint_final_rank1_swaps_or_rank2_insert=True,
        new_RT_and_PX_checkpoint_assets_required=True,
        parent_documented_result='.477 / submission57722897 read2026-10-29',
        no_documented_494_submission_ref_in_markdown=True,
        raw_inchikey_gates_not_official_tautomer_normalized=True)
    dep = ROOT / 'reports/public_review_20261116/notebooks/dependency_inventory'
    dependencies = []
    for ref in metadata['dataset_data_sources']:
        if ref.startswith('heliosli/'):
            path = dep / (ref.replace('/', '__') + '.json')
            if path.exists():
                dependencies.append(dict(json.loads(path.read_text(encoding='utf-8')), evidence_path=str(path.relative_to(ROOT)), evidence_sha256=sha(path)))
    record['existing_dependency_api_evidence'] = dependencies
    sys.path.insert(0, str(ROOT / 'scripts'))
    from kaggle_first_submission import make_api
    api = make_api()
    public_rows = []
    try:
        for page in range(1, 6):
            rows = api.dataset_list(user='heliosli', page=page) or []
            public_rows.extend(dict(ref=getattr(item, 'ref', None), title=getattr(item, 'title', None),
                                    bytes=getattr(item, 'total_bytes', None), is_private=getattr(item, 'is_private', None)) for item in rows)
            if len(rows) < 20:
                break
        record['public_author_inventory'] = dict(status='read', rows=public_rows, pages=page, bounded_page_cap=5)
    except Exception as error:
        record['public_author_inventory'] = dict(status='failed', error_type=type(error).__name__,
            http_status=getattr(getattr(error, 'response', None), 'status_code', None))
    try:
        response = api.dataset_list_files('heliosli/casmi26-m5', page_size=100)
        record['missing_M5_direct_file_inventory'] = dict(status='read', response=response.to_dict())
    except Exception as error:
        record['missing_M5_direct_file_inventory'] = dict(status='failed', error_type=type(error).__name__,
            http_status=getattr(getattr(error, 'response', None), 'status_code', None))
    record['conclusion'] = 'Public source alone cannot reproduce the .494-title full model composition; missing/unavailable model packages must not be silently counted as full reproduction.'
    save(OUT / 'audit.json', record)
    print(json.dumps(dict(version=record['version'], source_sha256=record['source_sha256'],
        public_author_datasets=record['public_author_inventory'], missing_M5_inventory=record['missing_M5_direct_file_inventory'],
        dependency_failures=[(d['ref'], d.get('http_status')) for d in dependencies], conclusion=record['conclusion']), ensure_ascii=True, default=str))


if __name__ == '__main__':
    for key, suffix in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'), ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        path = ROOT / suffix; path.mkdir(parents=True, exist_ok=True); os.environ[key] = str(path)
    logging.disable(logging.CRITICAL)
    main()
