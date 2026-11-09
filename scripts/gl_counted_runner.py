"""Pinned GL runner with read-only per-candidate finite-score counting."""
from functools import wraps
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import sys

try:
    from gl_score_observer import score_code
except ImportError:
    from forward_trace_runner import score_code

SOURCE_SHA='5c4f74313ac54263d05d987c39d012d81ec57c5f35e1095ecd49a5bcb6440fca'


def install_counts(module,source):
    contexts,active,counts={},{},{}
    original_plan=module.molecule_plan
    @wraps(original_plan)
    def plan(mol):
        value=original_plan(mol);contexts[id(value)]=str(mol['mid'])
        return value
    def observe(candidate,index,value,status):
        if value is not None and math.isfinite(value):active['values'].setdefault(candidate,[]).append(value)
    compiled,_=score_code(source)
    module._trace_observe=observe
    exec(compiled,module.__dict__)
    original_score=module.score_molecule
    @wraps(original_score)
    def score(plan_value,candidates,cache):
        active['values']={}
        result=original_score(plan_value,candidates,cache)
        this={}
        for candidate in candidates:
            values=active['values'].get(candidate,[])
            reconstructed=float(module.np.mean(values)) if values else None
            if reconstructed!=result[candidate]:raise ValueError('Observed values differ from original mean')
            this[candidate]=len(values)
        counts[contexts[id(plan_value)]]=this
        return result
    module.molecule_plan,module.score_molecule=plan,score
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--counts-json',required=True,type=Path)
    args,extra=parser.parse_known_args()
    path=args.package/'gl_runner.py';source=path.read_text()
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SOURCE_SHA:raise ValueError('Pinned GL runner differs')
    spec=importlib.util.spec_from_file_location('_original_gl_counted',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    counts=install_counts(module,source)
    result=module.main([str(args.package),str(args.input),str(args.output)]+extra)
    args.counts_json.write_text(json.dumps(counts,allow_nan=False)+'\n')
    return result


if __name__=='__main__':raise SystemExit(main())
