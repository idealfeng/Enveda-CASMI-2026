"""Independently inspect saved real canary scores and reconstruct candidate order.

Runs entirely on CPU, never invokes models, upstream notebooks, or Kaggle.
"""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
import pandas as pd
import rdkit
from rdkit import Chem, RDLogger
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem.MolStandardize import rdMolStandardize
from train_candidate_multispectrum_head import write


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']


def describe(smiles):
    m = Chem.MolFromSmiles(smiles)
    assert m is not None
    Chem.RemoveStereochemistry(m)
    m = rdMolStandardize.TautomerEnumerator().Canonicalize(m)
    return Chem.MolToInchiKey(m)[:14], rdMolDescriptors.CalcMolFormula(m)


def inspect(name):
    stage = ROOT/'submission/optimization_20261109'/name
    run = ROOT/'runs/guarded_batch_actual_canary_20261109'/name
    spec = read(stage/'branch_spec.json');recipe = read(stage/'recipe.json')
    nb = read(stage/'notebook.ipynb')
    base_nb = read(ROOT/'submission/optimization_20261108/mass_guarded_head_tail_1108/notebook.ipynb')
    cfg = recipe['configuration'];prefix = cfg['protected_prefix']
    before = pd.read_csv(run/'submission_guarded_tail_control.csv',dtype=str,keep_default_na=False)
    after = pd.read_csv(run/'submission.csv',dtype=str,keep_default_na=False)
    scored = pd.read_parquet(run/'guarded_tail_scores.parquet')
    evidence = pd.read_parquet(run/'guarded_tail_evidence.parquet')
    queries = pd.read_parquet(run/'effective_query_spectra.parquet')
    audit = read(run/'guarded_tail_scores.parquet.head_audit.json')
    observer = read(run/'guarded_tail_audit.json')
    runtime = read(run/'guarded_tail_runtime.json')
    canary = read(run/'verification.json')
    keyset = lambda f:set(zip(f.molecule_id.astype(str),f.smiles))
    checks = dict(staged_source_pin=sha(stage/'notebook.ipynb')==spec['notebook_sha256']==canary['stage_sha256'],
        original_pipeline_sources_unchanged=[source(c) for c in nb['cells'][:-2]]==[source(c) for c in base_nb['cells'][:-2]],
        installed_payload_pins=all(sha(run/'code'/filename)==value for filename,value in cfg['payload_pins'].items()),
        installed_tail_pin=sha(run/'code/guarded_head_tail_20261109.py')==recipe['tail_module_sha256'],
        original_scorer_pin=sha(run/'code/neural_scores_original.py')==cfg['baseline_scorer_sha256'],
        actual_coverage=len(before)==len(after)==3 and len(queries)==36 and len(scored)==len(evidence)==75,
        exact_ids_order=before.molecule_id.tolist()==after.molecule_id.tolist(),
        exact_scored_candidate_keys=keyset(evidence)==keyset(scored) and not scored.duplicated(['molecule_id','smiles']).any(),
        scores_finite_and_usable=bool(scored.neural_ok.all()) and bool(np.isfinite(scored.neural_score).all()),
        inputs_and_outputs_bound=audit['evidence_sha256']==sha(run/'guarded_tail_evidence.parquet') and audit['queries_sha256']==sha(run/'effective_query_spectra.parquet') and audit['output_sha256']==sha(run/'guarded_tail_scores.parquet'),
        observer_passed=observer['status']=='passed' and all(observer['checks'].values()),
        actual_runtime_applied=runtime['status']=='applied' and runtime['model_invoked'] is True,
        exact_head_receipts=audit['heads']==cfg['head_receipts']==runtime['head_receipts'])
    reconstruction = [];identity_ok=formula_ok=prefix_ok=candidates_ok=True
    by_mid = {str(mid):g for mid,g in scored.groupby('molecule_id',sort=False)}
    for mid,raw in before.itertuples(index=False,name=None):
        old = raw.split(';');new = list(old)
        desc = {s:describe(s) for s in old}
        values = dict(zip(by_mid[str(mid)].smiles,by_mid[str(mid)].neural_score))
        slots = defaultdict(list)
        for i,s in enumerate(old[prefix:],prefix):slots[desc[s][1]].append(i)
        for positions in slots.values():
            ranked = sorted((old[i] for i in positions), key=lambda s:(-float(values[s]),old.index(s)))
            for i,s in zip(positions,ranked):new[i]=s
        actual = after.loc[after.molecule_id==str(mid),'smiles'].item().split(';')
        reconstruction.append((str(mid),';'.join(new)))
        prefix_ok &= actual[:prefix]==old[:prefix]
        candidates_ok &= Counter(actual)==Counter(old)
        identity_ok &= Counter(describe(s)[0] for s in actual)==Counter(v[0] for v in desc.values())
        formula_ok &= all(describe(old[i])[1]==describe(actual[i])[1] for i in range(prefix,len(old)))
    checks.update(independent_scored_order_reconstruction=pd.DataFrame(reconstruction,columns=['molecule_id','smiles']).equals(after),
                  prefix_exact=prefix_ok,candidate_multisets_exact=candidates_ok,
                  official_identity_multisets_exact=identity_ok,formula_slots_exact=formula_ok)
    mean = scored.neural_cos/.1+2*scored.neural_fp
    mean_difference = float(np.abs(scored.neural_score-mean).max())
    if cfg['score_mode']=='frozen_v2_mean':
        checks['no_head_executed'] = audit['head_applied'] is False and audit['heads']==[] and audit['role']=='frozen_v2_mean'
        checks['actual_v2_mean_parity'] = mean_difference < 3e-6
    elif name=='mass_guarded_isomer_p7':
        checks['new_isomer_source_pin'] = sha(run/'code/candidate_multispectrum_head.py')=='894e000d85bd26d4845a7404782f38a8952955c77c4e0ee055b07542a0f7a18d'
        checks['actual_isomer_correction_bound'] = mean_difference <= .50001
    return dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
                stage_sha256=sha(stage/'notebook.ipynb'),scored_candidate_rows=len(scored),
                maximum_difference_from_original_v2_mean=mean_difference,
                canary_only=True,upstream_pipeline_executed_in_canary=False,
                control='Three rows of previously saved original output; base audit scope constructed only for late-stage integration fixture',
                known_pretrained_exposure=True),scored


def main():
    assert rdkit.__version__=='2026.03.3'
    RDLogger.DisableLog('rdApp.*')
    names = sys.argv[1:] or ['mass_guarded_oldhead_p3','mass_guarded_oldhead_p1','mass_guarded_v2mean_p7','mass_guarded_isomer_p7']
    reports={};frames={}
    for name in names:reports[name],frames[name]=inspect(name)
    cross={}
    a,b='mass_guarded_oldhead_p3','mass_guarded_oldhead_p1'
    if a in frames and b in frames:
        left=frames[a].sort_values(['molecule_id','smiles']).reset_index(drop=True)
        right=frames[b].sort_values(['molecule_id','smiles']).reset_index(drop=True)
        cross['p1_p3_identical_actual_scores_only_prefix_differs']=left.equals(right)
    result=dict(status='passed' if all(r['status']=='passed' for r in reports.values()) and all(cross.values()) else 'failed',
                branches=reports,cross_branch_checks=cross,no_model_invoked_by_review=True,
                canary_is_interface_test_not_efficacy_validation=True)
    write(ROOT/'reports/guarded_batch_independent_actual_review_20261109.json',result)
    print(json.dumps(result))
    if result['status']!='passed':raise ValueError('Independent saved-artifact audit failed')


if __name__=='__main__':main()
