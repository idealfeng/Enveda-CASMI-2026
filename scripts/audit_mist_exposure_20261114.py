"""Compare existing active development identities to official MIST MSG cache splits."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    source=ROOT/'assets/research/mist_msg_20261114/exposure/metadata'
    split_ids={};counts={};pins={}
    for split in ('train','val','test'):
        paths=list(source.glob('data/compact/msg/'+split+'/*/structure_ids.npy'))
        if not paths:raise ValueError('Missing official split identity arrays')
        ids=set();rows=0
        for p in paths:
            a=np.load(p,allow_pickle=False,mmap_mode='r')
            if a.ndim!=1 or a.dtype.kind!='U':raise ValueError('Unexpected identity array contract')
            rows+=len(a);ids.update(a.tolist());pins[p.relative_to(ROOT).as_posix()]=sha(p)
        if not all(len(x)==14 and x.isalpha() for x in ids):raise ValueError('Unexpected raw identity')
        split_ids[split]=ids;counts[split]=dict(rows=rows,unique_raw_keys=len(ids))
    root=ROOT/'runs/validation_pilot_v2_20261104'
    families=json.loads((root/'class2_exclusion_keys.json').read_text())['identity_by_raw_key']
    reverse={}
    for raw,officials in families.items():
        for official in officials:reverse.setdefault(official,set()).add(raw)
    with (root/'truth.csv').open(encoding='utf-8-sig',newline='') as f:truth=list(csv.DictReader(f))
    rows=[]
    for t in truth:
        identity=t['official_identity'];family=reverse.get(identity,set())|{identity}
        hits={split:sorted(family&ids) for split,ids in split_ids.items()}
        rows.append(dict(molecule_id=t['molecule_id'],panel=t['panel'],official_identity=identity,
                         known_raw_family=sorted(family),membership=hits,
                         no_known_train_or_selection_exposure=not(hits['train'] or hits['val']),
                         outside_all_msg_known_families=not any(hits.values())))
    result=dict(status='completed_split_membership_audit',source_rows=counts,source_pins=pins,
                truth_sha256=sha(root/'truth.csv'),family_map_sha256=sha(root/'class2_exclusion_keys.json'),
                queries=len(rows),known_train_or_val_exposed=sum(not r['no_known_train_or_selection_exposure'] for r in rows),
                no_known_train_or_val_exposure=sum(r['no_known_train_or_selection_exposure'] for r in rows),
                outside_all_msg_known_families=sum(r['outside_all_msg_known_families'] for r in rows),
                rows=rows,model_or_reference_rerun=False,labels_used_for_inference=False,
                limitation='Exact raw InChIKey14 membership plus known official identity families from existing validation. Unlisted tautomer aliases in MSG may still exist; absence is not a universal proof of no pretraining exposure. Existing baseline has its own known pretrained exposure.')
    out=ROOT/'reports/mist_evaluation_20261114';out.mkdir(parents=True,exist_ok=True)
    (out/'active48_exposure.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (out/'eligible_active_ids.json').write_text(json.dumps(dict(no_known_train_or_val=[r['molecule_id'] for r in rows if r['no_known_train_or_selection_exposure']],outside_all_msg=[r['molecule_id'] for r in rows if r['outside_all_msg_known_families']]),indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','queries','known_train_or_val_exposed','no_known_train_or_val_exposure','outside_all_msg_known_families']}))

if __name__=='__main__':main()
