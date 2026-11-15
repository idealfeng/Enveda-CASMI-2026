"""Inspect inert pickle opcodes only, without unpickling, Torch import or tensor loading."""
from pathlib import Path
import json,pickletools,re,zipfile

ROOT=Path(__file__).resolve().parents[1]
weight=ROOT/'assets/kaggle/agentili/casmi26-fr-reranker-blend/v2/fr_model.pt'
with zipfile.ZipFile(weight) as archive:
    names=[x.filename for x in archive.infolist() if x.filename.endswith('/data.pkl') or x.filename=='data.pkl']
    if len(names)!=1 or archive.getinfo(names[0]).file_size>2*1024*1024:
        raise ValueError('Unexpected Torch archive metadata')
    raw=archive.read(names[0])
ops=[dict(op=op.name,arg=arg,position=position) for op,arg,position in pickletools.genops(raw)]
args_at=next((i for i,x in enumerate(ops) if x['arg']=='args'),None)
strings=[x['arg'] for x in ops if isinstance(x['arg'],str)]
record=dict(scope='Static pickle opcode inspection only; no unpickle/model/Torch/GPU',metadata_bytes=len(raw),
    args_excerpt=ops[args_at:args_at+160] if args_at is not None else [],
    provenance_strings=[s for s in strings if re.search(r'NIST|train|split|licen|data|nist|epoch|holdout',s)],
    keys_tail=ops[-35:])
(ROOT/'reports/optimization_20261113/massbank_frnet_checkpoint_metadata.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
