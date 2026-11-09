"""Run the embedded 102-feature reranker on synthetic spectra; no competition labels."""
from pathlib import Path
import json
import sys
import time
import hashlib

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'submission/aggressive_20261107/flex_rr_aggressive/rr_review'
sys.path.insert(0,str(REVIEW))

def main():
    import numpy as np
    import lightgbm as lgb
    import frag_rescore as frag
    import rr_features as rf
    import rr_overlay as overlay
    started=time.monotonic()
    raw=(REVIEW/'rr_model.txt').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='3b80e1c9adf90721c99bb4e817a05379dd8b26e0988a001bd112330a66d9122b'
    model=lgb.Booster(model_str=raw.decode())
    smiles=['CC(=O)Nc1ccc(O)cc1','CC(=O)Nc1cccc(O)c1','CC(=O)Nc1ccccc1O']
    spectra=[dict(mz=np.array([43.01839,80.,108.0444,134.,152.0706]),
        it=np.array([.1,.5,1.,.2,.1]),prec=152.0706,adduct='[M+H]+',mode=1,ce=energy)
        for energy in (20.,40.)]
    frag.warmup()
    features=overlay.model_features(rf,frag,spectra,smiles,{}, {})
    predictions=model.predict(features)
    changed=overlay.rerank_list(smiles,dict(zip(smiles,[0.,3.,-2.])),dict.fromkeys(smiles,False),alpha=1.5)
    frozen=overlay.rerank_list(smiles,dict(zip(smiles,[0.,3.,-2.])),dict.fromkeys(smiles,True),alpha=1.5)
    checks=dict(expected_102_features=features.shape==(3,102),model_102_features=model.num_feature()==102,
        valid_prediction_shape=predictions.shape==(3,),finite_predictions=bool(np.isfinite(predictions).all()),
        actual_candidate_sets_preserved=set(changed)==set(smiles),top1_can_move=changed[0]!=smiles[0],
        training_freeze_preserved=frozen==smiles)
    record=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
        fixture='Synthetic spectra and three example isomers; no query labels or hidden inputs',
        features_shape=list(features.shape),predictions=predictions.tolist(),
        seconds=time.monotonic()-started,performance_evaluated=False,training_performed=False)
    destination=ROOT/'reports/aggressive_variant_review_20261107/rr_model_fixture.json'
    if destination.exists():raise FileExistsError('Preserve prior fixture evidence')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))
    return 0 if record['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
