"""Execute the frozen combined fast entry and check cross-component bindings."""
from pathlib import Path
import hashlib
import json
import resource
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_v80_variants_20261112 as builder


def main():
    import pandas as pd
    stage=ROOT/'submission/optimization_20261112/bestval_v80_adduct'
    nb=builder.read(stage/'notebook.ipynb');receipt=builder.read(stage/'prepare_receipt.json')
    pin=builder.sha(stage/'notebook.ipynb')
    assert pin==receipt['notebook_sha256']
    root=ROOT/'runs/bestval_adduct_combo_canary_20261112'
    root.mkdir(parents=True,exist_ok=False);code=root/'code';code.mkdir();inp=root/'input';inp.mkdir()
    comp=inp/'enveda-CASMI26-molecule-id-mass-spectra';comp.mkdir()
    actual=ROOT/'runs/bestval_models_canary_20261112'
    ids=pd.read_parquet(actual/'evidence.parquet').molecule_id.astype(str).drop_duplicates().tolist()
    pd.DataFrame(dict(molecule_id=ids,smiles=['C;CC;CCC']*len(ids))).to_csv(comp/'sample_submission.csv',index=False)
    shutil.copy2(actual/'queries.parquet',comp/'test.parquet')
    pub=ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
    linked=[
        ('casmi26-scorer-v2-model/final_model.pt','assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1/final_model.pt'),
        ('casmi26-scorer-train-v80/casmi_spectrum_model_ours_v80/best_validation_model.pt','assets/kaggle/popwenman/casmi26-scorer-train-v80/v1/casmi_spectrum_model_ours_v80/best_validation_model.pt'),
        ('casmi26-lotus-candidates/candidates_lotus.parquet','assets/kaggle/qwertykeypadapple/casmi26-lotus-candidates/v2/candidates_lotus.parquet')]
    original_recipe=builder.read(builder.BASE/'recipe.json')
    for item in original_recipe['files']:
        linked.append((item['ref'].split('/')[1]+'/'+item['file'],
                       'assets/kaggle/'+item['ref']+'/v'+str(item['version'])+'/'+item['file']))
    for destination,source in linked:
        dest=inp/destination;dest.parent.mkdir(parents=True,exist_ok=True);dest.hardlink_to(ROOT/source)
    ns=dict(pd=pd,ROOT=root,CODE=code,INPUT=inp,COMP=comp,IS_RERUN=False,COMMIT_MODE='fast',SAMPLE_IDS=ids,
        RUN_PIPELINE=False,VARIANT='CUSTOM',V8='MASS',MASS_ON=True,RR8=False,MASS_CENTER=-1.5,MASS_W=.15,
        POP_W=.10,SPEC_W=.10,NP_W=.12,LIB_HIT_GATE=.78,MASS_REPORT=dict(status='off'),MASS_LEAD_REPORT=dict(status='off'),
        RR8_REPORT=dict(status='off in this preset'))
    ns['materialise_sources']=lambda:str(pub)
    ns['run_public_pipeline']=lambda:False
    exec(compile(builder.source(nb['cells'][14]),'frozen_combo_cell14','exec'),ns)
    exec(compile(builder.source(nb['cells'][29]),'frozen_combo_cell29','exec'),ns)
    ns['GUARDED_TAIL_AUDIT']=dict(status='passed',csv_sha256=builder.sha(root/'submission.csv'))
    exec(compile(builder.source(nb['cells'][32]),'frozen_combo_cell32_actual_adduct_fast','exec'),ns)
    exec(compile(builder.source(nb['cells'][33]),'frozen_combo_cell33','exec'),ns)
    runtime=builder.read(root/'bestval_ensemble_runtime.json')
    audit=ns['BESTVAL_ENSEMBLE_AUDIT'];adduct=ns['ADDUCT_OVERLAY_AUDIT'];base=ns['BATCH_VARIANT_AUDIT']
    parent=builder.read(builder.BASE/'notebook.ipynb')
    adduct_nb=builder.read(ROOT/'submission/optimization_20261112/adduct_extlib/notebook.ipynb')
    checks=dict(frozen_source_pin=pin==receipt['notebook_sha256'],
        unchanged_other30_original_cells=all(nb['cells'][i]==parent['cells'][i] for i in range(33) if i not in (14,29,32)),
        exact_adduct_cell32=nb['cells'][32]==adduct_nb['cells'][32],
        explicit_branch_in_prepare=runtime['branch']==receipt['branch'],
        prepare_recipe_bound=runtime['recipe_sha256']==receipt['recipe_sha256'],
        base_recipe_bound=base['branch']==receipt['branch'] and base['recipe_sha256']==receipt['recipe_sha256'],
        final_recipe_bound=audit['branch']==receipt['branch'] and audit['recipe_sha256']==receipt['recipe_sha256'],
        fixed_pop_bestval_configuration=runtime['configuration']==builder.module().config('popwenman_best'),
        actual_adduct_fast_audit=adduct['status']=='passed' and all(v is True for v in adduct['checks'].values()),
        adduct_and_bestval_same_final_csv=audit['csv_sha256']==adduct['csv_sha256']==builder.sha(root/'submission.csv'),
        all_bestval_final_checks=all(v is True for v in audit['checks'].values()),
        no_model_scoring_on_fast=runtime['status']=='prepared')
    original=(root/'submission.csv').read_bytes()
    def rejected(label,changed_audit=None,csv=None):
        (root/'submission.csv').write_bytes(csv if csv is not None else original)
        ns['ADDUCT_OVERLAY_AUDIT']=changed_audit if changed_audit is not None else adduct
        try:exec(compile(builder.source(nb['cells'][33]),'frozen_combo_bad_'+label,'exec'),ns)
        except ValueError:
            checks[label+'_rejected']=True
            checks[label+'_removed_final_preserved_control']=not (root/'submission.csv').exists() and (root/'submission_bestval_observer_control.csv').exists()
        else:checks[label+'_rejected']=False
    rejected('bad_adduct_status',dict(adduct,status='failed'))
    rejected('bad_adduct_output_binding',dict(adduct,csv_sha256='0'*64))
    rejected('changed_final_csv',csv=original.replace(b'CCO',b'CCN',1))
    (root/'submission.csv').write_bytes(original);ns['ADDUCT_OVERLAY_AUDIT']=adduct
    exec(compile(builder.source(nb['cells'][33]),'frozen_combo_restored','exec'),ns)
    checks['restored_good_entry_passed']=ns['BESTVAL_ENSEMBLE_AUDIT']['status']=='passed'
    checks['frozen_source_unchanged']=builder.sha(stage/'notebook.ipynb')==pin
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    checks['memory_under_400mib']=peak<400*1024
    assert all(v is True for v in checks.values()),[k for k,v in checks.items() if not v]
    record=dict(status='passed',notebook_sha256=pin,recipe_sha256=receipt['recipe_sha256'],checks=checks,
        checks_total=len(checks),peak_rss_kib=peak,changed_frozen_cells_executed=[14,29,32,33],
        actual_adduct_fast_path=True,no_new_model_scoring=True,no_new_full_library_matching=True,
        original30_cells_not_rerun=True,quality_gain_claim=False)
    (root/'verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (ROOT/'reports/optimization_20261112/combo_stage_canary.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
