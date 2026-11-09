
# Observation only. This cell never changes candidates, weights or submission.csv.
def _batch_variant_audit():
    checks={}
    expected=BATCH_RECIPE
    checks['recipe_sha256']=BATCH_RECIPE_SHA256=='92a6ad3d6133b13cb0789557bebefcac6dcb67bdf3824901e37d2b5878419423'
    checks['configuration_exact']=all(globals().get(name)==value for name,value in expected['config'].items())
    checks['public_input_pins']=BATCH_BUNDLE_AUDIT['public']['pins']==expected['public_pins']
    checks['all_native_models_staged']=set(BATCH_BUNDLE_AUDIT)==set(expected['weights'])
    checks['distinct_model_checkpoints']=len({entry['pins']['final_model.pt'] for entry in BATCH_BUNDLE_AUDIT.values()})==len(expected['weights'])
    checks['no_lotus_dependency']='lotus' not in ' '.join(expected['dataset_sources']).lower()
    checks['v56_original_priors']=POP_W==0.10 and SPEC_W==0.05 and NP_W==0.02 and LIB_HIT_GATE==0.87
    frame=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    checks['csv_columns']=list(frame.columns)==['molecule_id','smiles']
    checks['csv_ids']=frame.molecule_id.tolist()==SAMPLE_IDS and frame.molecule_id.is_unique
    checks['csv_nonempty_counts']=bool(frame.smiles.str.split(';').map(lambda guesses:1<=len(guesses)<=25 and all(guesses)).all())
    mode='full_runtime' if RUN_PIPELINE else 'fast_static'
    processed=0
    if not RUN_PIPELINE:
        checks['fast_mode_explicit']=COMMIT_MODE=='fast' and not IS_RERUN and not PIPELINE_DONE
        checks['no_runtime_claim']=BATCH_MAIN_ENSEMBLE_AUDIT is None and BATCH_OUTSIDER_ENSEMBLE_AUDIT is None
    else:
        receipt=json.loads((ROOT/'execution_receipt.json').read_text())
        processed=int(receipt['processed_molecules'])
        checks['pipeline_complete']=bool(PIPELINE_DONE and NEURAL_OK and CONSENSUS_OK)
        checks['main_runtime_ensemble']=BATCH_MAIN_ENSEMBLE_AUDIT.get('status')=='passed' and BATCH_MAIN_ENSEMBLE_AUDIT.get('combined_score_max_abs_difference')==0.0
        checks['main_combined_file_unchanged']=_batch_sha(ROOT/'neural_candidate_features.parquet')==BATCH_MAIN_ENSEMBLE_AUDIT['output_sha256']
        checks['main_runtime_weights']=BATCH_MAIN_ENSEMBLE_AUDIT['weights']==expected['weights']
        if IS_RERUN:
            checks['hidden_full_input']=receipt.get('is_full_run') is True and processed==len(SAMPLE_IDS)
            checks['hidden_400_rows']=len(frame)==400
        if OUTSIDERS_OK:
            checks['outsider_runtime_ensemble']=BATCH_OUTSIDER_ENSEMBLE_AUDIT is not None and BATCH_OUTSIDER_ENSEMBLE_AUDIT['status']=='passed'
        checks['final_layer_applied']=FINAL_REPORT.get('status')=='applied'
        checks['merge_applied']=MERGE_REPORT.get('status')=='applied'
    result=dict(status='passed' if all(checks.values()) else 'failed',mode=mode,branch=expected['branch'],
        target=expected['target'],version=1,recipe_sha256=BATCH_RECIPE_SHA256,checks=checks,
        config=expected['config'],expected_dataset_sources=expected['dataset_sources'],model_bundles=BATCH_BUNDLE_AUDIT,
        main_ensemble=BATCH_MAIN_ENSEMBLE_AUDIT,outsider_ensemble=BATCH_OUTSIDER_ENSEMBLE_AUDIT,
        processed_molecules=processed,submission_rows=len(frame),submission_sha256=_batch_sha(ROOT/'submission.csv'),
        fast_static_only=not RUN_PIPELINE,hidden_score_proven=False,scoring_changes=expected['algorithm_changes'])
    (ROOT/'batch_variant_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['status']=='passed', 'Variant audit failed: '+','.join(k for k,v in checks.items() if not v)
    return result

BATCH_VARIANT_AUDIT=_batch_variant_audit()
print('BATCH_VARIANT_AUDIT',BATCH_VARIANT_AUDIT['mode'],BATCH_VARIANT_AUDIT['branch'],BATCH_VARIANT_AUDIT['status'],flush=True)
