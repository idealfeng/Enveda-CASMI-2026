"""Call the exact original v2 mean scorer and bind its actual output to inputs."""
from pathlib import Path
import hashlib,importlib.util,json,sys
import numpy as np
import pandas as pd

V2_SHA='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'
BASE_SHA='cb9e4d6732992e3310e951533fd0c644d3b515134ad03768c35e5a86551267d2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def score(bundle,checkpoint,evidence,queries,output,device='cuda'):
    source=Path(__file__).resolve().parent/'neural_scores_original.py'
    if sha(source)!=BASE_SHA or sha(Path(bundle)/checkpoint)!=V2_SHA:raise ValueError('Frozen scorer or encoder differs')
    spec=importlib.util.spec_from_file_location('_actual_original_v2_scorer',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.score(bundle,checkpoint,evidence,queries,output,device)
    frame=pd.read_parquet(output);inputs=pd.read_parquet(evidence)
    if len(frame)!=len(inputs) or frame.duplicated(['molecule_id','smiles']).any():raise ValueError('Original scorer changed keys')
    if set(zip(frame.molecule_id.astype(str),frame.smiles))!=set(zip(inputs.molecule_id.astype(str),inputs.smiles)):raise ValueError('Scored key coverage differs')
    if not np.isfinite(frame.neural_score.astype(float)).all():raise ValueError('Non-finite scorer output')
    failures=json.loads(Path(str(output)+'.errors.json').read_text())
    covered=frame.neural_ok.astype(bool)
    audit=dict(status='passed',role='frozen_v2_mean',head_applied=False,encoder_sha256=V2_SHA,heads=[],
        baseline_scorer_sha256=BASE_SHA,evidence_sha256=sha(evidence),queries_sha256=sha(queries),output_sha256=sha(output),
        input_rows=len(inputs),output_rows=len(frame),scored_candidate_rows=int(covered.sum()),
        scored_queries=int(frame.loc[covered,'molecule_id'].nunique()),errors=failures,training_performed=False)
    Path(str(output)+'.head_audit.json').write_text(json.dumps(audit,indent=2)+'\n')

if __name__=='__main__':score(*sys.argv[1:])
