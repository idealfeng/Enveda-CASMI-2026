
# Observe the public recipe without changing its scoring or optional stages.
def _batch_public_mass_audit():
    import hashlib,json
    from pathlib import Path
    import numpy as np
    import pandas as pd
    import rdkit
    expected={'branch': 'public_mass_repro', 'recipe_sha256': '6e888687eb7d901c3cb2899a9b37cd10c4bd6c2de423670ced5ee31dec923149', 'public_pins': {'features.py': 'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455', 'model.py': '2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39', 'config.json': '563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03', 'final_model.pt': '44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}, 'v2_sha': 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46', 'lotus_sha': '7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f'}
    checks={}
    def check(name,value):
        checks[name]=bool(value)
        assert value,name
    def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    check('mass_recipe',V8=='MASS' and MASS_ON and RR8 is False and MASS_CENTER==-1.5 and MASS_W==0.15)
    check('original_public_priors',POP_W==0.10 and SPEC_W==0.10 and NP_W==0.12 and LIB_HIT_GATE==0.78)
    check('official_rdkit',rdkit.__version__=='2026.03.3')
    pub={name:digest(Path(PUB_BUNDLE)/name) for name in expected['public_pins']}
    ours={name:digest(Path(OURS_BUNDLE)/name) for name in expected['public_pins']}
    check('public_model_pins',pub==expected['public_pins'])
    wanted=dict(expected['public_pins']);wanted['final_model.pt']=expected['v2_sha']
    check('ours_model_pins',ours==wanted)
    check('two_distinct_models',pub['final_model.pt']!=ours['final_model.pt'])
    lotus=[p for p in INPUT.rglob('candidates_lotus.parquet') if 'casmi26-lotus-candidates' in p.parts]
    check('lotus_pin',len(lotus)==1 and digest(lotus[0])==expected['lotus_sha'])
    sub=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('csv_schema_ids',list(sub.columns)==['molecule_id','smiles'] and sub.molecule_id.tolist()==SAMPLE_IDS and sub.molecule_id.is_unique)
    check('csv_counts',sub.smiles.str.split(';').map(lambda g:1<=len(g)<=25 and all(g)).all())
    if IS_RERUN:
        check('pipeline_complete',PIPELINE_DONE and NEURAL_OK and CONSENSUS_OK and SUBMITTED==VARIANT)
        receipt=json.loads((ROOT/'execution_receipt.json').read_text())
        check('hidden_full_scope',receipt.get('is_full_run') is True and receipt.get('processed_molecules')==len(SAMPLE_IDS)==400)
        check('mass_layer_executed',MASS_REPORT.get('status')=='on' and MASS_LEAD_REPORT.get('status')=='ran')
        check('rr_disabled',RR8_REPORT.get('status')=='off in this preset')
        a=pd.read_parquet(ROOT/'neural_public.parquet').set_index(['molecule_id','smiles'])
        b=pd.read_parquet(ROOT/'neural_ours.parquet').set_index(['molecule_id','smiles'])
        c=pd.read_parquet(ROOT/'neural_candidate_features.parquet').set_index(['molecule_id','smiles'])
        check('ensemble_candidate_keys',a.index.is_unique and b.index.is_unique and c.index.is_unique and set(a.index)==set(b.index)==set(c.index))
        b,c=b.reindex(a.index),c.reindex(a.index)
        def z(series):
            group=series.groupby(level=0)
            return (series-group.transform('mean'))/group.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)
        values=.5*z(a.neural_score.fillna(0.0))+.5*z(b.neural_score.fillna(0.0))
        check('exact_dual_scores',np.array_equal(values.to_numpy(),c.neural_score.to_numpy()))
        check('model_coverage_equal',a.neural_ok.astype(bool).equals(b.neural_ok.astype(bool)))
        check('usable_scores_finite',np.isfinite(c.loc[c.neural_ok.astype(bool),'neural_score']).all())
    else:
        check('fast_no_model',not RUN_PIPELINE and not PIPELINE_DONE)
    result=dict(status='passed',branch=expected['branch'],mode='hidden_full' if IS_RERUN else 'fast_static',
        recipe_sha256=expected['recipe_sha256'],checks=checks,
        visible_model_executed=bool(RUN_PIPELINE),pins=dict(public=pub,ours=ours),
        mass_report=MASS_REPORT,mass_lead_report=MASS_LEAD_REPORT,
        csv_sha256=digest(ROOT/'submission.csv'))
    (ROOT/'batch_variant_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
BATCH_VARIANT_AUDIT=_batch_public_mass_audit()
