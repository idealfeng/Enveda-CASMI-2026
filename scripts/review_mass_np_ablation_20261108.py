"""Exercise the prepared final-NP ablation and its observer on bounded fixtures."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_mass_np_ablation_20261108 import OUT, SOURCE, SOURCE_SHA, instrument_merge, merge_function, src


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import numpy as np
    import pandas as pd
    import rdkit
    if rdkit.__version__ != '2026.03.3':
        raise ValueError('Run this fixture in the official-metric environment')
    original = json.loads(SOURCE.read_text(encoding='utf-8'))
    nb = json.loads((OUT/'notebook.ipynb').read_text(encoding='utf-8'))
    checks = {}

    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise AssertionError(name)

    check('source_pin', sha(SOURCE) == SOURCE_SHA)
    check('only_planned_original_cells_changed', [i for i, (a,b) in enumerate(zip(original['cells'],nb['cells']))
        if src(a) != src(b)] == [4,20])
    check('configuration_single_np_weight', src(nb['cells'][4]).replace(
        'POP_W, SPEC_W, NP_W = 0.10, 0.10, 0.0', 'POP_W, SPEC_W, NP_W = 0.10, 0.10, 0.12') == src(original['cells'][4]))
    check('merge_exact_instrumentation', instrument_merge(src(original['cells'][20])) == src(nb['cells'][20]))
    before = src(original['cells'][20]).split('    # 2b. Empty slots:',1)[1]
    after = src(nb['cells'][20]).split('    # 2b. Empty slots:',1)[1]
    check('outside_lotus_fill_exactly_unchanged', before == after)
    check('mass_leader_cell_unchanged', src(original['cells'][22]) == src(nb['cells'][22]))

    def function(cell_text, weight):
        namespace = dict(LIB_MAX={}, LIB_HIT_GATE=.78, POP_W=.10, SPEC_W=.10,
                         NP_W=weight, PIN_OLD_LEADER=True, MASS_PEN={})
        exec(compile(ast.fix_missing_locations(merge_function(cell_text)), '<actual-pxm>', 'exec'), namespace)
        return namespace['pxm_merge']

    physical = pd.DataFrame([('q1','C;CC;CCC'),('q2','CCC;CC;C')], columns=['molecule_id','smiles'])
    v2 = pd.DataFrame([('q1','C;CC;CCC'),('q2','CC;C;CCC')], columns=['molecule_id','smiles'])
    custom = pd.DataFrame([('q1','C;CC;CCC'),('q2','CC;C;CCC')], columns=['molecule_id','smiles'])
    evidence = {'q1': {'C':(1,1,'K1'), 'CC':(2,2,'K2'), 'CCC':(3,3,'K3')},
                'q2': {'C':(3,2,'K1'), 'CC':(1,1,'K2'), 'CCC':(2,3,'K3')}}
    kwargs = dict(np_map={'K3':1}, nf_evidence=evidence)
    for weight in (0.0, .12):
        old, old_counts = function(src(original['cells'][20]), weight)(physical,v2,custom,**kwargs)
        new, new_counts = function(src(nb['cells'][20]), weight)(physical,v2,custom,**kwargs)
        check('instrumentation_score_equivalence_' + str(weight), old == new and
            all(new_counts[k] == value for k,value in old_counts.items()))
    enabled, _ = function(src(nb['cells'][20]), .12)(physical,v2,custom,**kwargs)
    disabled, counts = function(src(nb['cells'][20]), 0.0)(physical,v2,custom,**kwargs)
    check('fixture_np_changes_expected_tail', enabled[0][1] == ['C','CCC','CC'] and disabled[0][1] == ['C','CC','CCC'])
    check('fixture_leaders_and_candidate_sets_preserved', all(a[0] == b[0] and a[1][0] == b[1][0]
        and set(a[1]) == set(b[1]) for a,b in zip(enabled,disabled)))
    check('fixture_zero_contribution_has_real_calls', counts['np_scored_candidates'] > 0 and
        counts['np_member_scored_candidates'] > 0 and counts['np_bonus_sum'] == counts['np_bonus_absmax'] == 0.0)

    fixture = ROOT/'reports/mass_np_ablation_fixture_20261108'
    fixture.mkdir(parents=True,exist_ok=False)
    pub = ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
    ours = fixture/'ours_bundle'; ours.mkdir()
    for filename in ('features.py','model.py','config.json'):
        shutil.copyfile(pub/filename,ours/filename)
    shutil.copyfile(ROOT/'assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1/final_model.pt',ours/'final_model.pt')
    ids = ['fixture_a','fixture_b']
    pd.DataFrame({'molecule_id':ids,'smiles':['C;CC','CCC;CCCC']}).to_csv(fixture/'submission.csv',index=False)
    (fixture/'execution_receipt.json').write_text(json.dumps(dict(is_full_run=True,processed_molecules=2)))
    a = pd.DataFrame(dict(molecule_id=['fixture_a']*2+['fixture_b']*2,
        smiles=['C','CC','CCC','CCCC'], neural_score=[1.,2.,4.,8.], neural_ok=[True]*4))
    b = a.copy(); b['neural_score'] = [2.,4.,3.,6.]
    def z(frame):
        group=frame.groupby('molecule_id')['neural_score']
        return (frame.neural_score-group.transform('mean'))/group.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)
    c = a.copy(); c['neural_score'] = .5*z(a)+.5*z(b)
    for name, frame in [('neural_public',a),('neural_ours',b),('neural_candidate_features',c)]:
        frame.to_parquet(fixture/(name+'.parquet'),index=False)
    observer = src(nb['cells'][-1])
    globals_template = dict(ROOT=fixture, INPUT=ROOT/'assets/kaggle/qwertykeypadapple', SAMPLE_IDS=ids,
        PUB_BUNDLE=pub, OURS_BUNDLE=ours, V8='MASS', MASS_ON=True, RR8=False,
        MASS_CENTER=-1.5, MASS_W=.15, POP_W=.10,SPEC_W=.10,NP_W=0.,LIB_HIT_GATE=.78,
        PIN_OLD_LEADER=True,OUTSIDER_FILL=True,FRAG_ON_V2=True, VARIANT='CUSTOM',SUBMITTED='CUSTOM',
        MASS_REPORT={'status':'on'},MASS_LEAD_REPORT={'status':'ran'},RR8_REPORT={'status':'off in this preset'})
    def observe(hidden, changes=None):
        namespace=dict(globals_template)
        namespace.update(IS_RERUN=hidden,RUN_PIPELINE=hidden,PIPELINE_DONE=hidden,NEURAL_OK=hidden,CONSENSUS_OK=hidden,
            MERGE_REPORT=dict(status='applied',rows=2,np_scored_candidates=4,np_member_scored_candidates=1,
                              np_bonus_sum=0.,np_bonus_absmax=0.) if hidden else dict(status='skipped_fast_commit'))
        if changes:
            namespace.update(changes)
        exec(compile(observer,'<actual-observer>','exec'),namespace)
        return namespace['BATCH_VARIANT_AUDIT']
    fast=observe(False); check('actual_fast_observer_passes',fast['mode']=='fast_static' and not fast['visible_model_executed'])
    hidden=observe(True); check('actual_hidden_observer_passes_dynamic_two_queries',hidden['mode']=='hidden_full'
        and hidden['checks']['hidden_full_scope'] and hidden['checks']['np_bonus_exactly_zero'])
    for name, merge in [('nonzero_np',dict(status='applied',rows=2,np_scored_candidates=4,np_bonus_sum=.12,np_bonus_absmax=.12)),
                        ('no_calls',dict(status='applied',rows=2,np_scored_candidates=0,np_bonus_sum=0.,np_bonus_absmax=0.)),
                        ('silent_merge_fallback',dict(status='restored_custom_after_error',rows=2,np_scored_candidates=4,np_bonus_sum=0.,np_bonus_absmax=0.))]:
        rejected=False
        try:
            observe(True,dict(MERGE_REPORT=merge))
        except AssertionError:
            rejected=True
        check('actual_observer_rejects_'+name,rejected)
    result=dict(status='passed',notebook_sha256=sha(OUT/'notebook.ipynb'),checks=checks,
        fixtures_only=True,full_model_inference=False,labels_used=False,cloud_write_performed=False,
        fast_checks=fast['checks'],hidden_checks=hidden['checks'])
    (fixture/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (OUT/'local_fixture_review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
