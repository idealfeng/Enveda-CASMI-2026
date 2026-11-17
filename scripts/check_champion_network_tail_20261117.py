"""Execute only the new tail on an already produced, SHA-bound two-query output.

The old mass/head audits remain historical evidence. No engine initialization,
model inference, labels, or efficacy metric is rerun or fabricated here.
"""
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import resource
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'runs/generation_production_20261113_r2/kaggle/working'
QUERY_COLUMNS = ['molecule_id','spectrum_id','instrument_type','adduct','collision_energy_ev',
                 'precursor_mz','ms2_mzs','ms2_normalized_intensities','ionization_mode']


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, default=ROOT/'submission/public_network_20261117/champion_network')
    parser.add_argument('--out', type=Path, default=ROOT/'runs/champion_network_tail_20261117')
    args = parser.parse_args()
    stage, out = args.stage.resolve(), args.out.resolve()
    if not out.is_relative_to(ROOT) or not stage.is_relative_to(ROOT):
        raise ValueError('All files must remain in the D workspace')
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    receipt = dict(status='started', started_at_utc=datetime.now(timezone.utc).isoformat(),
                   scope='actual new network -> AB -> final observer tail on historical production head output',
                   source_parent_run=OLD.relative_to(ROOT).as_posix(),
                   full_champion_initialization_executed=False, engine_or_model_inference_executed=False,
                   labels_read=False, efficacy_measured=False, score=None)
    try:
        sys.path.insert(0, str(ROOT/'.cache/rdkit-official-linux-2026033'))
        import pandas as pd
        import numpy as np
        from collections import Counter
        notebook_path = stage/'notebook.ipynb'
        notebook_pin = sha(notebook_path)
        notebook = read(notebook_path)
        if len(notebook['cells']) != 35:
            raise ValueError('Expected frozen optimized notebook with appended cells32..34')
        mass, head = read(OLD/'batch_variant_audit.json'), read(OLD/'guarded_tail_audit.json')
        if not all(a.get('status') == 'passed' and a.get('mode') == 'hidden_full' for a in (mass,head)):
            raise ValueError('Historical source stage audits not genuine completed production audits')
        if sha(OLD/'submission_external_control.csv') != head['csv_sha256']:
            raise ValueError('Historical head output does not bind head audit')
        if mass['csv_sha256'] != head['baseline_control_sha256']:
            raise ValueError('Historical mass-to-head source binding failed')
        work = out/'working'; work.mkdir()
        code = work/'p2s_code'; code.mkdir()
        inputs = out/'input'; inputs.mkdir()
        comp = inputs/'competitions/enveda-CASMI26-molecule-id-mass-spectra'; comp.mkdir(parents=True)
        shutil.copy2(OLD/'submission_external_control.csv', work/'submission.csv')
        for name in ['guarded_tail_audit.json','batch_variant_audit.json','frozen_candidate_evidence.parquet']:
            shutil.copy2(OLD/name, work/name)
        head_file_pin = sha(work/'guarded_tail_audit.json')
        # Save only observed query fields. The historical intermediate had labels;
        # they cannot enter this replay process or the raw AB matcher.
        observed = pd.read_parquet(OLD/'effective_query_spectra.parquet', columns=QUERY_COLUMNS)
        observed.to_parquet(comp/'test.parquet', index=False)
        libraries = read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/recipe.json')['files']
        bound = []
        for item in libraries:
            source = ROOT/'assets/kaggle'/item['ref']/('v'+str(item['version']))/item['file']
            if not source.is_file():
                candidates = [p for p in (OLD.parent/'input').rglob(item['file'])
                              if item['ref'].split('/')[1] in str(p)]
                if len(candidates) != 1:
                    raise ValueError('Cannot bind actual local source library: '+item['file'])
                source = candidates[0].resolve()
            if source.stat().st_size != item['bytes'] or sha(source) != item['sha256']:
                raise ValueError('Historical AB library fingerprint differs: '+item['file'])
            dest = inputs/item['ref']/item['file']; dest.parent.mkdir(parents=True,exist_ok=True)
            dest.symlink_to(source)
            bound.append(dict(file=item['file'],source=str(source.relative_to(ROOT)),sha256=item['sha256']))
        ids = pd.read_csv(work/'submission.csv',dtype=str,keep_default_na=False).molecule_id.tolist()
        scope = dict(ROOT=work,INPUT=inputs,COMP=comp,CODE=code,IS_RERUN=True,SAMPLE_IDS=ids,
                     BATCH_VARIANT_AUDIT=mass,GUARDED_TAIL_AUDIT=head,
                     Path=Path,json=json,hashlib=hashlib,shutil=shutil,pd=pd,np=np,Counter=Counter)
        steps = []
        for i in [32,33,34]:
            cell = notebook['cells'][i]['source'];cell=''.join(cell) if isinstance(cell,list) else cell
            tick = time.monotonic()
            print(json.dumps(dict(stage='actual_tail_cell_start',cell=i,seconds=time.monotonic()-start)),flush=True)
            with (out/f'cell{i}.log').open('w',encoding='utf-8') as log:
                with redirect_stdout(log),redirect_stderr(log):
                    exec(compile(cell,str(notebook_path)+f':cell{i}','exec'),scope)
            steps.append(dict(cell=i,source_sha256=hashlib.sha256(cell.encode()).hexdigest(),elapsed_seconds=time.monotonic()-tick))
            print(json.dumps(dict(stage='actual_tail_cell_completed',**steps[-1])),flush=True)
        # Parsing the actual file is mandatory; a passing in-memory dict cannot
        # cover malformed observer JSON or a final write that was never consumed.
        final = read(work/'champion_network_audit.json')
        if final['status'] != 'passed' or not all(v is True for v in final['checks'].values()):
            raise ValueError('Actual final observer did not pass')
        if sha(work/'guarded_tail_audit.json') != head_file_pin or read(work/'guarded_tail_audit.json') != head:
            raise ValueError('Historical head receipt was changed by replay')
        if sha(notebook_path) != notebook_pin:
            raise ValueError('Frozen notebook changed during replay')
        network = read(work/'network_audit.json');ab = read(work/'external_overlay_audit.json')
        receipt.update(status='passed_actual_tail_from_historical_head_to_final_csv',
                       notebook_sha256=notebook_pin,steps=steps,rows=len(ids),query_rows=len(observed),
                       query_columns=QUERY_COLUMNS,libraries=bound,
                       historical_mass_audit_sha256=sha(OLD/'batch_variant_audit.json'),
                       historical_head_audit_sha256=head_file_pin,
                       historical_head_csv_sha256=head['csv_sha256'],
                       actual_network_summary=network.get('actual_network_summary'),
                       network_audit_sha256=sha(work/'network_audit.json'),
                       AB_audit_sha256=sha(work/'external_overlay_audit.json'),
                       final_audit_sha256=sha(work/'champion_network_audit.json'),
                       final_csv_sha256=sha(work/'submission.csv'),
                       actual_AB_checks=ab['checks'],actual_final_checks=final['checks'],
                       historical_head_receipt_unchanged=True,
                       host_peak_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                       elapsed_seconds=time.monotonic()-start)
        save(out/'verification.json',receipt)
        print(json.dumps(receipt),flush=True)
    except BaseException as error:
        receipt.update(status='failed_preserved',error_type=type(error).__name__,error=str(error),
                       traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-start,
                       host_peak_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
        save(out/'failure.json',receipt)
        raise


if __name__ == '__main__':
    main()
