"""Observe GLACIER's per-spectrum scores without changing its prediction or mean-scoring code.

Default is plan-only. --self-test uses a synthetic cache, never a model. Model execution
requires --run-model; add --trace-jsonl to enable observation, omit it for the control.
"""
from pathlib import Path
from functools import wraps
import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier'
SOURCE_SHA = '5c4f74313ac54263d05d987c39d012d81ec57c5f35e1095ecd49a5bcb6440fca'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('All paths must remain inside the D: workspace')
    return path


def safe_json(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json(v) for v in value]
    return value


class ObserveScore(ast.NodeTransformer):
    """Add only index enumeration and read-only observations at three exact sites."""
    def __init__(self):
        self.counts = dict(plan_loop=0, missing_prediction=0, similarity=0)

    @staticmethod
    def observation(value, status):
        return ast.Expr(ast.Call(ast.Name('_trace_observe', ast.Load()),
            [ast.Name('c', ast.Load()), ast.Name('_trace_plan_index', ast.Load()), value, ast.Constant(status)], []))

    def visit_For(self, node):
        node = self.generic_visit(node)
        if isinstance(node.iter, ast.Name) and node.iter.id == 'plan':
            if ast.dump(node.target, include_attributes=False) != ast.dump(ast.parse('qm, qp, ad, ins, ceb = ()').body[0].targets[0], include_attributes=False):
                raise ValueError('Unexpected upstream spectrum loop target')
            node.target = ast.Tuple([ast.Name('_trace_plan_index', ast.Store()), node.target], ast.Store())
            node.iter = ast.Call(ast.Name('enumerate', ast.Load()), [ast.Name('plan', ast.Load())], [])
            self.counts['plan_loop'] += 1
        return node

    def visit_If(self, node):
        node = self.generic_visit(node)
        if (isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                and node.test.left.id == 'pr' and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], ast.Is) and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value is None):
            if len(node.body) != 1 or not isinstance(node.body[0], ast.Continue):
                raise ValueError('Unexpected upstream missing-prediction handling')
            node.body.insert(0, self.observation(ast.Constant(None), 'prediction_missing'))
            self.counts['missing_prediction'] += 1
        return node

    def visit_Assign(self, node):
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 's'
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id == 'entropy_sim'):
            self.counts['similarity'] += 1
            return [node, self.observation(ast.Name('s', ast.Load()), 'similarity')]
        return node


class RemoveObservations(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == '_trace_observe':
            return None
        return self.generic_visit(node)

    def visit_For(self, node):
        node = self.generic_visit(node)
        if isinstance(node.target, ast.Tuple) and isinstance(node.target.elts[0], ast.Name) and node.target.elts[0].id == '_trace_plan_index':
            node.target = node.target.elts[1]
            node.iter = ast.Name('plan', ast.Load())
        return node


def score_code(source):
    original = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'score_molecule')
    patched = ast.parse(ast.unparse(original)).body[0]
    change = ObserveScore()
    patched = ast.fix_missing_locations(change.visit(patched))
    if change.counts != dict(plan_loop=1, missing_prediction=1, similarity=1):
        raise ValueError('Unexpected upstream score shape')
    restored = ast.fix_missing_locations(RemoveObservations().visit(ast.parse(ast.unparse(patched)).body[0]))
    if ast.dump(restored, include_attributes=False) != ast.dump(original, include_attributes=False):
        raise ValueError('Observation stripping did not restore the upstream AST exactly')
    return compile(ast.Module([patched], type_ignores=[]), 'observed-original-gl-score', 'exec'), original


def self_test(source):
    import numpy as np
    code, original = score_code(source)
    calls, observed = [], []
    plan = [(1.0, None, 'a', 'QTOF', 20.0), (2.0, None, 'a', 'QTOF', 30.0),
            (3.0, None, 'a', 'QTOF', float('nan'))]
    cache = {('first', 'a', 'QTOF', 20.0): (0.1, None),
             ('second', 'a', 'QTOF', 20.0): (0.2, None),
             ('second', 'a', 'QTOF', 30.0): (float('nan'), None)}
    for ce in (20.0, 40.0, 60.0):
        cache[('first', 'a', 'QTOF', ce)] = (ce/100, None)

    def similarity(qm, qp, pm, pp, tol, ppm):
        calls.append((qm, pm))
        return qm+pm

    common = dict(np=np, SUM_CE=(20.0, 40.0, 60.0), FLOOR=0.002, TOPK=256,
        POWER=1.0, ENTW=True, TOL=0.01, PPM=20.0,
        prep_query=lambda pm, pp, *args: (pm, pp), entropy_sim=similarity,
        merge=lambda parts: (sum(p[0] for p in parts), None))
    baseline = dict(common)
    exec(compile(ast.Module([original], type_ignores=[]), 'unmodified-original-gl-score', 'exec'), baseline)
    control = baseline['score_molecule'](plan, ['first','second'], cache)
    original_calls = list(calls); calls.clear()
    current = dict(common, _trace_observe=lambda *values: observed.append(values))
    exec(code, current)
    result = current['score_molecule'](plan, ['first','second'], cache)
    checks = dict(exact_aggregate=result == control, exact_similarity_call_order=calls == original_calls,
        all_candidate_spectrum_pairs_observed=len(observed) == 6,
        missing_prediction_observed=any(x[-1] == 'prediction_missing' for x in observed),
        nonfinite_observed=any(x[-1] == 'similarity' and not math.isfinite(x[2]) for x in observed))
    if not all(checks.values()):
        raise ValueError('Synthetic observer equivalence failed')
    return dict(status='passed', model_loaded=False, checks=checks,
        original_ast_restored_after_stripping_observation=True)


def install_trace(module, source, stream, identities):
    contexts, active = {}, {}
    stats = dict(coverage_events=0, score_events=0, missing_prediction_events=0,
                 nonfinite_events=0, aggregate_exact_checks=0)

    def write(record):
        stream.write(json.dumps(safe_json(record), allow_nan=False, separators=(',', ':'))+'\n')

    original_plan = module.molecule_plan
    @wraps(original_plan)
    def plan(mol):
        value = original_plan(mol)
        covered = []
        for index, sp in enumerate(mol.get('spectra') or []):
            keep = module.is_covered(sp)
            peaks = {key: sp.get(key) for key in ('mz','it','prec','adduct','mode')}
            record = dict(mid=str(mol.get('mid')), spectrum_index=index,
                spectrum_id=sp.get('spectrum_id',sp.get('id')),
                spectrum_content_sha256=hashlib.sha256(json.dumps(peaks,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                adduct=sp.get('adduct'), ionization_mode=sp.get('mode'), instrument_raw=sp.get('instrument'),
                ce_ev=sp.get('ce_ev'), ce_orig=sp.get('ce_orig'), ce_units=sp.get('ce_units'),
                covered=bool(keep), coverage_reason='covered' if keep else 'upstream_is_covered_false')
            if keep:
                _, _, adduct, instrument, bucket = value[len(covered)]
                record.update(plan_index=len(covered), adduct=adduct, instrument_token=instrument,
                              ce_bucket=bucket, prediction_mode='single_ce' if math.isfinite(bucket) else 'merged_20_40_60')
                covered.append(record)
            write(dict(event='spectrum_coverage', **record));stats['coverage_events'] += 1
        if len(covered) != len(value):
            raise ValueError('Coverage metadata differs from upstream plan')
        contexts[id(value)] = covered
        return value

    def observe(candidate, index, score, status):
        metadata = active['spectra'][index]
        finite = score is not None and math.isfinite(score)
        if finite:
            active['scores'].setdefault(candidate,[]).append(score)
        kind = status if status == 'prediction_missing' else 'scored' if finite else 'nonfinite_similarity'
        write(dict(event='candidate_spectrum_score', **metadata, candidate_smiles=candidate,
            candidate_official_identity=identities.get(candidate), score=float(score) if finite else None, status=kind))
        stats['score_events'] += 1
        stats['missing_prediction_events'] += int(status == 'prediction_missing')
        stats['nonfinite_events'] += int(status != 'prediction_missing' and not finite)

    code, _ = score_code(source)
    module._trace_observe = observe
    exec(code,module.__dict__)
    observed_score = module.score_molecule
    @wraps(observed_score)
    def score(plan_value, candidates, cache):
        active.update(spectra=contexts[id(plan_value)],scores={})
        result = observed_score(plan_value,candidates,cache)
        for candidate in candidates:
            values = active['scores'].get(candidate,[])
            reconstructed = float(module.np.mean(values)) if values else None
            if reconstructed != result[candidate]:
                raise ValueError('Trace scores do not reconstruct the original mean exactly')
            stats['aggregate_exact_checks'] += 1
        stream.flush()
        return result
    module.molecule_plan, module.score_molecule = plan, score
    return stats, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pkg', nargs='?', type=Path, default=PKG)
    parser.add_argument('inp', nargs='?', type=Path)
    parser.add_argument('out', nargs='?', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--run-model', action='store_true')
    parser.add_argument('--trace-jsonl', type=Path)
    parser.add_argument('--identity-map', type=Path, help='Optional SMILES -> official2026IK14 map; never computed with scorer RDKit2025')
    args, extra = parser.parse_known_args()
    pkg = inside(args.pkg); original = pkg/'gl_runner.py'
    if sha(original) != SOURCE_SHA:
        raise ValueError('Upstream GL runner differs from the pinned source')
    source = original.read_text(encoding='utf-8')
    if args.self_test:
        print(json.dumps(self_test(source),indent=2));return 0
    score_code(source)
    if not args.run_model:
        print(json.dumps(dict(status='plan_only',model_loaded=False,source_sha256=SOURCE_SHA,
            execution_requires='--run-model',trace_enabled=bool(args.trace_jsonl),
            identity_note='Pass an official2026 sidecar to populate candidate_official_identity.'),indent=2));return 0
    if args.inp is None or args.out is None:
        parser.error('Explicit existing input and new output are required for --run-model')
    inp, out = inside(args.inp), inside(args.out)
    trace = inside(args.trace_jsonl) if args.trace_jsonl else None
    reserved = {out, Path(str(out)+'.meta.json'), Path(str(out)+'.trace_run.json')}
    if trace in reserved:
        raise ValueError('Trace and standard output/metadata paths must differ')
    if not inp.is_file():
        raise ValueError('Existing cached runner input is required')
    if out.exists() or (trace and trace.exists()):
        raise ValueError('Use fresh output/trace paths; existing runs are immutable')
    out.parent.mkdir(parents=True,exist_ok=True)
    if trace:trace.parent.mkdir(parents=True,exist_ok=True)
    identities = json.loads(inside(args.identity_map).read_text()) if args.identity_map else {}
    if any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch('[A-Z]{14}',v) for k,v in identities.items()):
        raise ValueError('Invalid official identity sidecar')
    # Reuse an existing D-backed offline site unless the caller explicitly supplies one.
    if not any(token == '--site' or token.startswith('--site=') for token in extra):
        extra += ['--site',str(ROOT/'runs/validation_flex_c2_20261105d/ice_site')]
    for flag in ('--site','--wheels','--ckpt'):
        for index, token in enumerate(extra):
            if token == flag:
                if index+1 >= len(extra):raise ValueError('Missing path after '+flag)
                value = extra[index+1]
            elif token.startswith(flag+'='):
                value = token.split('=',1)[1]
            else:
                continue
            if value != 'none':inside(value)
    spec = importlib.util.spec_from_file_location('_pinned_gl_trace_upstream',original)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    stream = trace.open('x',encoding='utf-8') if trace else None
    stats = None
    try:
        if stream:
            stats,write = install_trace(module,source,stream,identities)
            write(dict(event='run_start',source_sha256=SOURCE_SHA,input_sha256=sha(inp),
                wrapper_sha256=sha(Path(__file__)),official_identity_sidecar=bool(identities),
                identity_map_sha256=sha(inside(args.identity_map)) if args.identity_map else None,
                note='Trace adds CPU/I/O overhead; use sufficient budget and audit full coverage.'))
        rc = module.main([str(pkg),str(inp),str(out)]+extra)
        meta_path = Path(str(out)+'.meta.json')
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        healthy = rc == 0 and meta.get('status') == 'ok' and not meta.get('errors')
        record = dict(status='complete' if healthy else 'upstream_not_healthy',source_sha256=SOURCE_SHA,
            input_sha256=sha(inp),trace_enabled=bool(stream),trace_statistics=stats,
            upstream_status=meta.get('status'),output_sha256=sha(out) if out.exists() else None,
            model_training_performed=False)
        Path(str(out)+'.trace_run.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        if stream:write(dict(event='run_end',**record))
        print(json.dumps(record,indent=2));return 0 if healthy else 1
    finally:
        if stream:stream.close()


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    for key,relative in [('TMPDIR','.cache/tmp-linux'),('TMP','.cache/tmp-linux'),('TEMP','.cache/tmp-linux'),
        ('PIP_CACHE_DIR','.cache/pip-linux'),('XDG_CACHE_HOME','.cache/xdg'),('TORCH_HOME','.cache/torch'),
        ('HF_HOME','.cache/huggingface'),('MPLCONFIGDIR','.cache/matplotlib'),('NUMBA_CACHE_DIR','.cache/numba-linux'),
        ('TRITON_CACHE_DIR','.cache/triton'),('CUDA_CACHE_PATH','.cache/cuda')]:
        path=ROOT/relative;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
    raise SystemExit(main())
