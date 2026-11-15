"""Check new attribution routes in isolated D-drive fixtures; no network or real writes."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import kaggle_batch as batch
import review_gain_ledger_20261113 as fixtures
import watch_all_today_20261113 as worker
import watch_batch_with_ledger_20261113 as strict

ROOT = Path(__file__).resolve().parents[1]


def rebind(f, name, ref):
    spec = f['manifest']['branches'][0]
    spec['name'] = name
    spec['required_runtime_audits'][0]['expected_fields']['branch'] = name
    state = f['root']/f['manifest']['state_root']/name
    state.mkdir(parents=True, exist_ok=True)
    for filename in ('submission.json', 'score.json'):
        receipt = fixtures.read(f['state']/filename)
        receipt.update(branch_sha256=batch.branch_sha(spec), submission_ref=ref)
        fixtures.write(state/filename, receipt)
    f['row'].update(branch=name, submission_ref=ref)
    return state


def main():
    checks = {}
    before = {n: fixtures.sha(ROOT/'reports'/n)
              for n in ('improvement_ledger.json', 'IMPROVEMENT_LEDGER.md')}
    with patch.object(strict, 'ATTRIBUTIONS', worker.ATTRIBUTIONS):
        for index, name in enumerate(worker.ATTRIBUTIONS):
            with fixtures.fixture() as f:
                ref = 92000001 + index
                rebind(f, name, ref)
                added = strict.record_gains(f['manifest'], f['result'])
                entry = fixtures.read(f['ledger'])['records'][-1]
                checks[name+'_source_and_gain_bound'] = (
                    added == [ref] and entry['source'] == worker.ATTRIBUTIONS[name][0]
                    and entry['attribution_limit'] == worker.ATTRIBUTIONS[name][1]
                    and entry['ref'] == ref and entry['comparison_anchor_ref'] == 58156482)
                checks[name+'_idempotent'] = not strict.record_gains(f['manifest'], f['result'])
                f['row'].update(status='PENDING', public_score_available=False, public_score=None)
                checks[name+'_pending_no_gain'] = not strict.record_gains(f['manifest'], f['result'])
        with fixtures.fixture() as f:
            first = copy.deepcopy(f['manifest'])
            second = copy.deepcopy(f['manifest'])
            spec = second['branches'][0]
            spec['name'] = 'head_mean_ab'
            spec['required_runtime_audits'][0]['expected_fields']['branch'] = 'head_mean_ab'
            second['state_root'] = 'reports/another_state'
            state = f['root']/second['state_root']/spec['name']
            for filename in ('submission.json', 'score.json'):
                receipt = fixtures.read(f['state']/filename)
                receipt.update(branch_sha256=batch.branch_sha(spec), submission_ref=93000002)
                if filename == 'score.json': receipt['public_score'] = .490
                fixtures.write(state/filename, receipt)
            row = dict(f['row'], branch='head_mean_ab', submission_ref=93000002, public_score=.490)
            strict.record_gains(first, f['result'])
            strict.record_gains(second, dict(branches=[row]))
            ledger = fixtures.read(f['ledger'])
            checks['two_manifests_sequential_no_lost_gain'] = (
                ledger['current_best'] == .490
                and [r['ref'] for r in ledger['records'][-2:]] == [91000001, 93000002])
            checks['duplicate_lower_gain_not_readded'] = not strict.record_gains(first, f['result'])
    checks['real_ledger_files_unchanged'] = all(
        fixtures.sha(ROOT/'reports'/n) == sha for n, sha in before.items())
    source = (ROOT/'scripts/watch_all_today_20261113.py').read_text(encoding='utf-8')
    checks['old_writer_lock_gate_present'] = "(state/'watcher.lock').exists()" in source
    checks['single_writer_exclusive_claim_present'] = "batch.claim(lock, record)" in source
    checks['manifest_pins_rechecked'] = "[batch.sha(p) for p in paths] != pins" in source
    result = dict(status='passed' if all(checks.values()) else 'failed', checks=checks,
                  source_sha256=fixtures.sha(ROOT/'scripts/watch_all_today_20261113.py'),
                  no_network=True, real_ledger_writes=False)
    fixtures.write(ROOT/'reports/optimization_20261113/all_today_watcher_review.json', result)
    print(json.dumps(dict(status=result['status'], passed=sum(checks.values()),
                          total=len(checks), failed=[k for k,v in checks.items() if not v])))
    if not all(checks.values()): raise ValueError('Daily watcher fixture failed')


if __name__ == '__main__': main()
