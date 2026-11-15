"""Independent read-only review of the generation stage; never launches a model."""
from pathlib import Path
import ast
import base64
import csv
import hashlib
import json
import zlib

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'submission/optimization_20261113/generation_production'
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
RUN=ROOT/'runs/generation_production_20261113_r2'
OUT=ROOT/'reports/optimization_20261113/evidence_generation_review.json'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def src(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def digest(v):return hashlib.sha256(v).hexdigest()
def sha(p):return digest(Path(p).read_bytes())
def assignment(source,name):
    return next(n.value for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
def compressed_assignment(source,name):
    value=assignment(source,name)
    if isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute) and value.func.attr=='decode':
        value=value.func.value
    return zlib.decompress(base64.b64decode(ast.literal_eval(value.args[0].args[0])))

def main():
    b=read(BASE/'notebook.ipynb');s=read(STAGE/'notebook.ipynb');recipe=read(STAGE/'recipe.json')
    spec=read(STAGE/'branch_spec.json');prep=read(RUN/'preparation.json')
    changes=[i for i,(x,y) in enumerate(zip(b['cells'],s['cells'])) if x!=y]
    original_bundle=compressed_assignment(src(b['cells'][11]),'_guarded_source').decode()
    modules={}
    for n in ast.parse(original_bundle).body:
        if isinstance(n,ast.Assign):
            for t in n.targets:
                if isinstance(t,ast.Subscript) and isinstance(t.value,ast.Name) and t.value.id=='MODULES':
                    modules[ast.literal_eval(t.slice)]=ast.literal_eval(n.value)
    original_runner=modules['runner.py']
    stage12=src(s['cells'][12]);runner=compressed_assignment(stage12,'_gen_runner_text').decode()
    module=compressed_assignment(stage12,'_gen_raw')
    wanted='from generation_runtime_patch_20261112 import after_cell, finish\n'+original_runner
    needle="        exec(compile(''.join(c['source']),f'pipeline_cell_{i}','exec'),scope)"
    wanted=wanted.replace(needle,needle+'\n        after_cell(scope,i,root)')
    wanted=wanted.replace('    export(scope,root)','    export(scope,root)\n    finish(scope,root)')
    runtime=module.decode();pins=ast.literal_eval(assignment(runtime,'SOURCE_PINS'))
    assets=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-v4b-models/code'
    engine=(assets/'casmi/engine.py').read_bytes()
    old=b'ad = max(set(adducts), key=adducts.count)';new=b'ad = max(adducts, key=adducts.count)'
    assert engine.count(old)==1
    actual=dict(engine=digest(engine.replace(old,new,1)),derive=sha(assets/'casmi/derive.py'),
                hooks_v1=sha(assets/'fe_v4/hooks_v1.py'),v1engine=sha(assets/'fe_v4/v1engine.py'))
    bm=read(BASE/'kernel-metadata.json');sm=read(STAGE/'kernel-metadata.json')
    static=dict(parent_sha=sha(BASE/'notebook.ipynb')==recipe['champion_notebook_sha256'],
        stage_sha=sha(STAGE/'notebook.ipynb')==spec['notebook_sha256']==prep['stage_notebook_sha256'],
        metadata_sha=sha(STAGE/'kernel-metadata.json')==spec['metadata_sha256'],
        only_original_cell12_changed=changes==[12],original_cell12_is_prefix=stage12.startswith(src(b['cells'][12])),
        one_appended_audit_cell=len(s['cells'])==len(b['cells'])+1,
        embedded_frozen_cell11_unchanged=s['cells'][11]==b['cells'][11],
        all_original_cells13_to32_unchanged=s['cells'][13:33]==b['cells'][13:33],
        original_head_AB_cells_retained=s['cells'][30:33]==b['cells'][30:33],
        original_runner_sha=digest(original_runner.encode())==recipe['original_runner_sha256'],
        runner_only_aftercell_and_finish_hook=runner==wanted,
        runner_sha=digest(runner.encode())==recipe['runner_sha256'],
        module_payload_sha=digest(module)==recipe['module_sha256'],
        module_equals_local=module==(ROOT/recipe['local_module_source']).read_bytes(),
        exact_post_frozen27_source_pins=actual==pins,
        dataset_versions_unchanged=bm['dataset_sources']==sm['dataset_sources'],
        competition_versions_unchanged=bm['competition_sources']==sm['competition_sources'],
        private_gpu_offline=sm['is_private'] and sm['enable_gpu'] and not sm['enable_internet'],
        stage_all_code_compiles=all(compile(src(c),'review_only','exec') is not None for c in s['cells'] if c['cell_type']=='code'))
    # Runtime success depends on the real runner's completed receipt and actual
    # hidden_full artifacts. Static checks never substitute for that path.
    work=RUN/'kaggle/working';vr=RUN/'verification.json';failure=RUN/'failure.json'
    runtime_report=dict(status='pending',full_run_log_sha256=sha(RUN/'full_run.log'),
        preparation_sha256=sha(RUN/'preparation.json'),failure_present=failure.exists(),
        verification_present=vr.exists())
    if vr.exists():
        v=read(vr);names=['batch_variant_audit.json','guarded_tail_audit.json','external_overlay_audit.json','generation_variant_audit.json']
        audits={n:read(work/n) for n in names}
        runtime_report.update(status=v['status'],verification_sha256=sha(vr),
            exact_stage=v['stage_notebook_sha256']==spec['notebook_sha256'],
            all_outer_code_cells=[m['cell'] for m in v['marks']]==[i for i,c in enumerate(s['cells']) if c['cell_type']=='code'],
            all_audits_actual_hidden_full=all(a['mode']=='hidden_full' and a['status']=='passed' and bool(a['checks']) and all(a['checks'].values()) for a in audits.values()),
            output_bound=sha(work/'submission.csv')==v['output_sha256'],
            audit_sha256={n:sha(work/n) for n in names})
        with (work/'submission.csv').open(encoding='utf-8',newline='') as f:
            reader=csv.DictReader(f);columns=reader.fieldnames;output=list(reader)
        with (RUN/'kaggle/input/enveda-CASMI26-molecule-id-mass-spectra/sample_submission.csv').open(encoding='utf-8',newline='') as f:
            sample=list(csv.DictReader(f))
        generation=read(work/'generation_runtime.json')
        execution=read(work/'execution_receipt.json')
        v43=read(work/'v43_execution_receipt.json')
        ice_meta=read(work/'ice_work/ice_out.json.meta.json')
        gl_meta=read(work/'gl_work/gl_out.json.meta.json')
        expected_ids=[r['molecule_id'] for r in sample]
        code=work/'p2s_code'
        health=dict(actual_csv_columns=columns==['molecule_id','smiles'],
            actual_csv_ids=[r['molecule_id'] for r in output]==expected_ids,
            two_unique_ids=len(output)==len({r['molecule_id'] for r in output})==2,
            exactly25_nonempty_unique_candidates=all(len(r['smiles'].split(';'))==25 and len(set(r['smiles'].split(';')))==25 and all(r['smiles'].split(';')) for r in output),
            installed_engine_pin=sha(work/'v43_v4code/casmi/engine.py')==pins['engine'],
            runtime_installed_source_pins=generation['installed_source_pins']==pins,
            embedded_actual_module=sha(code/'generation_runtime_patch_20261112.py')==recipe['module_sha256'],
            embedded_actual_runner=sha(code/'generation_runner.py')==recipe['runner_sha256'],
            actual_frozen_sha=sha(code/'frozen_0465.ipynb')==execution['source_sha256']=='d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88',
            executed_real_submission_path=execution['mode']=='submission' and execution['is_full_run'] and execution['source_adaptations']==[] and execution['processed_molecules']==2,
            actual_engine2_pubchem_lists=v43['engine2_nonempty']==v43['pubchem_nonempty']==v43['main_lists']==2,
            no_main_errors=v43['main_errors']==v43['placeholder_rows']==0,
            exact_generation_configuration=generation['configuration']==recipe['configuration'],
            actual_rank_features=len(generation['selected_ranker_features'])==len(set(generation['selected_ranker_features']))==160 and all(r['rank_called'] and r['ranker_feature_count']==160 and r['n_features']==252 and r['observed_generated']==r['n_generated'] for r in generation['rows']),
            finite_complete_ice=ice_meta['status']=='ok' and ice_meta['n_mols_scored']==ice_meta['n_mols_covered']==2 and ice_meta['n_cands']==ice_meta['n_scored']==136 and ice_meta['n_pred_fail']==0 and not ice_meta['errors'],
            finite_complete_gl=gl_meta['status']=='ok' and gl_meta['n_mols_scored']==gl_meta['n_mols_covered']==2 and gl_meta['n_cands']==gl_meta['n_scored']==136 and gl_meta['n_pred_fail']==gl_meta['n_feat_fail']==0 and not gl_meta['errors'],
            neural_errors_empty=all(read(work/n)==[] for n in ['neural_candidate_features.parquet.errors.json','outsider_neural_features.parquet.errors.json','guarded_tail_scores.parquet.errors.json']),
            both_original_AB_sources=audits['external_overlay_audit.json']['reference_counts']==dict(A=200724,B=124160))
        runtime_report.update(production_health=health,rows=len(output),candidates=sum(len(r['smiles'].split(';')) for r in output),
            generated_candidates=sum(r['n_generated'] for r in generation['rows']),
            generated_candidates_in_actual_engine25=sum(r['engine_top25_generated'] for r in generation['rows']),
            generated_candidates_in_final25=audits['generation_variant_audit.json']['generated_raw_smiles_in_final25'],
            generation_queries=[dict(molecule_id=r['molecule_id'],parents=r['parents_used'],generated=r['n_generated'],actual_ranker_features=r['ranker_feature_count']) for r in generation['rows']],
            stale_log_banner_note='CLAW STAGE HEALTH says NOT RUN, but actual ICE/GL meta, score files and V43 receipt prove successful 2/2 scoring; banner is not the health source.',
            expected_inactive_scopes=['N1 proxy has no eligible queries in this H+ subset; no proxy coverage claim.',
                'AB actually loads and matches both libraries but finds zero hits in this subset; promotion branch not exercised.'],
            source_label_audit=dict(status='manual_source_review_no_query_label_reads_found',
                truth_metadata_present=True,clean_validation=False,no_efficacy_claim=True,
                review_boundary='Source review, not runtime field-access instrumentation. Full query frame and its labels are exported, but reviewed prediction inputs use spectral fields and candidate structures only.',
                reviewed_prediction_consumers=['FROZEN39 V1FE spectra construction; FROZEN41 GL/ICE item construction',
                    'Actual eng/casmi_engine.py compute_channels', 'Actual pc_runner.py spectra construction',
                    'p2s_code/neural_scores.py score: query spectrum encoder versus candidate-frame smiles',
                    'guarded_head_tail.py run and learned_head_score.py score',
                    'alex_v12_external_function.py query parsing; external matching uses reference structures'],
                query_fields=['molecule_id','ms2_mzs','ms2_normalized_intensities','precursor_mz','adduct','ionization_mode','instrument_type','collision_energy_ev'],
                label_fields_not_used_as_query_features=['normalized_smiles','inchikey','inchikey14','molecular_formula','official_identity'],
                export_note='export_evidence.py writes scope te with the extra columns unchanged to effective_query_spectra.parquet. This persistence is why no_truth_loaded is false.',
                provenance_correction='Original verification.json limitation says unlabelled incorrectly. input_schema_review.json and preparation.json retract that claim; this independent report uses labelled metadata present, deployment smoke only.',
                input_schema_review_sha256=sha(RUN/'input_schema_review.json')))
    report=dict(status='pending_real_full_path',static_checks=static,
        notebook_sha256=sha(STAGE/'notebook.ipynb'),recipe_sha256=sha(STAGE/'recipe.json'),
        source_pins=actual,original_cell_count=len(b['cells']),original_cell_changes=changes,real_execution=runtime_report,
        scope='Read-only independent audit; two-query local production subset with unused truth metadata present. No efficacy or clean-validation claim.',
        no_model_or_library_launched=True)
    if not all(static.values()):report['status']='failed_static'
    elif failure.exists():report['status']='failed_runtime'
    elif vr.exists() and v['status']=='passed_real_production_subset' and all(runtime_report.get(k) for k in ('exact_stage','all_outer_code_cells','all_audits_actual_hidden_full','output_bound')) and all(runtime_report['production_health'].values()):
        report['status']='passed_real_production_subset_release_recommended'
        report['release_recommendation']='Release this unchanged frozen stage for one Kaggle submission. This closes the previous source-pin/runtime-path failure on the tested subset; full hidden coverage, resource budget and score gain remain unproven.'
        report['remaining_constraints']=['Only 2 queries / 20 spectra on local RTX4060, not full Kaggle hidden test or T4 runtime validation.',
            'No same-run default-generation control, so 308 generated candidates and 14 final candidates do not measure incremental coverage or score gain.',
            'Both AB libraries and heads executed; this subset has zero AB hits, so actual promotion branch was not exercised.',
            'Input includes unused truth metadata. Treat only as production execution-path smoke, never clean CV.',
            'Do not select future methods from these two known-answer queries.']
    OUT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
