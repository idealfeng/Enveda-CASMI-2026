import json,sys
from pathlib import Path
import pyarrow.parquet as pq
sys.path.insert(0,str(Path.cwd()))
from validation.metric import identity,heavy_atom_composition
root=Path('assets/kaggle/egehseyinca/enveda180-casmi26-reference-ccby4/v1')
refs=pq.read_table(root/'enveda180_hplus_hminus_references.parquet',columns=['reference_key','smiles','neutral_mass','adduct'])
aliases=pq.read_table(root/'enveda180_only_candidate_aliases.parquet')
print('METADATA',refs.num_rows,'refkeys',len(set(refs['reference_key'].to_pylist())),'smiles',len(set(refs['smiles'].to_pylist())),flush=True)
rows=aliases.to_pylist()
import time
t=time.monotonic()
for r in rows:
 r['official_identity']=identity(r['smiles'])
 r['heavy_composition']=json.dumps(heavy_atom_composition(r['smiles']))
print('ALIASES',len(rows),'identity_mismatch',sum(r['candidate_key']!=r['official_identity'] for r in rows),'seconds',time.monotonic()-t,flush=True)
out=Path('reports/external_reference_pilot_20261107')
(out/'aliases_canonical.json').write_text(json.dumps(rows),encoding='utf-8')
ids={r['official_identity'] for r in rows}
from collections import Counter
counts=Counter()
for key,adduct in zip(refs['reference_key'].to_pylist(),refs['adduct'].to_pylist()):
 if key in ids: counts[adduct]+=1
print('PUBLISHER_SOURCEONLY_REFROWS',dict(counts),flush=True)
cache=pq.read_table('runs/validation_pilot_v2_20261104/structure_identity_audit.parquet').to_pylist()
comps={r['heavy_composition'] for r in rows}
selected=[r for r in cache if r['heavy_composition'] in comps or r['heavy_composition'] is None]
print('TRAIN_COMPOSITION_CANDIDATES',len(selected),'unknowns',sum(r['heavy_composition'] is None for r in selected),flush=True)
(out/'train_composition_candidates.json').write_text(json.dumps(selected),encoding='utf-8')
