"""Offline audit of downloaded tri-model V1 outputs. Never edit the submission CSV."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import math
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TARGET = 'stormseye/casmi26-public-tri-v30'
VERSION = 1
DEFAULT_INPUT = ROOT/'runs/public_tri_cloud_v1_outputs_20261106'
DEFAULT_REPORT = ROOT/'reports/public_tri_v30_output_verification_20261106.json'
RUN_RECEIPT = ROOT/'reports/public_tri_v30_cloud_run_20261106.json'
BINDING = ROOT/'reports/public_tri_v30_server_binding_20261106.json'
SAMPLE = ROOT/'enveda-CASMI26-molecule-id-mass-spectra/sample_submission.csv'
REQUIRED = ('submission.csv','public_neural_input_audit.json','public_neural_execution_audit.json')
UPSTREAM_SHA = '73c8bdc7799ffdad7ef756015c74c90365ee060122f2567f8a3c061ff42cc0df'
SMOKE_SHA = 'b8ebb7ac69f726c191c6888c186b7cdffae72adf474b64c82611137da43a2b15'
PUBLIC_PINS = {
    'features.py':'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455',
    'model.py':'2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39',
    'config.json':'563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03',
    'final_model.pt':'44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642',
}
MODELS = {
    'v2':dict(checkpoint_sha256='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46',
              config_sha256='5ed9578966792110846b3bf7c11a34d8247fa8e57d168b37124d208924fd9524'),
    'v4':dict(checkpoint_sha256='10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51',
              config_sha256='3ee4f2ebe68d21bcd251214ecb23bdf0837b6c4cfae9efc467ca9fcabbdf69a4'),
}
LOTUS_SHA='7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f'
REQUIRED_RUNTIME_CHECKS = {
    'input_preflight','pipeline_and_three_scoring_calls','metric_rdkit',
    'public_actual_bundle_pins','v2_actual_bundle_pins','v4_actual_bundle_pins',
    'three_distinct_checkpoints','three_model_candidate_keys','combined_candidate_keys',
    'processed_ids_match_effective_queries','processed_masks_equal','new_model_coverage_equals_public',
    'combined_ok_matches_original_and','public_usable_scores_finite','v2_usable_scores_finite',
    'v4_usable_scores_finite','combined_scores_finite_including_inactive','exact_three_way_combined_scores',
    'csv_columns','csv_id_order','csv_unique_ids','csv_guess_count_and_nonempty','csv_bytes_unchanged_by_observer',
}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(path):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT):raise ValueError('All paths must stay inside the D: workspace')
    return path


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        return reader.fieldnames,list(reader)


def identity_diagnostics(rows, active_ids, identity, parse_guesses):
    """Invalid/nonmatching guesses are quality findings; duplicate identities consume rank."""
    invalid,duplicates,bad_length,empty_fields=[],[],[],[]
    counts=[]
    for row in rows:
        mid=row.get('molecule_id')
        raw=row.get('smiles')
        if isinstance(raw,str) and any(not part.strip() for part in raw.split(';')):
            empty_fields.append(mid)
        try:guesses=parse_guesses(raw)
        except (ValueError,TypeError):
            bad_length.append(mid)
            continue
        counts.append(len(guesses))
        keys=[identity(smiles) for smiles in guesses]
        if None in keys:
            invalid.append(dict(molecule_id=mid,count=keys.count(None),active=mid in active_ids))
        valid=[key for key in keys if key is not None]
        repeated=len(valid)-len(set(valid))
        if repeated:
            duplicates.append(dict(molecule_id=mid,count=repeated,active=mid in active_ids))
    return dict(invalid_identity_rows=invalid,duplicate_identity_rows=duplicates,
        duplicate_identity_slots=sum(row['count'] for row in duplicates),bad_length_rows=bad_length,
        empty_semicolon_field_rows=empty_fields,min_guesses=min(counts) if counts else None,
        max_guesses=max(counts) if counts else None,
        duplicate_policy='Recorded, not automatically rejected: official metric consumes their rank positions.',
        original_csv_modified=False)


def verify(input_dir):
    from validation import metric
    input_dir=inside(input_dir)
    if input_dir==ROOT:raise ValueError('Expected a separate downloaded-output directory')
    run,binding,download=read(RUN_RECEIPT),read(BINDING),read(input_dir/'download_receipt.json')
    if (run.get('target')!=TARGET or run.get('status')!='run_requested' or run.get('version_number')!=VERSION
            or binding.get('status')!='passed' or binding.get('target')!=TARGET or binding.get('version')!=VERSION):
        raise ValueError('Accepted V1 receipt and passing private/source binding required')
    if (download.get('status')!='downloaded' or download.get('target')!=TARGET or download.get('version')!=VERSION
            or download.get('session_status')!='COMPLETE' or download.get('missing_required')):
        raise ValueError('Completed version-bound small-output download required')
    checks={}
    checks['staged_notebook_hash_bound']=(binding.get('staged_notebook_sha256')==run.get('notebook_sha256')==download.get('notebook_sha256'))
    checks['server_source_observation_bound']=(binding.get('server_source_sha256')==download.get('server_source_sha256')
        and isinstance(binding.get('server_source_sha256'),str) and len(binding['server_source_sha256'])==64)
    checks['server_cell_semantics_bound']=binding.get('checks',{}).get('source_semantics') is True
    checks['private_offline_source_binding_passed']=bool(binding.get('checks')) and all(v is True for v in binding['checks'].values())
    checks['binding_receipt_hash']=download.get('binding_sha256')==sha(BINDING)
    files=download.get('downloaded_files',[])
    names=[item.get('name') for item in files]
    if len(names)!=len(set(names)) or not set(REQUIRED)<=set(names):
        raise ValueError('Missing or duplicate required output receipt entries')
    for item in files:
        path=inside(ROOT/item['path'])
        expected=(input_dir/item['name']).resolve()
        if not expected.is_relative_to(input_dir) or path!=expected:
            raise ValueError('Downloaded receipt path/name does not stay inside its output directory')
        if sha(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:
            raise ValueError('Downloaded artifact changed: '+item['name'])
    checks['all_downloaded_hashes_match']=True
    pre=read(input_dir/'public_neural_input_audit.json')
    execution=read(input_dir/'public_neural_execution_audit.json')
    checks['both_runtime_audits_passed']=pre.get('status')=='passed' and execution.get('status')=='passed'
    checks['runtime_upstream_recipe_bound']=(pre.get('upstream_source_sha256')==execution.get('upstream_source_sha256')==UPSTREAM_SHA)
    checks['runtime_smoke_adaptation_bound']=(pre.get('smoke_source_sha256')==execution.get('smoke_source_sha256')==SMOKE_SHA)
    checks['input_audit_hash_bound']=execution.get('input_audit_sha256')==sha(input_dir/'public_neural_input_audit.json')
    checks['observers_do_not_modify_scores_or_candidates']=(pre.get('scoring_or_candidate_changes') is False and execution.get('scoring_or_candidate_changes') is False)
    runtime_checks=execution.get('checks',{})
    checks['runtime_required_checks_present']=REQUIRED_RUNTIME_CHECKS<=set(runtime_checks)
    checks['all_runtime_checks_true']=bool(runtime_checks) and all(value is True for value in runtime_checks.values())
    pins=pre.get('inputs',{})
    checks['native_public_four_pins']=pins.get('public',{}).get('pins')==PUBLIC_PINS
    checks['native_lotus_pin']=pins.get('lotus',{}).get('sha256')==LOTUS_SHA
    checks['native_new_model_pins']=all(all(pins.get(name,{}).get(key)==value for key,value in expected.items()) for name,expected in MODELS.items())
    models=execution.get('models',{})
    for name in ('public','v2','v4'):
        wanted=dict(PUBLIC_PINS)
        if name!='public':
            wanted['final_model.pt']=MODELS[name]['checkpoint_sha256']
            wanted['config.json']=MODELS[name]['config_sha256']
        checks[name+'_actual_staged_model_pins']=models.get(name,{}).get('pins')==wanted
    checks['three_distinct_actual_models']=len({models.get(n,{}).get('pins',{}).get('final_model.pt') for n in ('public','v2','v4')})==3
    difference=execution.get('combined_score_max_abs_difference')
    checks['combined_score_values_exact']=isinstance(difference,(int,float)) and not isinstance(difference,bool) and math.isfinite(difference) and difference==0
    sample_columns,sample_rows=read_csv(SAMPLE)
    columns,rows=read_csv(input_dir/'submission.csv')
    sample_ids=[row['molecule_id'] for row in sample_rows]
    ids=[row.get('molecule_id') for row in rows]
    active=execution.get('active_ids',[])
    active_ids=set(active)
    checks['csv_columns']=columns==['molecule_id','smiles']
    checks['csv_unique_nonempty_ids']=len(ids)==len(set(ids)) and all(isinstance(mid,str) and mid.strip() for mid in ids)
    checks['csv_matches_official_sample_id_order']=ids==sample_ids
    checks['csv_400_rows']=len(rows)==len(sample_rows)==400
    checks['runtime_sample_order_assertion']=runtime_checks.get('csv_id_order') is True
    checks['runtime_scope_counts']=(len(active)==len(active_ids)==execution.get('processed_molecules')
        and execution.get('input_molecules')==len(rows) and active_ids<=set(ids)
        and execution.get('placeholder_rows')==len(rows)-len(active_ids))
    full=execution.get('is_full_run')
    checks['runtime_mode_declared']=isinstance(full,bool)
    if full is False:
        checks['visible_smoke12']=len(active_ids)==12 and active_ids==set(sorted(sample_ids)[:12])
        checks['visible_common_coverage_usable']=all(models.get(name,{}).get('usable_molecules')==12 and not models.get(name,{}).get('unsupported_molecules') for name in ('public','v2','v4'))
        checks['visible_runtime_check_flags']=(runtime_checks.get('visible_smoke12') is True and runtime_checks.get('visible_all_active_usable') is True)
    elif full is True:
        checks['full_public_input_coverage']=active_ids==set(ids)
    checks['main_model_coverage_consistent']=all(
        models.get(name,{}).get('active_candidates')==models.get('public',{}).get('active_candidates')
        and models.get(name,{}).get('usable_candidates')==models.get('public',{}).get('usable_candidates')
        and models.get(name,{}).get('usable_molecules')==models.get('public',{}).get('usable_molecules')
        and models.get(name,{}).get('unsupported_molecules')==models.get('public',{}).get('unsupported_molecules')
        for name in ('v2','v4'))
    checks['official_rdkit']=metric.assert_official_rdkit()=='2026.03.3'
    csv_before=sha(input_dir/'submission.csv')
    diagnostics=identity_diagnostics(rows,active_ids,metric.identity,metric.parse_guesses)
    checks['candidate_count_1_to_25']=not diagnostics['bad_length_rows']
    checks['all_candidates_have_metric_identity']=not diagnostics['invalid_identity_rows']
    checks['submission_runtime_sha_bound']=execution.get('submission',{}).get('sha256')==csv_before
    checks['submission_runtime_rows_and_bytes']=(execution.get('submission',{}).get('rows')==len(rows)
        and execution.get('submission',{}).get('bytes')==(input_dir/'submission.csv').stat().st_size)
    checks['csv_bytes_unchanged_by_verifier']=sha(input_dir/'submission.csv')==csv_before
    if (input_dir/'e004_verification.json').is_file():
        baseline=read(input_dir/'e004_verification.json')
        checks['baseline_effective_ids_agree']=set(baseline.get('processed_ids',[]))==active_ids
        checks['baseline_input_id_set_agrees']=set(baseline.get('input_ids',[]))==set(ids)
        checks['baseline_main_errors_zero']=baseline.get('base_errors')==0
    warnings=[]
    if diagnostics['duplicate_identity_rows']:
        warnings.append('Duplicate official identities consume candidate ranks; they do not alone invalidate an official submission.')
    if diagnostics['empty_semicolon_field_rows']:
        warnings.append('Empty semicolon fields are removed by the official metric; no CSV modification was made.')
    outsider=execution.get('outsider_observation',{})
    if outsider.get('original_OUTSIDERS_OK') and outsider.get('exact_combined_scores') is not True:
        warnings.append('Optional outsider ensemble did not produce independently verified exact three-way values; review source policy before submission.')
    return dict(status='passed' if all(checks.values()) else 'failed',target=TARGET,version=VERSION,
        checked_at_utc=datetime.now(timezone.utc).isoformat(),read_only=True,checks=checks,
        submission_sha256=csv_before,submission_rows=len(rows),downloaded_output_directory=str(input_dir.relative_to(ROOT)),
        notebook_sha256=run['notebook_sha256'],active_ids=sorted(active_ids),processed_molecules=len(active_ids),
        input_molecules=len(rows),placeholder_rows=len(rows)-len(active_ids),is_full_run=full,
        csv_identity_diagnostics=diagnostics,outsider_observation=outsider,warnings=warnings,
        local_sample_sha256=sha(SAMPLE),sample_order_evidence='Local official sample plus the version-bound runtime observer assertion against its actual SAMPLE_IDS.',
        competition_submission_performed=False,
        limits=['This is a private Save&Run output audit, not a competition hidden scoring rerun or Public Score.',
            'Inactive LOTUS-filled rows may contain multiple candidates; 388 exact CCO rows are not required.',
            'Optional outsider stages keep original budgets/fallback policy; observations are preserved without changing the CSV.',
            'All three neural models have official-train full refits; visible/development performance is not clean CV.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=DEFAULT_INPUT)
    parser.add_argument('--output',type=Path,default=DEFAULT_REPORT)
    args=parser.parse_args()
    for name,relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        path=ROOT/relative;path.mkdir(parents=True,exist_ok=True);os.environ[name]=str(path)
    try:
        destination=inside(args.output)
        if destination.exists():
            raise FileExistsError('Preserve prior audit reports; choose a new --output path')
        result=verify(args.input)
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(status=result['status'],target=TARGET,version=VERSION,
            checks_passed=sum(result['checks'].values()),checks_total=len(result['checks']),
            failed_checks=[name for name,value in result['checks'].items() if not value],
            submission_sha256=result['submission_sha256'],processed_molecules=result['processed_molecules'],
            duplicate_identity_rows=len(result['csv_identity_diagnostics']['duplicate_identity_rows']),warnings=result['warnings']),indent=2))
        return 0 if result['status']=='passed' else 1
    except Exception as error:
        print(json.dumps(dict(status='verification_stopped',error_type=type(error).__name__),indent=2));return 1


if __name__=='__main__':raise SystemExit(main())
