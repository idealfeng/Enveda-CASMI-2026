"""Read-only count of evaluation candidates removed by split-identity filtering."""
from pathlib import Path
import json
import numpy as np
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'runs/candidate_head_20261108'
queries=json.loads((folder/'queries.json').read_text())
receipt=json.loads((folder/'prepare_receipt.json').read_text())
denied=set(receipt['deny_identities'])
independent={q['key'] for q in queries if q['split']!='train'}
pool=pq.read_table(ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/pool_meta.parquet',columns=['smiles','mass'])
masses=pool['mass'].to_numpy()
mapping={r['smiles']:r for r in pq.read_table(folder/'candidate_catalog.parquet').to_pylist()}
rows=[]
for q in queries:
    if q['split']=='train':continue
    mass=q['observed_neutral_mass']
    lo=int(np.searchsorted(masses,mass*(1-1e-5)))
    hi=int(np.searchsorted(masses,mass*(1+1e-5)))
    seen=set();full=[];removed=[]
    for smiles in pool['smiles'].slice(lo,hi-lo).to_pylist():
        item=mapping.get(smiles)
        if item is None or item['key'] in denied or item['key'] in seen:continue
        seen.add(item['key']);full.append(item['fp_index'])
        if item['key'] in independent-{q['key']}:
            removed.append(dict(key=item['key'],fp_index=item['fp_index']))
    stored=q['retrieved_candidates']
    excluded={v['fp_index'] for v in removed}
    if [x for x in full if x not in excluded]!=stored:
        raise ValueError('Reconstructed restricted candidates differ')
    rows.append(dict(key=q['key'],split=q['split'],restricted_candidates=len(stored),
                     full_candidates=len(full),removed=removed))
report=dict(status='passed',queries=len(rows),affected_queries=sum(bool(r['removed']) for r in rows),
    removed_total=sum(len(r['removed']) for r in rows),
    eval_affected=sum(r['split']=='eval' and bool(r['removed']) for r in rows),
    eval_removed=sum(len(r['removed']) for r in rows if r['split']=='eval'),rows=rows,
    model_evaluation_performed=False,known_pretrained_exposure=True)
(ROOT/'reports/candidate_head_candidate_restriction_audit_20261108.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
