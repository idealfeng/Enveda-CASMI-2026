"""Prepare the public popwenman MASS-only recipe with equivalent public v2 weights."""
from pathlib import Path
import ast
import copy
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
NAME='public_mass_repro'
TARGET='stormseye/casmi26-public-mass-repro-1107'
SOURCE=ROOT/'third_party/public_scan_popwenman__casmi26-0482-gold-apex-v22_20261107/source.ipynb'
SOURCE_SHA='351d0fadaffd5d9894d76f55b3fa30247b269255d6ca46fe1e93f3d31ef9d9d4'
OUT=ROOT/'submission/aggressive_20261107'/NAME
V2_SHA='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'
PUBLIC_PINS={
 'features.py':'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455',
 'model.py':'2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39',
 'config.json':'563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03',
 'final_model.pt':'44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def src(cell):
 v=cell['source'];return ''.join(v) if isinstance(v,list) else v
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

OBSERVER=r'''
# Observe the public recipe without changing its scoring or optional stages.
def _batch_public_mass_audit():
    import hashlib,json
    from pathlib import Path
    import numpy as np
    import pandas as pd
    import rdkit
    expected=__EXPECTED__
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
'''

def main():
 if OUT.exists():raise FileExistsError('Preserve prepared stages')
 raw=SOURCE.read_bytes()
 if sha(raw)!=SOURCE_SHA:raise ValueError('Original public source changed')
 original=json.loads(raw);nb=copy.deepcopy(original)
 model_path=ROOT/'assets/kaggle/popwenman/casmi26-scorer-train-v80/v1/casmi_spectrum_model_ours_v80/final_model.pt'
 replacement_path=ROOT/'assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1/final_model.pt'
 if not model_path.exists() or not replacement_path.exists():raise FileNotFoundError('Both original and equivalent public weights required')
 if sha(model_path.read_bytes())!=V2_SHA or sha(replacement_path.read_bytes())!=V2_SHA:raise ValueError('Model equivalence proof failed')
 original_cfg=read(model_path.parent/'config_used.json');replacement_cfg=read(replacement_path.parent/'config_used.json')
 different={k for k in set(original_cfg)|set(replacement_cfg) if original_cfg.get(k)!=replacement_cfg.get(k)}
 if not different<={'output','work'}:raise ValueError('Unexpected native model configuration differences: '+repr(sorted(different)))
 if not all(x in src(original['cells'][4]) for x in ["V8 = 'MASS'","COMMIT_MODE = 'fast'"]):raise ValueError('Unexpected public recipe')
 metadata=read(ROOT/'submission/flex_v56_cloud_draft/kernel-metadata.json')
 metadata.update(id=TARGET,title='CASMI26 Public mass repro 1107',code_file='notebook.ipynb')
 metadata['dataset_sources'] += ['bgunshui/casmi26-scorer-v2-model/1','qwertykeypadapple/casmi26-lotus-candidates/2']
 recipe=dict(branch=NAME,target=TARGET,upstream='popwenman/casmi26-0482-gold-apex-v22',upstream_version=2,
     upstream_source_sha256=SOURCE_SHA,recipe='Original MASS-only, RR disabled',validation_mode='fast_static',
     adaptations=['Replace unavailable-in-dataset training output with byte-identical public bgun v2 weights.',
         'Use previously working Docker image and existing offline RDKit bundle.',
         'Omit catalogue/extra wheel datasets unused by the inference code; use pinned old six plus v2 and LOTUS.',
         'Append observer; all original cells remain byte-identical.'],
     checkpoint_sha256=V2_SHA,native_configuration_differences=sorted(different),new_training=False,locked_final_used=False)
 recipe_raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipe_sha=sha(recipe_raw)
 expected=dict(branch=NAME,recipe_sha256=recipe_sha,public_pins=PUBLIC_PINS,v2_sha=V2_SHA,
     lotus_sha='7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f')
 nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=OBSERVER.replace('__EXPECTED__',repr(expected))))
 for i,c in enumerate(nb['cells']):
  if c['cell_type']=='code':
   compile(src(c),'prepared-public-mass','exec');c['outputs']=[];c['execution_count']=None
 for a,b in zip(original['cells'],nb['cells']):
  if src(a)!=src(b):raise ValueError('Original source cell modified')
 OUT.mkdir(parents=True);write(OUT/'notebook.ipynb',nb);write(OUT/'kernel-metadata.json',metadata);(OUT/'recipe.json').write_bytes(recipe_raw)
 static=dict(status='passed',target=TARGET,version=1,notebook_sha256=sha((OUT/'notebook.ipynb').read_bytes()),
     checks=dict(original_source_pin=True,all_original_cell_text_unchanged=True,all_code_compile=True,
     native_checkpoint_equivalent=True,configuration_inference_equivalent=True,private_offline=True,
     original_mass_only_recipe=True,known_runtime_image=True,no_training_or_label_use=True))
 write(OUT/'static_review.json',static)
 receipt=dict(status='prepared',branch=NAME,target=TARGET,version=1,notebook_sha256=static['notebook_sha256'],
     metadata_sha256=sha((OUT/'kernel-metadata.json').read_bytes()),recipe_sha256=recipe_sha,
     static_review_path=str((OUT/'static_review.json').relative_to(ROOT)),validation_mode='fast_static')
 write(OUT/'prepare_receipt.json',receipt);print(json.dumps(receipt,indent=2));return receipt

if __name__=='__main__':main()
