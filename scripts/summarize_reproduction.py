"""Collect existing run receipts and hash-bound comparisons without running models."""
from pathlib import Path
import argparse
import hashlib
import json


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tag', default='20261104b')
parser.add_argument('--output', type=Path, default=ROOT / 'reports/reproduction_status.json')
args = parser.parse_args()


def read(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


runs = []
for scheme, version in [('prvsiyan', 'V43'), ('canqiang', 'E006 V1'), ('flexonafft', 'V56')]:
    work = ROOT / 'runs' / f'{scheme}_smoke_{args.tag}'
    receipt_name = 'local_reproduction_status.json' if scheme == 'flexonafft' else 'local_run_receipt.json'
    receipt = read(work / receipt_name)
    comparison_path = ROOT / 'reports' / f'{scheme}_smoke_comparison.json'
    comparison = read(comparison_path)
    final = work / 'submission.csv'
    output_sha = hashlib.sha256(final.read_bytes()).hexdigest() if final.is_file() else None
    comparison_bound = bool(output_sha and comparison.get('actual_sha256') == output_sha)
    active = receipt.get('processed_molecules')
    base = read(work / 'e004_verification.json')
    if active is None:
        active = base.get('processed_molecules')
    item = dict(scheme=scheme, version=version, status=receipt.get('status', 'not_started'),
                work_root=str(work.relative_to(ROOT)), receipt=receipt_name,
                elapsed_seconds=receipt.get('elapsed_seconds'),
                engine2_reused=bool(receipt.get('engine2_reuse')),
                processed_molecules=active, output_sha256=output_sha,
                comparison_hash_matches_output=comparison_bound,
                matching_molecules=comparison.get('matching_molecules') if comparison_bound else None)
    if receipt.get('cell_results'):
        item['latest_cell'] = receipt['cell_results'][-1]
    else:
        item['last_completed_cell'] = receipt.get('last_completed_cell')
    if scheme != 'flexonafft':
        prior = read(ROOT / 'runs' / f'{scheme}_smoke_20261104a' / 'local_run_receipt.json')
        cell = 12 if scheme == 'prvsiyan' else 11
        item['prior_engine2_seconds'] = next((x.get('elapsed_seconds') for x in
            prior.get('cell_results', []) if x['cell'] == cell and x['status'] == 'complete'), None)
    else:
        audit = read(ROOT / 'reports/flexonafft_smoke_audit.json')
        item['execution_audit'] = {k: audit.get(k) for k in
            ['status', 'failed_checks', 'required_unknown_checks', 'allowed_skips']}
    runs.append(item)
report = dict(tag=args.tag, runs=runs, hidden_score_reproduced=False,
    scope='Original 12-molecule visible-placeholder smoke; remaining rows can be padding.',
    timing='Runner elapsed time; Engine2 recovery reuse is explicitly recorded. Not full-test timing.')
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
