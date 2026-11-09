"""Compare locally calculated active smoke rows to a version-bound public output."""
from pathlib import Path
import argparse
import functools
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reference',type=Path,required=True,help='Version-bound active-row CSV (usually 12 molecules)')
parser.add_argument('--actual',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--metric-identity',action='store_true')
args=parser.parse_args()
reference=pd.read_csv(args.reference,dtype=str)
actual=pd.read_csv(args.actual,dtype=str)
for name,frame in [('reference',reference),('actual',actual)]:
    if not {'molecule_id','smiles'}.issubset(frame.columns) or frame[['molecule_id','smiles']].isna().any().any() or frame.molecule_id.duplicated().any():
        raise ValueError(f'Invalid {name} CSV')
actual=actual.set_index('molecule_id')
rows=[]
if args.metric_identity:
    from validation import metric
    metric.assert_official_rdkit()
    @functools.lru_cache(maxsize=10000)
    def key(smiles):
        value=metric.identity(smiles)
        if value is None:
            raise ValueError(f'Unparseable candidate: {smiles}')
        return value
for row in reference.itertuples(index=False):
    if row.molecule_id not in actual.index:
        raise ValueError(f'Missing active molecule: {row.molecule_id}')
    expected=row.smiles.split(';')
    observed=actual.loc[row.molecule_id,'smiles'].split(';')
    if not 1<=len(observed)<=25:
        raise ValueError(f'Invalid guess count for {row.molecule_id}')
    item={'molecule_id':row.molecule_id,'reference_guesses':len(expected),'actual_guesses':len(observed),
          'top1_exact':expected[0]==observed[0],'candidate_set_exact':set(expected)==set(observed),
          'ranking_exact':expected==observed}
    if args.metric_identity:
        e=list(map(key,expected));o=list(map(key,observed))
        item.update(top1_identity=e[0]==o[0],candidate_set_identity=set(e)==set(o),ranking_identity=e==o)
    rows.append(item)
checks=['top1_exact','candidate_set_exact','ranking_exact']
if args.metric_identity:
    checks+=['top1_identity','candidate_set_identity','ranking_identity']
report={'scope':'Active visible-placeholder rows only; this does not reproduce hidden leaderboard score.',
        'reference':str(args.reference),'actual':str(args.actual),'active_molecules':len(rows),
        'reference_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        'actual_sha256':hashlib.sha256(args.actual.read_bytes()).hexdigest(),
        'actual_output_rows':len(actual),
        'metric_rdkit':metric.assert_official_rdkit() if args.metric_identity else None,
        'metric_source':{'url':metric.OFFICIAL_METRIC_URL,'version':metric.OFFICIAL_METRIC_VERSION,
                         'sha256':metric.OFFICIAL_SOURCE_SHA256,
                         'stereochemistry_removed_before_tautomer_canonicalization':True} if args.metric_identity else None,
        'matching_molecules':{name:sum(x[name] for x in rows) for name in checks},'rows':rows}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
