"""Prepare the original complete GL input for observation-only tracing; never run a model."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import shlex
import sys

from prepare_gl_trace_canary import ROOT,SOURCE,PKG,WHEELS,SITE,sha,inside,linux


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'runs/exp003_gl_trace_full_20261106')
    args=parser.parse_args();output=inside(args.output)
    if output==ROOT or output.is_relative_to(SOURCE.parents[1]):
        raise ValueError('Use a separate new experiment directory')
    if output.exists():
        original_name=output.name
        for index in range(2,100):
            proposed=output.with_name(original_name+'_'+str(index))
            if not proposed.exists():output=proposed;break
        else:raise ValueError('No fresh experiment directory available')
    from validation import metric
    rdkit=metric.assert_official_rdkit()
    original_bytes=SOURCE.read_bytes();source_hash=sha(SOURCE)
    items=json.loads(original_bytes)
    if len({str(m['mid']) for m in items})!=len(items):
        raise ValueError('Repeated query ID in original GL input')
    if len(items)!=45:
        raise ValueError('Expected original complete 45-query GL input')
    smiles=list(dict.fromkeys(c for m in items for c in m['cands']))
    if any(not isinstance(c,str) for c in smiles):
        raise ValueError('Non-string candidate in original input')
    identities={};unavailable=[]
    for candidate in smiles:
        key=metric.identity(candidate)
        if key is None:unavailable.append(candidate)
        else:identities[candidate]=key
    marker=SITE/'.ice_site_ok';marker_hash=sha(marker)
    wheels=sorted(list(WHEELS.glob('*.whl.ice'))+list(WHEELS.glob('*.whl')))
    wanted='\n'.join(p.name for p in wheels)
    if not wheels or marker.read_text()!=wanted:
        raise ValueError('Old site would not be bootstrap no-op; do not write it')
    output.mkdir(parents=True,exist_ok=False);(output/'trace').mkdir()
    input_path=output/'input.json';identity_path=output/'official_identities.json'
    input_path.write_bytes(original_bytes)
    identity_path.write_text(json.dumps(identities,indent=2)+'\n',encoding='utf-8')
    command=[linux(ROOT/'.venv-linux/bin/python'),linux(ROOT/'scripts/forward_trace_runner.py'),
        linux(PKG),linux(input_path),linux(output/'trace/gl_out.json'),'--run-model',
        '--identity-map',linux(identity_path),'--trace-jsonl',linux(output/'trace/per_spectrum.jsonl'),
        '--site',linux(SITE),'--wheels',linux(WHEELS),'--device','cuda','--budget','0',
        '--bs','32','--threads','4','--quiet']
    script='#!/usr/bin/env bash\nset -euo pipefail\nsource '+shlex.quote(linux(ROOT/'scripts/linux_env.sh'))+'\nexec '+shlex.join(command)+'\n'
    (output/'trace.sh').write_text(script,encoding='utf-8',newline='\n')
    if input_path.read_bytes()!=original_bytes or sha(SOURCE)!=source_hash or sha(marker)!=marker_hash:
        raise ValueError('Source input or site marker changed during preparation')
    if b'\r' in (output/'trace.sh').read_bytes():
        raise ValueError('Shell script must use LF')
    report=dict(status='prepared_not_run' if not unavailable else 'prepared_identity_gaps_not_run',
        prepared_at_utc=datetime.now(timezone.utc).isoformat(),output_directory=output.relative_to(ROOT).as_posix(),
        source_input=SOURCE.relative_to(ROOT).as_posix(),source_input_sha256=source_hash,input_sha256=sha(input_path),
        original_input_byte_identical=True,molecules=len(items),
        candidate_rows=sum(len(m['cands']) for m in items),unique_candidate_smiles=len(smiles),
        spectra=sum(len(m.get('spectra') or []) for m in items),query_order=[str(m['mid']) for m in items],
        identity_sidecar_sha256=sha(identity_path),official_identity_rdkit=rdkit,
        official_identity_count=len(identities),official_identity_unavailable=unavailable,
        official_identity_source='validation.metric.identity on candidate structures only; no query truth read',
        source_runner_sha256=sha(PKG/'gl_runner.py'),wrapper_sha256=sha(ROOT/'scripts/forward_trace_runner.py'),
        preparation_script_sha256=sha(Path(__file__)),script_sha256=sha(output/'trace.sh'),
        threads=4,batch_size=32,budget_seconds=0,
        site=dict(path=SITE.relative_to(ROOT).as_posix(),old_marker_sha256=marker_hash,
            expected_wheel_basenames=[p.name for p in wheels],marker_exactly_matches=True,
            bootstrap_action='explicit wheel directory matches marker; install_site returns before any write'),
        command='wsl -d Ubuntu --exec bash '+shlex.quote(linux(output/'trace.sh')),
        model_called=False,truth_or_locked250_read=False,download_performed=False,
        limits=['This is preparation only; it does not establish mean equivalence on the full input.',
            'Do not score truth or interpret traces as accuracy gain before a separate experiment is frozen.',
            'Unknown official identities remain explicit gaps; candidates and original input are not altered.'])
    (output/'prepare.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('status','output_directory','molecules','candidate_rows',
        'unique_candidate_smiles','spectra','official_identity_count','official_identity_unavailable',
        'input_sha256','command')},indent=2))
    return 0


if __name__=='__main__':
    sys.dont_write_bytecode=True
    raise SystemExit(main())
