"""Freeze a truth-free two-query GL trace canary; never load or run a model."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import ast
import hashlib
import json
import math
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT/'runs/validation_flex_c2_20261105d/gl_work/gl_in.json'
PKG = ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier'
WHEELS = PKG.parent/'casmi26-iceberg/wheels'
SITE = ROOT/'runs/validation_flex_c2_20261105d/ice_site'
RUNNER_SHA = '5c4f74313ac54263d05d987c39d012d81ec57c5f35e1095ecd49a5bcb6440fca'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('All paths must stay in the D: workspace')
    return path


def linux(path):
    return '/mnt/d/Paper/casmi/'+inside(path).relative_to(ROOT).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'runs/exp003_gl_trace_canary_20261106')
    args = parser.parse_args()
    output = inside(args.output)
    if output == ROOT or output.is_relative_to(SOURCE.parents[1]):
        raise ValueError('A separate experiment directory is required')
    if output.exists():
        stem = output.name
        for index in range(2, 100):
            candidate = output.with_name(stem+'_'+str(index))
            if not candidate.exists():
                output = candidate
                break
        else:
            raise ValueError('No fresh experiment path available')
    import numpy as np
    from validation import metric
    rdkit_version = metric.assert_official_rdkit()
    runner = PKG/'gl_runner.py'
    if sha(runner) != RUNNER_SHA:
        raise ValueError('Upstream GL runner changed')
    # Use exactly the pure metadata helpers, without importing the model runner.
    names = {'_nce','spectrum_ce','ce_bucket','is_covered'}
    definitions = [node for node in ast.parse(runner.read_text(encoding='utf-8')).body
                   if isinstance(node,ast.FunctionDef) and node.name in names]
    if {node.name for node in definitions} != names:
        raise ValueError('Metadata helper source differs')
    helpers = dict(np=np,re=re,COV=('[M+H]+','[M+Na]+'))
    exec(compile(ast.Module(definitions,type_ignores=[]),'pinned-gl-metadata-only','exec'),helpers)
    source_sha = sha(SOURCE)
    molecules = json.loads(SOURCE.read_text(encoding='utf-8'))
    if len({str(m['mid']) for m in molecules}) != len(molecules):
        raise ValueError('Duplicate input molecule IDs')
    selected, details = [], []
    for mol in sorted(molecules,key=lambda item:str(item['mid'])):
        covered = []
        for index, spectrum in enumerate(mol.get('spectra') or []):
            if spectrum.get('adduct') != '[M+H]+' or not helpers['is_covered'](spectrum):
                continue
            bucket = helpers['ce_bucket'](helpers['spectrum_ce'](spectrum))
            if math.isfinite(bucket):
                covered.append((index,float(bucket)))
        buckets = sorted({bucket for _,bucket in covered})
        if len(covered)<2 or len(buckets)<2 or len(mol.get('cands') or [])<8:
            continue
        selected.append(dict(mol,cands=mol['cands'][:8]))
        details.append(dict(mid=str(mol['mid']),original_candidates=len(mol['cands']),selected_candidates=8,
            original_spectra=len(mol.get('spectra') or []),finite_ce_hplus_spectrum_indices=[i for i,_ in covered],
            distinct_ce_buckets=buckets))
        if len(selected)==2:
            break
    if len(selected)!=2:
        raise ValueError('Insufficient two-CE H+ queries in the existing source input')
    identities = {}
    for mol in selected:
        original = next(item for item in molecules if item['mid']==mol['mid'])
        if mol['spectra'] != original['spectra'] or mol['cands'] != original['cands'][:8]:
            raise ValueError('Input structure or original order changed')
        for smiles in mol['cands']:
            identity = metric.identity(smiles)
            if identity is None:
                raise ValueError('A selected original candidate lacks official2026 identity')
            identities[smiles] = identity
    marker = SITE/'.ice_site_ok'
    before_marker_sha = sha(marker)
    wheel_files = sorted(list(WHEELS.glob('*.whl.ice'))+list(WHEELS.glob('*.whl')))
    wanted = '\n'.join(path.name for path in wheel_files)
    ready = bool(wheel_files) and marker.read_text() == wanted
    output.mkdir(parents=True,exist_ok=False)
    site = SITE if ready else output/'ice_site'
    (output/'control').mkdir();(output/'trace').mkdir()
    input_path,identity_path = output/'input.json',output/'official_identities.json'
    input_path.write_text(json.dumps(selected,indent=2)+'\n',encoding='utf-8')
    identity_path.write_text(json.dumps(identities,indent=2)+'\n',encoding='utf-8')
    commands = {}
    for arm in ('control','trace'):
        command = [linux(ROOT/'.venv-linux/bin/python'),linux(ROOT/'scripts/forward_trace_runner.py'),
            linux(PKG),linux(input_path),linux(output/arm/'gl_out.json'),'--run-model',
            '--identity-map',linux(identity_path),'--site',linux(site),'--wheels',linux(WHEELS),
            '--device','cuda','--budget','0','--bs','32','--threads','2','--quiet']
        if arm=='trace':
            command += ['--trace-jsonl',linux(output/arm/'per_spectrum.jsonl')]
        script = '#!/usr/bin/env bash\nset -euo pipefail\nsource '+shlex.quote(linux(ROOT/'scripts/linux_env.sh'))+'\nexec '+shlex.join(command)+'\n'
        (output/(arm+'.sh')).write_text(script,encoding='utf-8',newline='\n')
        commands[arm] = 'wsl -d Ubuntu --exec bash '+shlex.quote(linux(output/(arm+'.sh')))
    if source_sha != sha(SOURCE) or before_marker_sha != sha(marker):
        raise ValueError('Original source input or old site marker changed')
    reread = json.loads(input_path.read_text())
    if reread != selected:
        raise ValueError('Serialized input did not preserve data exactly')
    report = dict(status='prepared_not_run',prepared_at_utc=datetime.now(timezone.utc).isoformat(),
        output_directory=str(output.relative_to(ROOT)),source_input=str(SOURCE.relative_to(ROOT)),
        source_input_sha256=source_sha,source_molecules=len(molecules),upstream_runner_sha256=RUNNER_SHA,
        wrapper_sha256=sha(ROOT/'scripts/forward_trace_runner.py'),
        preparation_script_sha256=sha(Path(__file__)),
        generated_script_sha256={arm:sha(output/(arm+'.sh')) for arm in ('control','trace')},
        selection='Sort mid ascending; first2 with>=2positiveH+ spectra in>=2distinct finite original CE buckets and>=8candidates; keep original first8candidates and all original spectra/field/order.',
        selected=details,input_sha256=sha(input_path),identity_sidecar_sha256=sha(identity_path),
        molecules=2,candidate_rows=sum(len(m['cands']) for m in selected),unique_candidate_smiles=len(identities),
        unique_official_identities=len(set(identities.values())),rdkit=rdkit_version,
        official_identity_source='validation.metric.identity over candidate structures only; no query truth read',
        site=dict(path=str(site.relative_to(ROOT)),reuses_old_site=ready,old_marker_sha256=before_marker_sha,
            expected_wheel_basenames=[p.name for p in wheel_files],marker_exactly_matches=ready,
            bootstrap_action='install_site returns before mkdir/pip/write' if ready else 'fresh offline install into new experiment site when parent runs model'),
        all_fields_and_spectrum_order_preserved=True,truth_or_locked250_read=False,
        model_or_gpu_called=False,download_performed=False,old_input_and_marker_unchanged=True,
        commands=commands,
        limits=['Canary validates observation equivalence only; it is not a performance evaluation.',
                'Run control then trace sequentially, budget0, compare full output/coverage and reconstruct means.',
                'Old site bootstrap is no-op only with the explicit wheel directory bound here and unchanged marker.'])
    (output/'prepare.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('status','output_directory','selected','candidate_rows',
        'unique_candidate_smiles','rdkit','site','commands')},indent=2))
    return 0


if __name__=='__main__':
    sys.dont_write_bytecode=True
    raise SystemExit(main())
