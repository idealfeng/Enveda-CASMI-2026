"""Independent exact-source and deployed-payload checks for the chosen guard arms."""
from pathlib import Path
import ast,base64,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import kaggle_batch as batch

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def src(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']

def review(name,prefix,model):
    stage=ROOT/'submission/optimization_20261109'/name
    nb=read(stage/'notebook.ipynb');recipe=read(stage/'recipe.json');spec=read(stage/'branch_spec.json')
    anchor=read(ROOT/'submission/optimization_20261108/mass_guarded_head_tail_1108/notebook.ipynb')
    cfg=recipe['configuration'];late=ast.parse(src(nb['cells'][-2]));node=next(n for n in late.body if isinstance(n,ast.Try))
    values={}
    for n in node.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            try:values[n.targets[0].id]=ast.literal_eval(n.value)
            except (ValueError,TypeError):pass
    payloads={k:base64.b64decode(v) for k,v in values['_late_payloads'].items()}
    checks=dict(anchor_source_pin=sha(ROOT/'submission/optimization_20261108/mass_guarded_head_tail_1108/notebook.ipynb')=='6de37bec32c8aa8bfb46b2c5e94e374b53fe36137dff1cd7d1c4a295359f56fe',
        all_original_cells_exact=len(nb['cells'])==len(anchor['cells']) and all(src(a)==src(b) for a,b in zip(nb['cells'][:-2],anchor['cells'][:-2])),
        prefix_exact=cfg['protected_prefix']==prefix,
        source_spec=sha(stage/'notebook.ipynb')==spec['notebook_sha256'],
        metadata_spec=sha(stage/'kernel-metadata.json')==spec['metadata_sha256'],
        all_payload_hashes=set(payloads)==set(cfg['payload_pins']) and all(hashlib.sha256(v).hexdigest()==cfg['payload_pins'][k] for k,v in payloads.items()),
        named_guard_module=recipe['tail_module_sha256']==sha(ROOT/'scripts/guarded_head_tail_20261109.py'),
        reconstructs_actual_scored_order="check('actual_scored_order_consumed'" in src(nb['cells'][-1]),
        keeps_dynamic_hidden_size="len(SAMPLE_IDS)>0" in src(nb['cells'][-1]))
    if model=='mean':
        checks['mean_only_payload']=set(payloads)=={'guarded_v2_mean_score_20261109.py'} and cfg['head_receipts']==[] and cfg['score_mode']=='frozen_v2_mean'
    else:
        runtime=json.loads(payloads['learned_head_runtime.json'])
        checks['learned_score_wrapper_exact']=payloads['learned_head_score.py']==(ROOT/'scripts/learned_head_score.py').read_bytes()
        checks['runtime_model_source']=hashlib.sha256(payloads[runtime['head_model_file']]).hexdigest()==runtime['head_model_sha256']
        checks['original_scorer_pin']=runtime['baseline_scorer_sha256']=='cb9e4d6732992e3310e951533fd0c644d3b515134ad03768c35e5a86551267d2'
        if model=='isomer':
            training=read(ROOT/'runs/isomer_head_20261109/recipe_frozen_before_training.json')
            headspec=read(ROOT/'runs/isomer_head_20261109/head_spec.json')
            checks['actual_training_source_bound']=runtime['head_model_sha256']==headspec['model_sha256']==training['model_code_sha256']
            checks['actual_trained_weights_bound']=[x['sha256'] for x in runtime['heads']]==[x['sha256'] for x in headspec['heads']]
            checks['independent_training_audit']=read(ROOT/'runs/isomer_head_20261109/independent_verification.json')['status']=='passed'
        else:
            checks['old_trained_weights_bound']=[x['sha256'] for x in runtime['heads']]==['99e63aedb420217c817aeaaebd3d09ffa9620824a8d8833dcf55fd90ae903a53','f29077ca350e48705cec93ed7a9716b2b718e965ba56cec859bb829bf4b7ba75']
    for c in nb['cells']:
        if c['cell_type']=='code':compile(src(c),'root_independent_review','exec')
    checks['all_cells_compile']=True
    if not all(checks.values()):raise ValueError(name+': '+repr(checks))
    return dict(status='passed',checks=checks,notebook_sha256=sha(stage/'notebook.ipynb'))

if __name__=='__main__':
    rows={n:review(n,p,m) for n,p,m in [('mass_guarded_oldhead_p3',3,'old'),('mass_guarded_v2mean_p7',7,'mean'),('mass_guarded_isomer_p7',7,'isomer')]}
    out=ROOT/'reports/guarded_root_review_20261109.json'
    out.write_text(json.dumps(dict(status='passed',branches=rows),indent=2)+'\n',encoding='utf-8')
    print(json.dumps({n:dict(status=r['status'],checks=len(r['checks'])) for n,r in rows.items()}))
