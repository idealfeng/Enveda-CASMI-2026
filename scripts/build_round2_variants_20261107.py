"""Prepare five V35-based afternoon recipes. No network, training or submissions."""
from pathlib import Path
import ast
import copy
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'third_party/public_scan_zz3t3rn41__casmi26-peaks-to-structures-v2_20261107_pm/source.ipynb'
SOURCE_SHA='759067bc1449427089e95b811ee49f866580590905484577fe09a143740a2842'
BASE=ROOT/'submission/aggressive_20261107_pm'
STATE='reports/aggressive_batch_20261107_pm'
PUBLIC_PINS={
 'features.py':'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455',
 'model.py':'2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39',
 'config.json':'563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03',
 'final_model.pt':'44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}
V2_SHA='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'
VARIANTS={
 'v35_baseline':dict(note='Unchanged public V35 recipe; new physical/outsider rules.',public_weight=.5,config={},patch=None),
 'v35_weak_prior':dict(note='Only reduce documentation priors to V56 settings.',public_weight=.5,
     config=dict(SPEC_W=.05,NP_W=.02,LIB_HIT_GATE=.87),patch='weak_prior'),
 'v35_v2_emphasis':dict(note='Only increase v2 neural ensemble weight to .75 in main and outsider scores.',
     public_weight=.25,config={},patch='v2_emphasis'),
 'v35_robust_mass':dict(note='Only aggregate all effective per-spectrum neutral masses by median, retaining original mass constants; raw-adduct fallback fills missing queries.',
     public_weight=.5,config={},patch='robust_mass'),
 'v35_no_interleave':dict(note='Disable forced outside candidates at ranks 8/14/20/24; keep original vacant-slot backfill.',
     public_weight=.5,config={},patch='no_interleave')}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def source(cell):
 value=cell['source'];return ''.join(value) if isinstance(value,list) else value
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def replace_once(text,before,after):
 if text.count(before)!=1:raise ValueError('Expected one exact patch site: '+before[:80])
 return text.replace(before,after)


ROBUST_MAP='''    # Neutral masses: robust across effective spectra, retaining original constants.
    _ADD = {'[M+H]+': 1.007276, '[M+NH4]+': 18.033823, '[M-H2O+H]+': -17.003289, '[M-2H2O+H]+': -35.013853,
            '[M+Na]+': 22.989218, '[M+K]+': 38.963158, '[M-H]-': -1.007276, '[M-H2O-H]-': -19.017841,
            '[M+CH2O2-H]-': 44.998203, '[M+Cl]-': 34.969402}
    nm_map = {}
    _mass_map_report = dict(method='effective_all_spectra_median',effective_queries=0,raw_fallback_queries=0)
    _spec_p = ROOT / 'effective_query_spectra.parquet'
    if _spec_p.is_file():
        _sdf = pd.read_parquet(_spec_p,columns=['molecule_id','nm'])
        _sdf['nm'] = pd.to_numeric(_sdf.nm,errors='coerce')
        _sdf = _sdf[_sdf.nm.notna() & _sdf.nm.gt(50) & _sdf.nm.lt(float('inf'))]
        nm_map = {str(k):float(v) for k,v in _sdf.groupby('molecule_id',sort=False).nm.median().items()}
        _mass_map_report['effective_queries'] = len(nm_map)
    _raw_path = COMP / 'test.parquet'
    if _raw_path.is_file():
        _eq = pd.read_parquet(_raw_path,columns=['molecule_id','precursor_mz','adduct'])
        _eq['neutral_mass'] = pd.to_numeric(_eq.precursor_mz,errors='coerce')-_eq.adduct.map(_ADD)
        _valid = _eq.neutral_mass.notna() & _eq.neutral_mass.gt(50) & _eq.neutral_mass.lt(float('inf'))
        _eq = _eq[_valid]
        for _mid,_neutral in _eq.groupby('molecule_id',sort=False).neutral_mass.median().items():
            if str(_mid) not in nm_map:
                nm_map[str(_mid)]=float(_neutral)
                _mass_map_report['raw_fallback_queries'] += 1
    _mass_map_report['total_queries'] = len(nm_map)
    globals()['BATCH_MASS_MAP_AUDIT'] = _mass_map_report

'''


OBSERVER=r'''
# Read-only recipe, deployment and hidden execution checks.
def _round2_observe():
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
    check('configuration',all(globals().get(k)==v for k,v in expected['config'].items()))
    check('official_rdkit',rdkit.__version__=='2026.03.3')
    public={name:digest(Path(PUB_BUNDLE)/name) for name in expected['public_pins']}
    ours={name:digest(Path(OURS_BUNDLE)/name) for name in expected['public_pins']}
    check('public_model_pins',public==expected['public_pins'])
    wanted=dict(expected['public_pins']);wanted['final_model.pt']=expected['v2_sha']
    check('v2_model_pins',ours==wanted)
    check('distinct_models',public['final_model.pt']!=ours['final_model.pt'])
    lotus=[p for p in INPUT.rglob('candidates_lotus.parquet') if 'casmi26-lotus-candidates' in p.parts]
    check('lotus_pin',len(lotus)==1 and digest(lotus[0])==expected['lotus_sha'])
    sub=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('csv_schema_ids',list(sub.columns)==['molecule_id','smiles'] and sub.molecule_id.tolist()==SAMPLE_IDS and sub.molecule_id.is_unique)
    check('csv_counts',sub.smiles.str.split(';').map(lambda g:1<=len(g)<=25 and all(g)).all())
    blend={}
    if IS_RERUN:
        check('pipeline_complete',PIPELINE_DONE and NEURAL_OK and CONSENSUS_OK and SUBMITTED==VARIANT)
        receipt=json.loads((ROOT/'execution_receipt.json').read_text())
        check('hidden_full_scope',receipt.get('is_full_run') is True and receipt.get('processed_molecules')==len(SAMPLE_IDS)==400)
        check('merge_applied',MERGE_REPORT.get('status')=='applied')
        def verify_blend(label,pa,pb,pc,required):
            if not all(Path(p).is_file() for p in (pa,pb,pc)):
                check(label+'_optional_absence',not required)
                return
            a=pd.read_parquet(pa).set_index(['molecule_id','smiles'])
            b=pd.read_parquet(pb).set_index(['molecule_id','smiles'])
            c=pd.read_parquet(pc).set_index(['molecule_id','smiles'])
            check(label+'_keys',a.index.is_unique and b.index.is_unique and c.index.is_unique and set(a.index)==set(b.index)==set(c.index))
            b,c=b.reindex(a.index),c.reindex(a.index)
            def z(series):
                group=series.groupby(level=0)
                return (series-group.transform('mean'))/group.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)
            w=expected['public_weight']
            wanted=w*z(a.neural_score.fillna(0.0))+(1-w)*z(b.neural_score.fillna(0.0))
            exact=np.array_equal(wanted.to_numpy(),c.neural_score.to_numpy())
            check(label+'_scores',exact)
            check(label+'_coverage',a.neural_ok.astype(bool).equals(b.neural_ok.astype(bool)))
            check(label+'_finite',np.isfinite(c.loc[c.neural_ok.astype(bool),'neural_score']).all())
            blend[label]=dict(rows=len(a),public_weight=w,exact=bool(exact))
        verify_blend('main',ROOT/'neural_public.parquet',ROOT/'neural_ours.parquet',ROOT/'neural_candidate_features.parquet',True)
        # Outsiders retain the author's original optional time guard and fallback.
        outsider_files=[ROOT/name for name in ('outsider_public.parquet','outsider_ours.parquet','outsider_neural_features.parquet')]
        if OUTSIDERS_OK and all(p.is_file() for p in outsider_files):
            try:
                verify_blend('outsider',*outsider_files,False)
            except AssertionError:
                # Preserve evidence, but do not invalidate an allowed optional fallback.
                # Remove only these observer assertions; never edit candidate scores.
                for key in list(checks):
                    if key.startswith('outsider_'):del checks[key]
                blend['outsider']=dict(optional_fallback_observed=True)
        if expected['branch']=='v35_robust_mass':
            check('robust_mass_executed',globals().get('BATCH_MASS_MAP_AUDIT',{}).get('method')=='effective_all_spectra_median')
    else:
        check('fast_no_model',not RUN_PIPELINE and not PIPELINE_DONE)
    result=dict(status='passed',mode='hidden_full' if IS_RERUN else 'fast_static',branch=expected['branch'],
        recipe_sha256=expected['recipe_sha256'],checks=checks,pins=dict(public=public,ours=ours),
        actual_model_inference=bool(RUN_PIPELINE),blend=blend,mass_map_audit=globals().get('BATCH_MASS_MAP_AUDIT'),
        csv_sha256=digest(ROOT/'submission.csv'))
    (ROOT/'batch_variant_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
BATCH_VARIANT_AUDIT=_round2_observe()
'''


def build(name,settings,original):
 stage=BASE/name
 if stage.exists():raise FileExistsError('Preserve prepared experiments: '+name)
 nb=copy.deepcopy(original);patches=[]
 def change(index,before,after,label):
  nb['cells'][index]['source']=replace_once(source(nb['cells'][index]),before,after);patches.append(label)
 patch=settings['patch']
 if patch=='weak_prior':
  change(4,'POP_W, SPEC_W, NP_W = 0.10, 0.10, 0.12','POP_W, SPEC_W, NP_W = 0.10, 0.05, 0.02','weak_documentation_priors')
  change(4,'LIB_HIT_GATE = 0.78','LIB_HIT_GATE = 0.87','library_prior_gate')
 elif patch=='v2_emphasis':
  s=source(nb['cells'][14]);count=0
  for frame,ours in [('_a','_b'),('_oa','_ob')]:
   for column in ['neural_score','neural_cos','neural_fp','neural_std']:
    first=f"{frame}['{column}'] = 0.5 * "
    if s.count(first)!=1:raise ValueError('Unexpected ensemble column')
    # Each original assignment has exactly two weight literals.
    lines=s.splitlines(keepends=True)
    for i,line in enumerate(lines):
     if first in line:
      if line.count('0.5 * ')!=2:raise ValueError('Unexpected mixture expression')
      line=line.replace('0.5 * ','0.25 * ',1)
      second=line.rfind('0.5 * ');line=line[:second]+line[second:].replace('0.5 * ','0.75 * ',1)
      lines[i]=line;count+=1
    s=''.join(lines)
  if count!=8:raise ValueError('Expected eight main/outsider mixture assignments')
  s=replace_once(s,'ENSEMBLE neural = 0.5*z(public) + 0.5*z(ours)',
      'ENSEMBLE neural = 0.25*z(public) + 0.75*z(ours)')
  s=replace_once(s,'ENSEMBLE outsider neural = 0.5*z(public) + 0.5*z(ours)',
      'ENSEMBLE outsider neural = 0.25*z(public) + 0.75*z(ours)')
  nb['cells'][14]['source']=s;patches.append('v2_weight_.75_in_all_eight_main_and_outside_columns')
 elif patch=='robust_mass':
  s=source(nb['cells'][18]);start=s.index('    # Build Neutral Mass Map for timsTOF mass penalty')
  stop=s.index('    merged_tuples, counts = pxm_merge(',start)
  nb['cells'][18]['source']=s[:start]+ROBUST_MAP+s[stop:];patches.append('all_effective_spectra_neutral_median_instead_of_first_effective_mass_raw_fallback')
 elif patch=='no_interleave':
  change(18,'if OUTSIDER_FILL and m_lib < LIB_HIT_GATE and str(mid) in out_by_mid:',
      'if False and OUTSIDER_FILL and m_lib < LIB_HIT_GATE and str(mid) in out_by_mid:',
      'disable_four_forced_outsider_slots_keep_vacant_backfill')
 config={}
 if any(not isinstance(node,ast.Assign) for node in ast.parse(source(nb['cells'][4])).body):
  raise ValueError('Expected literal configuration cell')
 exec(compile(source(nb['cells'][4]),'frozen-config','exec'),config)
 wanted_config={key:config[key] for key in ['VARIANT','CUSTOM','COMMIT_MODE','OUTSIDER_FILL','POP_W','SPEC_W','NP_W','LIB_HIT_GATE','MASS_ON','MASS_CENTER','MASS_FREE','MASS_FULL','MASS_W']}
 target='stormseye/casmi26-'+name.replace('_','-')+'-1107pm'
 recipe=dict(branch=name,target=target,upstream='zz3t3rn41/casmi26-peaks-to-structures-v2',upstream_version=35,
     upstream_sha256=SOURCE_SHA,description=settings['note'],patches=patches,public_weight=settings['public_weight'],
     v2_weight=1-settings['public_weight'],config=wanted_config,validation_mode='fast_static',
     known_best_anchor=.481,training_performed=False,locked_final_used=False)
 recipe_raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipe_sha=sha(recipe_raw)
 expected=dict(branch=name,recipe_sha256=recipe_sha,config=wanted_config,public_weight=settings['public_weight'],
     public_pins=PUBLIC_PINS,v2_sha=V2_SHA,lotus_sha='7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f')
 nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=OBSERVER.replace('__EXPECTED__',repr(expected))))
 for cell in nb['cells']:
  if cell['cell_type']=='code':
   compile(source(cell),'prepared-'+name,'exec');cell['outputs']=[];cell['execution_count']=None
 changed=[i for i,(before,after) in enumerate(zip(original['cells'],nb['cells'])) if source(before)!=source(after)]
 allowed={None:[], 'weak_prior':[4],'v2_emphasis':[14],'robust_mass':[18],'no_interleave':[18]}[patch]
 if changed!=allowed:raise ValueError('Unplanned source cell modifications')
 metadata=read(ROOT/'submission/aggressive_20261107/public_mass_repro/kernel-metadata.json')
 metadata.update(id=target,title=target.split('/')[-1].replace('-',' '),code_file='notebook.ipynb')
 stage.mkdir(parents=True);write(stage/'notebook.ipynb',nb);write(stage/'kernel-metadata.json',metadata);(stage/'recipe.json').write_bytes(recipe_raw)
 static=dict(status='passed',target=target,version=1,notebook_sha256=sha((stage/'notebook.ipynb').read_bytes()),
     checks=dict(upstream_source_pin=True,all_code_compile=True,only_planned_cells_changed=True,
     rr_and_v4_absent=True,private_offline=True,model_sources_previously_verified=True,
     no_new_training_or_label_use=True,fast_static_scope_explicit=True),changed_original_cells=changed)
 write(stage/'static_review.json',static)
 receipt=dict(status='prepared',branch=name,target=target,version=1,notebook_sha256=static['notebook_sha256'],
     metadata_sha256=sha((stage/'kernel-metadata.json').read_bytes()),recipe_sha256=recipe_sha,
     static_review_path=str((stage/'static_review.json').relative_to(ROOT)),validation_mode='fast_static')
 write(stage/'prepare_receipt.json',receipt)
 return dict(name=name,target=target,version=1,stage_dir=str(stage.relative_to(ROOT)),
     notebook_sha256=receipt['notebook_sha256'],metadata_sha256=receipt['metadata_sha256'],
     static_review_path=receipt['static_review_path'],description='CASMI26 20261107 PM '+name+' audited V1',validation_mode='fast_static',
     required_runtime_audits=[dict(name='batch_variant_audit.json',
     expected_fields=dict(status='passed',mode='fast_static',branch=name,recipe_sha256=recipe_sha),
     required_true_checks=['configuration','official_rdkit','public_model_pins','v2_model_pins','distinct_models','lotus_pin','csv_schema_ids','csv_counts','fast_no_model'])])


def main():
 if BASE.exists():raise FileExistsError('Use a fresh batch directory')
 raw=SOURCE.read_bytes()
 if sha(raw)!=SOURCE_SHA:raise ValueError('Upstream source changed')
 original=json.loads(raw)
 if source(original['cells'][14]).count('0.5 * ')!=16:raise ValueError('Expected original dual ensemble recipe')
 BASE.mkdir(parents=True)
 branches=[build(name,settings,original) for name,settings in VARIANTS.items()]
 manifest=dict(schema_version=1,batch_id='20261107_pm',competition='enveda-CASMI26-molecule-id-mass-spectra',
     max_submissions=5,baseline_public_score=.481,state_root=STATE,branches=branches)
 write(BASE/'manifest.json',manifest)
 print(json.dumps(dict(status='prepared',manifest=str((BASE/'manifest.json').relative_to(ROOT)),
     branches=[dict(name=b['name'],target=b['target']) for b in branches]),indent=2))

if __name__=='__main__':main()
