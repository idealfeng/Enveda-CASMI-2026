"""Offline audit of selectively downloaded, version-bound V2 outputs. No API calls."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import ast
import csv
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
TARGET='stormseye/casmi26-flex-v56-baseline'
EXPECTED_SOURCE='0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769'
OUTPUT=ROOT/'reports/kaggle_baseline_v2_output_independent_recheck_20261105.json'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'runs/kaggle_baseline_v2_outputs_20261105b')
    args=parser.parse_args();folder=args.input.resolve()
    if not folder.is_relative_to(ROOT):parser.error('Input must stay inside D: workspace')
    checks={};details={};errors=[];downloaded=[];submission_sha=None
    try:
        receipt=read(folder/'download_receipt.json');binding=read(folder/'source_binding.json')
        downloaded=receipt.get('downloaded_files',[])
        checks['version_bound_complete_download']=receipt.get('status')=='downloaded' and receipt.get('target')==TARGET and receipt.get('version')==2 and not receipt.get('missing_required') and receipt.get('session_status')=='COMPLETE'
        checks['private_offline_v2_original_source']=binding.get('target')==TARGET and binding.get('version')==2 and binding.get('version_label_requested')=='v2' and binding.get('private') is True and binding.get('internet') is False and binding.get('original_sha256')==EXPECTED_SOURCE and binding.get('cell_semantics_equal') is True
        file_checks=[]
        for item in downloaded:
            path=(ROOT/str(item['path']).replace('\\','/')).resolve()
            file_checks.append(path.is_relative_to(folder) and path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256'])
        checks['downloaded_small_files_sha_bound']=bool(file_checks) and all(file_checks)
        final=folder/'submission.csv';submission_sha=sha(final)
        with final.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream);columns=reader.fieldnames;rows=list(reader)
        with (ROOT/'enveda-CASMI26-molecule-id-mass-spectra/sample_submission.csv').open(encoding='utf-8-sig',newline='') as stream:
            ids=[item['molecule_id'] for item in csv.DictReader(stream)]
        checks['visible_csv_400_ids_order_and_shape']=columns==['molecule_id','smiles'] and len(rows)==400 and len({x['molecule_id'] for x in rows})==400 and [x['molecule_id'] for x in rows]==ids and all(1<=len(x['smiles'].split(';'))<=25 and all(s.strip() for s in x['smiles'].split(';')) and len(set(x['smiles'].split(';')))==len(x['smiles'].split(';')) for x in rows)
        csv_audit=read(ROOT/'reports/kaggle_baseline_v2_independent_csv_checks_20261105.json')
        checks['official_rdkit_csv_audit_same_bytes']=csv_audit.get('status')=='passed' and csv_audit.get('rdkit')=='2026.03.3' and csv_audit.get('submission_sha256')==submission_sha and all(csv_audit.get('checks',{}).values())
        base=read(folder/'e004_verification.json');inner=read(folder/'v43_execution_receipt.json');execution=read(folder/'execution_receipt.json');manifest=read(folder/'run_manifest.json')
        processed=set(base.get('processed_ids',[]));by_id={x['molecule_id']:x['smiles'] for x in rows}
        checks['actual_smoke12_padding388']=base.get('processed_molecules')==12 and base.get('input_molecules')==400 and base.get('placeholder_fill_rows')==388 and base.get('is_full_run') is False and len(processed)==12 and processed==set(sorted(ids)[:12]) and all(by_id[mid]=='CCO' for mid in set(ids)-processed) and inner.get('processed_molecules')==12 and inner.get('placeholder_rows')==388 and inner.get('scoring_rerun') is False
        checks['both_retrieval_engines_and_base_clean']=base.get('base_errors')==0 and all(base.get(k)==12 for k in ('base_nonempty','engine2_nonempty','pubchem_nonempty')) and inner.get('main_errors')==0 and all(inner.get(k)==12 for k in ('main_lists','engine2_lists','pubchem_lists','engine2_nonempty','pubchem_nonempty')) and manifest.get('n_errors')==0
        values={}
        nb=json.loads((ROOT/'third_party/flexonafft_evidence_gap/v56/original.ipynb').read_text(encoding='utf-8'))
        for cell in nb['cells']:
            if cell.get('cell_type')!='code':continue
            text=''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
            for node in ast.parse(text).body:
                if isinstance(node,ast.Assign):
                    for target in node.targets:
                        if isinstance(target,ast.Name) and target.id in ('FROZEN_SHA256','MODEL_PINS','MODULES','VARIANT'):
                            values[target.id]=ast.literal_eval(node.value)
                        elif (isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name)
                              and target.value.id=='MODULES' and isinstance(target.slice,ast.Constant)):
                            values.setdefault('MODULES',{})[target.slice.value]=ast.literal_eval(node.value)
        checks['frozen_execution_source_not_stale_version_label']=execution.get('source_sha256')==values['FROZEN_SHA256'] and execution.get('source_adaptations')==[] and execution.get('processed_molecules')==12 and execution.get('is_full_run') is False
        stages={}
        for name in ('ice','gl','n1'):
            stage=read(folder/f'{name}_work/{name}_out.json.meta.json');stages[name]=stage
            good=stage.get('status')=='ok' and stage.get('errors')==[] and stage.get('n_pred_fail')==0 and stage.get('n_feat_fail',0)==0 and stage.get('n_bad_smiles',0)==0 and str(stage.get('device','')).startswith('cuda') and stage.get('rdkit')=='2025.03.6'
            good=good and (stage.get('n_mols_done')==stage.get('n_mols') and stage.get('n_mols_done',0)>0 and stage.get('fake') is False if name=='n1' else stage.get('n_mols_scored')==stage.get('n_mols_covered') and stage.get('n_mols_scored',0)>0 and stage.get('n_scored',0)>0)
            checks[name+'_actual_model_meta_complete']=bool(good)
        consensus=read(folder/'variants/consensus_report.json');neural=read(folder/'neural_submission_report.json')
        checks['neural_and_outsider_errors_empty']=read(folder/'neural_candidate_features.parquet.errors.json')==[] and read(folder/'outsider_neural_features.parquet.errors.json')==[]
        checks['neural_all12_active']=values['VARIANT']=='CUSTOM' and consensus.get('CUSTOM',{}).get('active_rows')==12 and neural.get('candidate_set_preserved') is True and neural.get('rows')==400
        pins=values['MODEL_PINS'];bundle=values['MODULES']['bundle.py']
        assets=read(ROOT/'submission/flex_v56_review/local_asset_manifest.json');local_saner={Path(x['file']).name:x['recorded_sha256'] for x in assets if x['dataset']=='sanpier/casmi-spectrum-model-v1'}
        checks['saner_mandatory_pins_guard_and_completed_score']=all(local_saner.get(k)==v for k,v in pins.items()) and "sha(r/n)==h" in bundle and "assert len(matching)==1" in bundle and checks['neural_all12_active'] and checks['neural_and_outsider_errors_empty']
        physical=read(folder/'spectral_parallax_report.json');merge=read(folder/'merge_report.json');layer=read(folder/'final_layer_report.json')
        checks['physical_no_budget_or_restore']=bool(physical.get('submission_sha256')) and not any(physical.get(k) for k in ('error','control_restored','time_budget_exceeded')) and 'skip' not in str(physical.get('status','')).lower()
        checks['merge_and_final_applied']=merge.get('status')=='applied' and layer.get('status')=='applied' and merge.get('rows')==400 and layer.get('rows')==400 and not any(merge.get(k) or layer.get(k) for k in ('exception','restore_error','control_restored'))
        checks['physical_merge_final_sha_chain']=physical.get('submission_sha256')==merge.get('input_sha256',{}).get('physical_v2') and merge.get('output_sha256')==layer.get('input_sha256') and layer.get('output_sha256')==submission_sha
        log_checks=read(folder/'kernel_session_log_checks.json')
        bad=sum(log_checks.get('failure_marker_counts',{}).values())+sum(log_checks.get('neural_input_failure_counts',[]))
        for name in ('submission_pipeline.log','submission_neural.log','outsiders_neural.log','bootstrap.log'):
            path=folder/name
            if path.is_file():
                text=path.read_text(encoding='utf-8',errors='replace')
                bad+=sum(text.count(token) for token in ('Traceback (most recent call last)','FAILED ->','restored_after_error','NEURAL FAILED'))
                bad+=sum(int(v) for v in re.findall(r'NEURAL input failures kept at baseline:\s*(\d+)',text))
        checks['no_whole_stage_error_or_neural_fallback_markers']=bad==0
        alignment=read(ROOT/'reports/kaggle_baseline_v2_asset_alignment_20261105.json')
        checks['five_dataset_inventory_content_alignment']=alignment.get('status')=='passed_for_inventory_scope' and alignment.get('target')==TARGET and alignment.get('version')==2 and alignment.get('mismatches')==[]
        details=dict(visible_input_rows=400,actually_inferred_molecules=12,padded_cco_rows=388,
            hidden_inference_proven=False,hidden_score_claimed=False,stage_health={name:{k:v.get(k) for k in ('status','n_mols','n_mols_done','n_mols_covered','n_mols_scored','n_scored','errors','n_pred_fail','fake')} for name,v in stages.items()},
            stale_manifest_health_strings={k:manifest.get(k) for k in ('ice_health','gl_health')},
            manifest_health_interpretation='Use actual complete CUDA model metadata; original health strings are stale, not evidence that the models were skipped.',
            source_labels_interpretation='V80/V49 internal labels are ancestor labels; actual notebook identity is typedGetKernel V2 plus original code-cell semantics.',
            saner_required_model_pins=pins,saner_proof='Unchanged source mandatory full-SHA find_bundle guard plus completed all12 neural scoring; not an independent cloud model-file download.',
            asset_scope=alignment.get('counts'),saner_readme_independent_runtime_hash_verified=False)
    except BaseException as error:
        errors.append(dict(error_type=type(error).__name__))
    report=dict(target=TARGET,version=2,status='passed' if checks and all(checks.values()) and not errors else 'failed',
        checked_at_utc=datetime.now(timezone.utc).isoformat(),submission_sha256=submission_sha,
        checks=checks,downloaded_files=downloaded,details=details,errors=errors,input_dir=str(folder),
        scope='Visible-cloud source/runtime smoke audit: 12 actual molecules +388 CCO padding, not 400 hidden inferences or a competition score.',
        competition_submission_performed=False,network_called_by_verifier=False,
        limitations=['Content alignment is distinct from independently exposed numeric dataset-version IDs.',
            '42 large files use size+head/tail comparison, not a complete-file cloud hash proof.',
            'Saner model pins are proved through mandatory unchanged guard and successful scoring; its README is outside the five-dataset inventory.',
            'Successful visible smoke does not prove the complete hidden-input path or hidden-run time budget.'])
    OUTPUT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    OUTPUT.with_suffix('.md').write_text('# Kaggle V2 visible-output audit\n\nStatus: **'+report['status']+'**. Target: '+TARGET+'/2.\n\n'+report['scope']+'\n\nSubmission SHA256: `'+str(submission_sha)+'`.\n\n'+ '\n'.join('- '+key+': '+str(value) for key,value in checks.items())+'\n\nSee JSON for model metadata, source pins, stale-health explanation and evidence limits. No network, run, push or submission was performed by this verifier.\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('status','target','version','submission_sha256','checks','errors')},indent=2))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
