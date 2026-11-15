"""Freeze existing candidate lists for non-MSG active identities; no truth supplied to inference."""
from pathlib import Path
import csv
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation import metric

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    metric.assert_official_rdkit()
    out=ROOT/'runs/mist_active_evaluation_20261114';out.mkdir(parents=True,exist_ok=False)
    eligible=ROOT/'reports/mist_evaluation_20261114/eligible_active_ids.json'
    ids=json.loads(eligible.read_text())['outside_all_msg']
    source=ROOT/'runs/validation_flex_c2_20261105d/submission_reference.csv'
    with source.open(encoding='utf-8-sig',newline='') as f:original=list(csv.DictReader(f))
    by_id={r['molecule_id']:r for r in original};rows=[];changes=[]
    for mid in ids:
        r=by_id[mid];guesses=r['smiles'].split(';');seen=set();keep=[];dropped=[]
        for s in guesses:
            key=metric.identity(s)
            if key is None or key in seen:dropped.append(dict(smiles=s,reason='invalid' if key is None else 'duplicate_official_identity'))
            else:seen.add(key);keep.append(s)
        if not keep:raise ValueError('No legal candidates for existing query')
        rows.append(dict(molecule_id=mid,smiles=';'.join(keep)))
        changes.append(dict(molecule_id=mid,original_count=len(guesses),control_count=len(keep),dropped=dropped))
    target=out/'control_candidates.csv'
    with target.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['molecule_id','smiles']);writer.writeheader();writer.writerows(rows)
    raw=out/'original_candidates.csv'
    with raw.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['molecule_id','smiles']);writer.writeheader();writer.writerows(by_id[mid] for mid in ids)
    receipt=dict(status='frozen_candidate_control_ready',queries=len(rows),candidate_rows=sum(len(r['smiles'].split(';')) for r in rows),
                 source=str(source.relative_to(ROOT)),source_sha256=sha(source),eligible_sha256=sha(eligible),
                 control_sha256=sha(target),original_sha256=sha(raw),dedup=changes,
                 truth_loaded_by_this_preparation=False,selection='Outside all MSG raw identity families as already audited',
                 parent_is_exact_488=False,model_inference_executed=False,
                 boundary='Existing old Flex48 development lists; common official-identity dedup applied before any model comparison. This is not a clean full-stack CV or the exact .488 candidate set.')
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=receipt['status'],queries=receipt['queries'],candidates=receipt['candidate_rows'],control=str(target))))

if __name__=='__main__':main()
