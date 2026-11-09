"""Prepare one V56 + learned isomer reranker branch, without external actions."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import textwrap

ROOT = Path(__file__).resolve().parents[1]
NAME = 'flex_rr_aggressive'
TARGET = 'stormseye/casmi26-flex-rr-aggressive-1107'
ORIGINAL = ROOT/'third_party/flexonafft_evidence_gap/v56/original.ipynb'
ROMAN = ROOT/'third_party/romanrozen_0482_20261106/source.ipynb'
OUT = ROOT/'submission/aggressive_20261107'/NAME
ORIGINAL_SHA = '0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769'
ROMAN_SHA = '5bdea66bc23d299d9349122c9403a238e952bc91d356dffbe95d562e00553726'


def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def source(cell):
    value=cell['source']; return ''.join(value) if isinstance(value,list) else value
def code(value): return dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=value)
def ast_equal(first,second): return ast.dump(ast.parse(first))==ast.dump(ast.parse(second))
def write(path,value): path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


OBSERVER = r'''
# Observer does not change the candidate list, scores or submission file.
def _batch_rr_audit():
    import hashlib,json
    import pandas as pd
    import numpy as np
    from pathlib import Path
    from rdkit import Chem
    import rdkit
    expected=__EXPECTED__
    checks={}
    def check(name,value):
        checks[name]=bool(value)
        assert value,name
    check('recipe_configuration',RR8 is True and RR8_ALPHA==1.5 and RR8_LIB_TAU==0.95 and MASS_ON is False)
    check('original_final_prior',POP_W==0.1 and SPEC_W==0.05 and NP_W==0.02 and LIB_HIT_GATE==0.87)
    check('official_rdkit',rdkit.__version__=='2026.03.3')
    pins={name:hashlib.sha256((Path(BUNDLE)/name).read_bytes()).hexdigest() for name in expected['public_pins']}
    check('public_model_pins',pins==expected['public_pins'])
    check('rr_features_pin',hashlib.sha256(_RR8_FEATURES.encode()).hexdigest()==expected['features_sha'])
    check('rr_overlay_pin',hashlib.sha256(_RR8_OVERLAY.encode()).hexdigest()==expected['overlay_sha'])
    model_text=zlib.decompress(base64.b64decode(_RR8_MODEL_Z)).decode()
    check('rr_model_pin',hashlib.sha256(model_text.encode()).hexdigest()==expected['model_sha'])
    sub=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('csv_schema_ids',list(sub.columns)==['molecule_id','smiles'] and sub.molecule_id.tolist()==SAMPLE_IDS and sub.molecule_id.is_unique)
    lists=sub.smiles.str.split(';')
    check('csv_counts',lists.map(len).between(1,25).all() and lists.map(lambda values:all(values)).all())
    mode='hidden_full' if IS_RERUN else 'fast_static'
    if IS_RERUN:
        check('hidden_pipeline',PIPELINE_DONE and NEURAL_OK and CONSENSUS_OK and SUBMITTED==VARIANT)
        check('rr_executed',RR8_REPORT.get('status')=='ran' and RR8_REPORT.get('failed')==0)
        before=pd.read_csv(ROOT/'submission_before_rr8.csv',dtype=str,keep_default_na=False)
        check('rr_candidate_sets',_v8_check(before,sub))
        check('hidden_all_queries',len(sub)==400)
    else:
        check('fast_no_model',RUN_PIPELINE is False and PIPELINE_DONE is False)
    record=dict(status='passed',mode=mode,branch=expected['branch'],recipe_sha256=expected['recipe_sha256'],
        checks=checks,visible_model_executed=bool(RUN_PIPELINE),pins=pins,
        rr_report=globals().get('RR8_REPORT',{}),scoring_rerun=bool(IS_RERUN),
        csv_sha256=hashlib.sha256((ROOT/'submission.csv').read_bytes()).hexdigest())
    (ROOT/'batch_variant_audit.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
BATCH_VARIANT_AUDIT=_batch_rr_audit()
'''


def main():
    if OUT.exists(): raise FileExistsError('Preserve existing prepared branches')
    original_raw,roman_raw=ORIGINAL.read_bytes(),ROMAN.read_bytes()
    if sha(original_raw)!=ORIGINAL_SHA or sha(roman_raw)!=ROMAN_SHA: raise ValueError('Pinned source changed')
    original,roman=json.loads(original_raw),json.loads(roman_raw)
    nb=copy.deepcopy(original)
    configuration=source(nb['cells'][1])
    if configuration.count("COMMIT_MODE = 'smoke'")!=1: raise ValueError('Unexpected original commit mode')
    nb['cells'][1]['source']=configuration.replace("COMMIT_MODE = 'smoke'","COMMIT_MODE = 'fast'")
    # Keep all original hidden inference statements in their original order.
    current=source(original['cells'][11])
    marker="if not PIPELINE_DONE and not IS_RERUN and COMMIT_MODE == 'fast':"
    before,tail=current.split(marker,1)
    after=tail[tail.index('if not PIPELINE_DONE:'):]
    nb['cells'][11]['source']=before+'''if not RUN_PIPELINE:
    _fast_sample=pd.read_csv(COMP/'sample_submission.csv',dtype=str)
    _fast_sample['smiles']='CCO'
    _fast_sample.to_csv(ROOT/'submission.csv',index=False)
    NEURAL_OK=OUTSIDERS_OK=CONSENSUS_OK=False
    SUBMITTED='fast_static'
else:
'''+textwrap.indent(after,'    ')
    hidden_ast=ast.parse(source(nb['cells'][11])).body[-1].orelse
    if ast.dump(ast.Module(body=hidden_ast,type_ignores=[]))!=ast.dump(ast.parse(after)):
        raise ValueError('Hidden pipeline schedule changed')
    for i in range(12,len(original['cells'])):
        if original['cells'][i]['cell_type']=='code':
            src=source(original['cells'][i])
            wrapped='if RUN_PIPELINE:\n'+textwrap.indent(src,'    ')
            if ast.dump(ast.Module(body=ast.parse(wrapped).body[0].body,type_ignores=[]))!=ast.dump(ast.parse(src)):
                raise ValueError('Original scoring cell changed')
            nb['cells'][i]['source']=wrapped
    rr_source=source(roman['cells'][22])
    payload={}
    for node in ast.parse(rr_source).body:
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id.startswith('_RR8_'): payload[target.id]=node.value.value
    import base64,zlib
    pins=dict(features_sha=sha(payload['_RR8_FEATURES'].encode()),overlay_sha=sha(payload['_RR8_OVERLAY'].encode()),
        model_sha=sha(zlib.decompress(base64.b64decode(payload['_RR8_MODEL_Z']))))
    expected_pins=dict(features_sha='aec9012e72324095308af81c1408aa36f6a44cb00f6d4389e87529a68329d176',
        overlay_sha='e83b7986c46d0ef02bc6cfde17e891c9e7ee66a0eed8c716f5e3474e5663ccf7',
        model_sha='3b80e1c9adf90721c99bb4e817a05379dd8b26e0988a001bd112330a66d9122b')
    if pins!=expected_pins: raise ValueError('Embedded reranker payload changed')
    recipe=dict(branch=NAME,target=TARGET,base='original Flex V56',base_sha256=ORIGINAL_SHA,
        component='Roman V17 embedded 102-feature isomer LightGBM',component_source_sha256=ROMAN_SHA,
        changes=dict(RR8=True,RR8_ALPHA=1.5,RR8_LIB_TAU=0.95,RR8_BUDGET_SECONDS=2700,
            MASS_ON=False,top1_changes='Allowed for movable non-training structures below the library threshold'),
        neural='original public Saner only',prior='original V56 0.10/0.05/0.02, gate 0.87',
        validation_mode='fast_static',new_training=False,locked_final_used=False,**pins)
    recipe_raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode()
    recipe_sha=sha(recipe_raw)
    settings='''# Aggressive learned-reranker experiment, preserving V56 inference and priors.
V8='RR'
MASS_ON=False
MASS_PEN={}; MASS_PPM={}; MASS_REPORT={'status':'off in this experiment'}
RR8=True
RR8_ALPHA=1.5
RR8_LIB_TAU=0.95
RR8_BUDGET_SECONDS=2700
RR8_LIMIT_SECONDS=9*3600-1800
RR8_MIN_SECONDS=600
'''
    nb['cells'].extend([code(settings),code(rr_source)])
    public_pins={
        'features.py':'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455',
        'model.py':'2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39',
        'config.json':'563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03',
        'final_model.pt':'44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}
    expected=dict(branch=NAME,recipe_sha256=recipe_sha,public_pins=public_pins,**pins)
    nb['cells'].append(code(OBSERVER.replace('__EXPECTED__',repr(expected))))
    for cell in nb['cells']:
        if cell['cell_type']=='code':
            compile(source(cell),'prepared-'+NAME,'exec')
            cell['execution_count']=None;cell['outputs']=[]
    metadata=read(ROOT/'submission/flex_v56_cloud_draft/kernel-metadata.json')
    metadata.update(id=TARGET,title='CASMI26 Flex rr aggressive 1107',code_file='notebook.ipynb')
    OUT.mkdir(parents=True)
    (OUT/'recipe.json').write_bytes(recipe_raw)
    write(OUT/'notebook.ipynb',nb);write(OUT/'kernel-metadata.json',metadata)
    check=dict(source_pins=True,hidden_schedule_preserved=True,all_original_scoring_cells_preserved=True,
        original_neural_and_priors_preserved=True,embedded_rr_pins=True,all_cells_compile=True,
        private_offline=metadata['is_private'] is True and metadata['enable_internet'] is False,
        no_new_data_or_training=True,fast_placeholder_not_hidden_predictions=True)
    static=dict(status='passed',target=TARGET,version=1,notebook_sha256=sha((OUT/'notebook.ipynb').read_bytes()),checks=check)
    write(OUT/'static_review.json',static)
    receipt=dict(status='prepared',branch=NAME,target=TARGET,version=1,
        notebook_sha256=static['notebook_sha256'],metadata_sha256=sha((OUT/'kernel-metadata.json').read_bytes()),
        recipe_sha256=recipe_sha,static_review_path=str((OUT/'static_review.json').relative_to(ROOT)),
        validation_mode='fast_static',runtime_model_validation=False)
    write(OUT/'prepare_receipt.json',receipt)
    # Review-only files support a small, real feature/model inference fixture.
    review=OUT/'rr_review';review.mkdir()
    (review/'rr_features.py').write_text(payload['_RR8_FEATURES'],encoding='utf-8')
    (review/'rr_overlay.py').write_text(payload['_RR8_OVERLAY'],encoding='utf-8')
    (review/'rr_model.txt').write_bytes(zlib.decompress(base64.b64decode(payload['_RR8_MODEL_Z'])))
    for node in ast.parse(source(original['cells'][10])).body:
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
            if any(isinstance(t,ast.Name) and t.id=='_physical' for t in node.targets):
                (review/'frag_rescore.py').write_text(node.value.value,encoding='utf-8')
    print(json.dumps(receipt,indent=2));return receipt


if __name__=='__main__': main()
