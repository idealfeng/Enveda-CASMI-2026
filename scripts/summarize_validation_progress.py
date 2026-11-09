"""Collect persisted validation progress; never start inference or evaluate locked data."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import json


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'reports/validation_progress.json')
args = parser.parse_args()


def read(path):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


runs = []
for name, folder in [('flex', 'validation_flex_c2_20261105d'), ('v43', 'validation_v43_c2_20261105c')]:
    work = ROOT / 'runs' / folder
    receipt = read(work / 'validation_run_receipt.json')
    config = read(work / 'validation_config.json')
    item = dict(pipeline=name, work_root=str(work.relative_to(ROOT)), status=receipt.get('status', 'not_started'),
        processed_molecules=config.get('processed_molecules'), elapsed_seconds=receipt.get('elapsed_seconds'),
        latest_cell=receipt.get('cell_results', [])[-1:] or None,
        reference_policy=config.get('cohort_policy'), evaluation_label=config.get('evaluation_label'),
        run_receipt=str((work / 'validation_run_receipt.json').relative_to(ROOT)),
        e2_mask_audit=read(work / 'validation_e2_reference_audit.json').get('status'),
        runtime_audit=read(work / 'validation_runtime_audit.json').get('status'))
    if receipt.get('traceback'):
        item['last_error'] = receipt['traceback'].strip().splitlines()[-1]
    operator_stop = read(work / 'operator_stop.json')
    if operator_stop:
        item['status'] = operator_stop['status']
        item['last_error'] = operator_stop['reason']
        item['operator_stop'] = str((work / 'operator_stop.json').relative_to(ROOT))
    background_log = ROOT / 'runs' / (folder + '.console.log')
    pid_file = Path(str(background_log) + '.pid')
    exit_file = Path(str(background_log) + '.exit_code')
    if pid_file.exists():
        item['background_task'] = dict(linux_pid=pid_file.read_text().strip(),
            exit_code=int(exit_file.read_text().strip()) if exit_file.exists() else None,
            liveness='Not checked by this file collector; verify the current process identity separately.')
    runs.append(item)
component = ROOT / 'runs/component_neural_pilot_20261105'
component_files = sorted(p.name for p in component.glob('*.json')) if component.is_dir() else []
plan = read(component / 'plan.json')
component_receipt = read(component / 'run_receipt.json')
component_prepared = read(component / 'prepared.json')
component_evaluation = read(component / 'evaluation.json')
component_experiment = read(ROOT / 'experiments/COMP001_FOLD0_SANER_FIXED_CANDIDATES.json')
cloud_run = read(ROOT / 'reports/kaggle_baseline_run_20261105.json')
cloud_status = read(ROOT / 'reports/kaggle_baseline_v2_status.json')
cloud_outputs = read(ROOT / 'reports/kaggle_baseline_v2_output_verification_20261105.json')
submission = read(ROOT / 'reports/kaggle_first_submission_20261105.json')
submission_status = read(ROOT / 'reports/kaggle_first_submission_status.json')
tri_run = read(ROOT / 'reports/public_tri_v30_cloud_run_20261106.json')
tri_status = read(ROOT / 'reports/public_tri_v30_cloud_status_20261106.json')
tri_outputs = read(ROOT / 'reports/public_tri_v30_output_verification_20261106.json')
tri_submission = read(ROOT / 'reports/public_tri_v30_submission_20261106.json')
tri_submission_status = read(ROOT / 'reports/public_tri_v30_submission_status_20261106.json')
public_neural = read(ROOT / 'runs/exp004_public_neural_20261106/report.json')
submitted = True if submission.get('submission_ref') else None if submission else False
report = dict(local_work_date=datetime.now(timezone(timedelta(hours=8))).date().isoformat(), collected_at_utc=datetime.now(timezone.utc).isoformat(), runs=runs,
    component_pilot=dict(work_root=str(component.relative_to(ROOT)), planned_molecules=plan.get('molecules'),
                         status=component_receipt.get('status', component_prepared.get('status', plan.get('status', 'not_started'))),
                         elapsed_seconds=component_receipt.get('elapsed_seconds'),
                         baseline_metrics=component_evaluation.get('baseline_metrics'),
                         treatment_metrics=component_evaluation.get('metrics'),
                         fixed_candidate_audit=component_evaluation.get('fixed_candidate_audit'),
                         scope=component_experiment.get('scope'),
                         limitations=component_experiment.get('limitations', plan.get('limitations')),
                         persisted_json_files=component_files),
    dataset_integrity=read(ROOT / 'runs/validation_pilot_v2_20261104/dataset_integrity_report.json').get('status'),
    cloud=dict(target=cloud_run.get('target'), version=cloud_run.get('version_number'),
        persisted_session_status=cloud_status.get('session_status'),
        status_checked_at_utc=cloud_status.get('checked_at_utc'), output_audit=cloud_outputs.get('status'),
        submission_ref=submission.get('submission_ref'), submission_state=submission_status.get('status', submission.get('status')),
        submission_checked_at_utc=submission_status.get('checked_at_utc'),
        public_score=submission_status.get('public_score'),
        note='Persisted cloud receipts only; this collector performs no live status check or external action.'),
    public_neural_comparison=dict(status=public_neural.get('status', 'not_started'),
        scoring_layer=public_neural.get('scoring_layer'), metrics=public_neural.get('metrics'),
        elapsed_seconds=public_neural.get('elapsed_seconds'),
        public_control_byte_identical=public_neural.get('public_control_byte_identical'),
        limitations=public_neural.get('limitations')),
    public_tri_cloud=dict(target=tri_run.get('target'), version=tri_run.get('version_number'),
        persisted_session_status=tri_status.get('session_status'),
        status_checked_at_utc=tri_status.get('checked_at_utc'), output_audit=tri_outputs.get('status'),
        processed_molecules=tri_outputs.get('processed_molecules'),
        is_full_run=tri_outputs.get('is_full_run'),
        submission_ref=tri_submission.get('submission_ref'),
        submission_state=tri_submission_status.get('status', tri_submission.get('status', 'not_submitted')),
        public_score=tri_submission_status.get('public_score'),
        submission_checked_at_utc=tri_submission_status.get('checked_at_utc'),
        note='New V30 whole-recipe branch. Save&Run smoke success is not a hidden score; EXP004 is a separate fixed-candidate diagnostic.'),
    aggressive_batch=read(ROOT / 'reports/aggressive_batch_20261107/latest_status.json'),
    aggressive_batch_pm=read(ROOT / 'reports/aggressive_batch_20261107_pm/latest_status.json'),
    optimization_batch=read(ROOT / 'reports/optimization_20261108/latest_status.json'),
    optimization_batch_latest=read(ROOT / 'reports/optimization_20261109/latest_status.json'),
    optimization_dispatcher_latest=read(ROOT / 'reports/optimization_20261109/batch_dispatcher_status.json'),
    improvement_ledger=read(ROOT / 'reports/improvement_ledger.json'),
    candidate_multispectrum_head=read(ROOT / 'runs/candidate_head_20261108/summary.json'),
    isomer_residual_head=read(ROOT / 'runs/isomer_head_20261109/summary.json'),
    official_metric_rdkit='2026.03.3',
    hidden_score_reproduced=bool(submission_status.get('hidden_score_available')),
    kaggle_submission_performed=submitted,
    limitations=['Persisted cell progress is not a completed inference result.',
                 'The 48-query whole-stack pilot has known pretrained exposure.',
                 'The locked final cohort is not evaluated by this collector.'])
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
