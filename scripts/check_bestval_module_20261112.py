"""Check changed Notebook cells and pinned mixing with actual saved CPU scorer output."""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_v80_variants_20261112 as builder


def main(frozen=False):
    import pandas as pd
    import numpy as np
    import rdkit
    mod=builder.module()
    module_pin=builder.sha(builder.MODULE)
    parent=builder.read(builder.BASE/'notebook.ipynb')
    source=ROOT/'runs/bestval_models_canary_20261112'
    output=ROOT/('runs/bestval_frozen_entry_20261112' if frozen else 'runs/bestval_module_canary_20261112_final1')
    output.mkdir(parents=True,exist_ok=False)
    pub=ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
    input_root=ROOT/'assets/kaggle'
    all_checks={}
    stage_pins={}
    examples={
        mod.PUB_PINS['final_model.pt']:source/'public_final.parquet',
        mod.V2_SHA:source/'v2_final.parquet',
        mod.SPECS['popwenman_best']['sha256']:source/'popwenman_best.parquet',
        mod.SPECS['saner_best']['sha256']:source/'saner_best.parquet'}
    sample_ids=pd.read_parquet(source/'evidence.parquet').molecule_id.astype(str).drop_duplicates().tolist()
    for name,kind in builder.BRANCHES.items():
        if frozen:
            stage=builder.OUT/name
            notebook=builder.read(stage/'notebook.ipynb')
            receipt=builder.read(stage/'prepare_receipt.json')
            assert builder.sha(stage/'notebook.ipynb')==receipt['notebook_sha256']
            assert module_pin==receipt['module_sha256']
            stage_pins[name]=receipt['notebook_sha256']
        else:
            notebook=builder.make_notebook(parent,name,kind,'f'*64,module_pin)
        for fast in (True,False):
            root=output/(name+('_fast' if fast else '_hidden'))
            root.mkdir();code=root/'code';code.mkdir();comp=root/'competition';comp.mkdir()
            sample=pd.DataFrame(dict(molecule_id=sample_ids,smiles=['C;CC;CCC']*len(sample_ids)))
            sample.to_csv(comp/'sample_submission.csv',index=False)
            read_ids=[];outside=[];consumed=[]
            namespace=dict(pd=pd,ROOT=root,CODE=code,COMP=comp,INPUT=input_root,IS_RERUN=not fast,
                COMMIT_MODE='fast',SAMPLE_IDS=sample_ids,RUN_PIPELINE=not fast,VARIANT='CUSTOM',
                MASS_ON=True,RR8=False,V8='MASS',MASS_CENTER=-1.5,MASS_W=.15,
                POP_W=.10,SPEC_W=.10,NP_W=.12,LIB_HIT_GATE=.78,
                MASS_REPORT=dict(status='on'),MASS_LEAD_REPORT=dict(status='ran'),RR8_REPORT=dict(status='off in this preset'))
            namespace['materialise_sources']=lambda:str(pub)
            def run_pipeline():
                if not fast:
                    (root/'execution_receipt.json').write_text(json.dumps(dict(is_full_run=True,processed_molecules=len(sample_ids))))
                return not fast
            namespace['run_public_pipeline']=run_pipeline
            def score():
                digest=builder.sha(Path(namespace['BUNDLE'])/'final_model.pt')
                read_ids.append(digest)
                shutil.copy2(examples[digest],root/'neural_candidate_features.parquet')
                return True
            namespace['score_final_lists']=score
            def outside_score(needed):
                outside.append(builder.sha(Path(namespace['BUNDLE'])/'final_model.pt'))
                return False
            namespace['score_outside_candidates']=outside_score
            def consensus():
                consumed.append(builder.sha(root/'neural_candidate_features.parquet'))
                sample.to_csv(root/'submission.csv',index=False)
                return True,{},[]
            namespace['build_consensus']=consensus
            namespace['choose_and_submit']=lambda:'CUSTOM'
            exec(compile(builder.source(notebook['cells'][14]),'actual_bestval_cell14','exec'),namespace)
            exec(compile(builder.source(notebook['cells'][29]),'actual_bestval_cell29','exec'),namespace)
            namespace['EXTERNAL_OVERLAY_AUDIT']=dict(status='passed',csv_sha256=builder.sha(root/'submission.csv'))
            exec(compile(builder.source(notebook['cells'][33]),'actual_bestval_cell33','exec'),namespace)
            audit=namespace['BESTVAL_ENSEMBLE_AUDIT']
            prefix=name+('_fast:' if fast else '_hidden:')
            all_checks[prefix+'module_installed_exact']=builder.sha(code/'v80_ensemble_20261112.py')==module_pin
            all_checks[prefix+'all_final_checks']=all(v is True for v in audit['checks'].values())
            all_checks[prefix+'base_observer']=namespace['BATCH_VARIANT_AUDIT']['status']=='passed'
            all_checks[prefix+'unchanged_other31_cells']=all(notebook['cells'][i]==parent['cells'][i] for i in range(33) if i not in (14,29))
            runtime=mod.read(root/mod.RUNTIME)
            if fast:
                all_checks[prefix+'no_models_run']=not read_ids and runtime['status']=='prepared'
            else:
                all_checks[prefix+'three_explicit_scorer_calls']=read_ids==[mod.PUB_PINS['final_model.pt'],mod.V2_SHA,mod.SPECS[kind]['sha256']]
                all_checks[prefix+'outsider_still_v2']=outside==[mod.V2_SHA]
                all_checks[prefix+'mixed_features_really_consumed']=consumed==[runtime['output_sha256']]
                # Independently reproduce the original per-query z calculation.
                raw=[pd.read_parquet(root/f).set_index(['molecule_id','smiles']) for f in ('neural_public.parquet','neural_ours.parquet','neural_bestval.parquet')]
                wanted=np.zeros(len(raw[0]),dtype=np.float64)
                for frame,w in zip(raw,mod.SPECS[kind]['weights']):
                    g=frame.neural_score.groupby(level=0)
                    z=(frame.neural_score-g.transform('mean'))/g.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)
                    wanted+=w*z.to_numpy()
                actual=pd.read_parquet(root/'neural_candidate_features.parquet').neural_score.to_numpy()
                all_checks[prefix+'independent_weight_formula']=bool(np.allclose(wanted,actual,rtol=0,atol=2e-7))
                changed=copy.deepcopy(runtime);changed['configuration']['checkpoint']['weights']=[1.,0.,0.]
                mod.write(root/mod.RUNTIME,changed)
                try:mod.audit_scores(root,True,kind)
                except ValueError:all_checks[prefix+'weight_tamper_rejected']=True
                else:all_checks[prefix+'weight_tamper_rejected']=False
                mod.write(root/mod.RUNTIME,runtime)
                old=pd.read_parquet(root/'neural_candidate_features.parquet')
                altered=old.copy();altered.loc[0,'neural_score']+=.125
                altered.to_parquet(root/'neural_candidate_features.parquet',index=False)
                try:mod.audit_scores(root,True,kind)
                except ValueError:all_checks[prefix+'output_tamper_rejected']=True
                else:all_checks[prefix+'output_tamper_rejected']=False
                old.to_parquet(root/'neural_candidate_features.parquet',index=False)
    assert all(v is True for v in all_checks.values()),[k for k,v in all_checks.items() if not v]
    report=dict(status='passed',module_sha256=module_pin,checks=all_checks,checks_total=len(all_checks),
                score_source='Actual original scorer CPU outputs from 3 queries/26 spectra/15 candidates',
                changed_cells_executed=[14,29,33],original31_cells_not_rerun=True,
                scorer_stage_canary_uses_saved_actual_scores=True,truth_read=False,quality_gain_claim=False,
                frozen_staged_sources=frozen,stage_sha256=stage_pins)
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    report_name='v80_bestval_frozen_entry.json' if frozen else 'v80_bestval_module_canary.json'
    (ROOT/'reports/optimization_20261112'/report_name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--frozen',action='store_true')
    main(parser.parse_args().frozen)
