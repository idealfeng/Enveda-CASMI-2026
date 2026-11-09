"""Run actual staged late installer, scorer CLI and observer on three real queries."""
from pathlib import Path
import hashlib,json,sys,shutil
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_guarded_batch_20261109 import source
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    names=sys.argv[1:] or ['mass_guarded_oldhead_p3','mass_guarded_oldhead_p1','mass_guarded_v2mean_p7','mass_guarded_isomer_p7'];result={}
    for name in names:
        stage=ROOT/'submission/optimization_20261109'/name;nb=json.loads((stage/'notebook.ipynb').read_text());recipe=json.loads((stage/'recipe.json').read_text());out=ROOT/'runs/guarded_batch_actual_canary_20261109'/name;out.mkdir(parents=True,exist_ok=False);code=out/'code';code.mkdir()
        shutil.copy2(ROOT/'runs/validation_flex_c2_20261105d/p2s_code/neural_scores.py',code/'neural_scores.py')
        queries=pd.read_parquet(ROOT/'reports/learned_head_scorer_fixture_20261108/queries.parquet');queries.to_parquet(out/'effective_query_spectra.parquet',index=False)
        control=pd.read_csv(ROOT/'runs/validation_flex_c2_20261105d/submission.csv',dtype=str,keep_default_na=False);control=control[control.molecule_id.isin(set(queries.molecule_id))].copy();control.to_csv(out/'submission.csv',index=False)
        base=dict(status='passed',csv_sha256=sha(out/'submission.csv'));scope=dict(Path=Path,pd=pd,ROOT=out,CODE=code,OURS_BUNDLE=ROOT/'runs/guarded_tail_actual_canary_20261108/bundle',IS_RERUN=True,RUN_PIPELINE=True,PIPELINE_DONE=True,SAMPLE_IDS=control.molecule_id.tolist(),BATCH_VARIANT_AUDIT=base)
        for cell in nb['cells'][-2:]:exec(compile(source(cell),'actual_staged_late_cell','exec'),scope)
        report=scope['GUARDED_TAIL_REPORT'];observer=scope['GUARDED_TAIL_AUDIT'];after=pd.read_csv(out/'submission.csv',dtype=str,keep_default_na=False);prefix=recipe['configuration']['protected_prefix']
        checks=dict(actual_model_invoked=report['model_invoked'],actual_applied=report['status']=='applied',runtime_checks=all(report['checks'].values()),observer_checks=all(observer['checks'].values()),all_three_queries=report['eligible_queries']==3,exact_protected_prefix=all(a.split(';')[:prefix]==b.split(';')[:prefix] for a,b in zip(control.smiles,after.smiles)),actual_scored_order=observer['checks']['actual_scored_order_consumed'])
        result[name]=dict(status='passed' if all(checks.values()) else 'failed',stage_sha256=sha(stage/'notebook.ipynb'),checks=checks,queries=len(control),spectra=len(queries),changed_queries=report['changed_queries'],score_mode=report['score_mode'],known_pretrained_exposure=True,training_performed=False)
        (out/'verification.json').write_text(json.dumps(result[name],indent=2)+'\n');print(json.dumps(result[name]),flush=True)
        if not all(checks.values()):raise RuntimeError('Actual canary failed')
    output=ROOT/'reports/guarded_batch_actual_canary_20261109.json';output.write_text(json.dumps(dict(status='passed',branches=result),indent=2)+'\n')
if __name__=='__main__':main()
