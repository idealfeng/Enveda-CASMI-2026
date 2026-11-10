"""Read-only independent checks of DeepSeek generation artifacts; no inference."""
from pathlib import Path
import ast,base64,csv,hashlib,json,sys,zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from validation.metric import assert_official_rdkit,identity,reciprocal_rank

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def csvrows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert_official_rdkit()
    inputs={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'produre2').rglob('*') if p.is_file()}
    generation=csvrows(ROOT/'produre2/artifacts/step3_per_query.csv')
    summary=read(ROOT/'produre2/artifacts/step3_generation_summary.json')
    boolean=lambda s:s=='True'
    checks=dict(rows=len(generation)==summary['queries']==48,
        recovered=sum(boolean(x['recovered']) for x in generation)==summary['recovered_queries']==12,
        timeout=sum(boolean(x['timed_out']) for x in generation)==summary['timed_out_queries']==5,
        generated=sum(int(x['total_generated']) for x in generation)==summary['total_generated']==19232,
        valid=sum(int(x['valid_generated']) for x in generation)==summary['valid_generated'],
        novel=sum(int(x['novel_generated']) for x in generation)==summary['novel_generated'])
    base=csvrows(ROOT/'runs/validation_flex_c2_20261105d/baseline_submission.csv')
    truths={x['molecule_id']:x for x in csvrows(ROOT/'runs/validation_pilot_v2_20261104/truth.csv')}
    recovered={x['molecule_id'] for x in generation if boolean(x['recovered'])}
    rows=[];old=[];raw_oracle=[];truly_absent_only=[]
    for x in base:
        mid=x['molecule_id'];truth=truths[mid];arr=x['smiles'].split(';');tid=truth['official_identity']
        b=reciprocal_rank(tid,arr);keys=[identity(s) for s in arr]
        insert=mid in recovered and truth['smiles'] not in arr
        proposal=([truth['smiles']]+arr)[:25] if insert else arr
        g=reciprocal_rank(tid,proposal)
        missing=tid not in keys
        real_proposal=([truth['smiles']]+arr)[:25] if (mid in recovered and missing) else arr
        real=reciprocal_rank(tid,real_proposal)
        old.append(b);raw_oracle.append(g);truly_absent_only.append(real)
        if insert:rows.append(dict(molecule_id=mid,base_rank=keys.index(tid)+1 if tid in keys else None,
            truly_new_candidate_identity=missing,raw_string_inserted=True,
            before=b,after=g,duplicate_official_identity=len([identity(s) for s in proposal])!=len(set(identity(s) for s in proposal))))
    lineage={}
    a=ROOT/'third_party/canqiang_e006/engine_source_v4b/code/casmi'
    b=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-v4b-models/code/casmi'
    for name in ('engine.py','derive.py','chem.py'):
        lineage[name]=dict(experiment_import_sha256=digest(a/name),formal_asset_sha256=digest(b/name),exact_equal=(a/name).read_bytes()==(b/name).read_bytes())
    family=read(ROOT/'runs/validation_pilot_v2_20261104/identity_family_audit.json')
    targeted=[x for x in family['matching_pairs'] if x['official_identity'] in {t['official_identity'] for t in truths.values()}]
    alternate=[x for x in targeted if x['raw_inchikey14']!=x['official_identity']]
    report=dict(status='checked',artifact_internal_checks=checks,rdkit='2026.03.3',
        q4_oracle_recomputation=dict(base=sum(old)/len(old),raw_string_oracle=sum(raw_oracle)/len(old),
            delta=sum(raw_oracle)/len(old)-sum(old)/len(old),inserted_rows=rows,
            genuine_identity_absence_only_oracle=sum(truly_absent_only)/len(old),
            genuine_identity_absence_only_delta=sum(truly_absent_only)/len(old)-sum(old)/len(old),
            true_absent_recovered=sum(x['truly_new_candidate_identity'] for x in rows)),
        source_lineage=lineage,raw_key_vs_official_identity=dict(prior_audit_alternate_target_pairs=alternate),
        user_files_sha256_before=inputs,user_files_unchanged=all(digest(ROOT/p)==h for p,h in inputs.items()),
        actual_generation_rerun=False,actual_engine_ranking_rerun=False,hidden_or_locked_data_read=False)
    output=ROOT/'reports/produre_review_20261110/produre2_independent_checks.json'
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['artifact_internal_checks','q4_oracle_recomputation','source_lineage','raw_key_vs_official_identity','user_files_unchanged']},indent=2,ensure_ascii=False))

if __name__=='__main__':main()
