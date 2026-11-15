"""Exercise genuine negative-only query fallback without loading MIST tensors."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import mist_casmi_adapter_20261114 as adapter
import pandas as pd


def main():
    root=ROOT/'runs/mist_negative_fallback_20261114'
    root.mkdir(exist_ok=False,parents=True)
    tests=list((adapter.WORK.parent/'input').rglob('test.parquet'))
    assert len(tests)==1
    frame=pd.read_parquet(tests[0],columns=adapter.OFFICIAL_COLUMNS)
    frame=frame.loc[frame.ionization_mode.astype(str).str.lower()=='negative'].copy()
    baseline=pd.read_csv(adapter.WORK/'submission.csv',dtype=str,keep_default_na=False)
    assert set(frame.molecule_id)==set(baseline.molecule_id)
    frame.to_parquet(root/'official_negative_spectra.parquet',index=False)
    result=adapter.run(SimpleNamespace(output=root/'component',candidates=adapter.WORK/'submission.csv',
        test=root/'official_negative_spectra.parquet',device='cuda',prepare_only=False))
    assert result['status']=='passed_supported_input_fallback_only'
    assert result['actual_model_executed'] is False
    assert not (root/'component/actual_checkpoint_metadata.json').exists()
    assert all(result['checks'].values())
    out=dict(status='passed_actual_negative_only_fallback',queries=len(baseline),negative_spectra=len(frame),
             checks=result['checks'],adapter_sha256=adapter.sha(adapter.__file__),model_tensors_loaded=False,
             evidence='runs/mist_negative_fallback_20261114/component/verification.json')
    (ROOT/'reports/mist_casmi_20261114/negative_fallback_verification.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out))


if __name__=='__main__':main()
