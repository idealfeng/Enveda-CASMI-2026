"""Prepare/verify a fixed-candidate Na-only GL probe. Never alter original ranks."""
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT/'reports/forward_coverage_20261108'
RUN = ROOT/'runs/validation_flex_c2_20261105d'
PKG = ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier'
WHEELS = PKG.parent/'casmi26-iceberg/wheels'


def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def write(path, obj): path.write_text(json.dumps(obj, indent=2)+'\n', encoding='utf-8')
def linux(path): return '/mnt/d/Paper/casmi/'+path.resolve().relative_to(ROOT).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'runs/gl_na_probe_20261108')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args(); out = args.output.resolve()
    if not out.is_relative_to(ROOT): raise ValueError('Keep all artifacts in D workspace')
    if args.verify:
        receipt = read(out/'prepare.json'); items = read(out/'input.json')
        current = read(out/'gl_out.json'); meta = read(out/'gl_out.json.meta.json')
        trace = [json.loads(line) for line in (out/'per_spectrum.jsonl').read_text().splitlines()]
        cov = [r for r in trace if r.get('event') == 'spectrum_coverage']
        pairs = [r for r in trace if r.get('event') == 'candidate_spectrum_score']
        # Trace event schema remains audited explicitly; do not accept an empty selection.
        if not pairs: pairs = [r for r in trace if 'candidate_smiles' in r and 'spectrum_index' in r]
        expected = {(str(i['mid']), s, c) for i in items for s in range(len(i['spectra'])) for c in i['cands']}
        seen = {(str(r['mid']), r['spectrum_index'], r['candidate_smiles']) for r in pairs}
        finite = lambda v: isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
        means = {}; mean_errors = []; maximum_difference = 0.
        for item in items:
            mid = str(item['mid'])
            for candidate in item['cands']:
                values = [r['score'] for r in pairs if str(r['mid']) == mid and r['candidate_smiles'] == candidate and finite(r.get('score'))]
                target = current.get(mid, {}).get(candidate)
                if len(values) != len(item['spectra']) or not finite(target): mean_errors.append((mid, candidate)); continue
                value = sum(values)/len(values)
                maximum_difference = max(maximum_difference, abs(value-target))
                means[(mid, candidate)] = value
        checks = dict(original_hplus_input_unchanged=sha(RUN/'gl_work/gl_in.json') == receipt['original_gl_input_sha256'],
            original_hplus_output_unchanged=sha(RUN/'gl_work/gl_out.json') == receipt['original_gl_output_sha256'],
            probe_input_unchanged=sha(out/'input.json') == receipt['input_sha256'],
            identity_map_unchanged=sha(out/'official_identities.json') == receipt['identity_map_sha256'],
            actual_checkpoint_unchanged=sha(PKG/'ckpt/glacier.pt') == receipt['checkpoint_sha256'],
            model_completed=meta.get('status') == 'ok', model_reported_no_errors=not meta.get('errors'),
            exact_query_set=set(current) == {str(i['mid']) for i in items},
            exact_candidate_sets=all(set(current.get(str(i['mid']), {})) == set(i['cands']) for i in items),
            all_outputs_finite=all(finite(v) for values in current.values() for v in values.values()),
            all_na_coverage=len(cov) == sum(len(i['spectra']) for i in items) and all(r.get('covered') and r.get('adduct') == '[M+Na]+' for r in cov),
            complete_unique_pairs=seen == expected and len(pairs) == len(expected),
            all_pair_scores_finite=all(r.get('status') == 'scored' and finite(r.get('score')) for r in pairs),
            aggregate_means_reconstructed=not mean_errors and maximum_difference <= 1e-12)
        report = dict(status='passed' if all(checks.values()) else 'failed', checks=checks, runtime=meta,
            queries=len(items), spectra=sum(len(i['spectra']) for i in items),
            candidate_rows=sum(len(i['cands']) for i in items), candidate_spectrum_pairs=len(pairs),
            maximum_mean_difference=maximum_difference, mean_error_count=len(mean_errors),
            output_sha256=sha(out/'gl_out.json'), trace_sha256=sha(out/'per_spectrum.jsonl'),
            rankings_changed=False, accuracy_evaluated=False, training_performed=False,
            note='Na inference/coverage only. This does not establish a ranking or hidden leaderboard gain.')
        write(out/'verification.json', report)
        print(json.dumps({k: report[k] for k in ('status', 'checks', 'queries', 'spectra', 'candidate_rows', 'candidate_spectrum_pairs', 'maximum_mean_difference')}, indent=2))
        if not all(checks.values()): raise ValueError('Na probe verification failed')
        return
    if out.exists(): raise FileExistsError('Use a fresh probe directory')
    audit = read(AUDIT/'summary.json'); items = read(AUDIT/'gl_missing_na_input.json')
    original = {str(i['mid']): i for i in read(RUN/'ice_work/ice_in.json')}
    for item in items:
        prior = original[str(item['mid'])]
        if item['cands'] != prior['cands']: raise ValueError('Candidate list changed')
        for spectrum in item['spectra']:
            if spectrum not in prior['spectra'] or spectrum['adduct'] != '[M+Na]+': raise ValueError('Na input changed')
    if len(items) != 12 or sum(len(i['spectra']) for i in items) != 17: raise ValueError('Unexpected frozen Na scope')
    out.mkdir()
    for source, target in [('gl_missing_na_input.json', 'input.json'), ('gl_missing_na_official_identities.json', 'official_identities.json')]:
        (out/target).write_bytes((AUDIT/source).read_bytes())
    command = [linux(ROOT/'.venv-linux/bin/python'), linux(ROOT/'scripts/forward_trace_runner.py'), linux(PKG),
        linux(out/'input.json'), linux(out/'gl_out.json'), '--run-model', '--identity-map', linux(out/'official_identities.json'),
        '--trace-jsonl', linux(out/'per_spectrum.jsonl'), '--site', linux(RUN/'ice_site'), '--wheels', linux(WHEELS),
        '--device', 'cuda', '--budget', '0', '--bs', '32', '--threads', '4', '--quiet']
    script = '#!/usr/bin/env bash\nset -euo pipefail\nsource '+shlex.quote(linux(ROOT/'scripts/linux_env.sh'))+'\nexec '+shlex.join(command)+'\n'
    (out/'run.sh').write_text(script, encoding='utf-8', newline='\n')
    write(out/'prepare.json', dict(status='prepared_no_model_run', prepared_utc=datetime.now(timezone.utc).isoformat(),
        input_sha256=sha(out/'input.json'), identity_map_sha256=sha(out/'official_identities.json'),
        original_gl_input_sha256=sha(RUN/'gl_work/gl_in.json'), original_gl_output_sha256=sha(RUN/'gl_work/gl_out.json'),
        checkpoint_sha256=audit['checkpoint']['sha256'], actual_checkpoint_support=audit['checkpoint'],
        source_audit_sha256=sha(AUDIT/'summary.json'), command=command, run_script_sha256=sha(out/'run.sh'),
        candidate_policy='original ICE candidate lists, unchanged order; only original Na spectra absent from GL input',
        no_candidate_selection_from_truth=True, ranking_not_changed=True, hidden_or_locked250_not_read=True))
    print(json.dumps(dict(status='prepared', queries=len(items), spectra=sum(len(i['spectra']) for i in items),
        command='wsl -d Ubuntu --exec bash '+shlex.quote(linux(out/'run.sh'))), indent=2))


if __name__ == '__main__': main()
