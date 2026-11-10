"""Isolated matching-contract tests; no truth, GPU, network, or user artifacts."""
from __future__ import annotations
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import enveda_matching_20261110 as E


def original_cosine():
    stage=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
    notebook=json.loads((stage/'notebook.ipynb').read_text())
    cell=notebook['cells'][-1]['source']
    cell=''.join(cell) if isinstance(cell,list) else cell
    tree=ast.parse(cell)
    assignment=next(x for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_external_payloads' for t in x.targets))
    payloads=ast.literal_eval(assignment.value)
    raw=base64.b64decode(payloads['alex_v12_external_function.py'])
    recipe=json.loads((stage/'recipe.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==recipe['original_function_sha256']
    f=next(x for x in ast.walk(ast.parse(raw)) if isinstance(x,ast.FunctionDef) and x.name=='calc_cosine')
    module=ast.Module(body=[f],type_ignores=[]);ast.fix_missing_locations(module)
    scope={'np':np};exec(compile(module,'actual_pinned_Alex_cosine','exec'),scope)
    return scope['calc_cosine']


def reference(smiles='CCO', mass=100., adduct='[M+H]+', mz=None, intensity=None, key='fixture'):
    return dict(reference_key=key,smiles=smiles,neutral_mass=mass,adduct=adduct,
        ms2_mzs=[10.,20.,30.,40.,50.] if mz is None else mz,
        ms2_normalized_intensities=[1.,.8,.6,.4,.2] if intensity is None else intensity)


def query(prec=101.007276,adduct='[M+H]+',mode=1,mz=None,intensity=None):
    return dict(mz=np.array([10.,20.,30.,40.,50.] if mz is None else mz,dtype=np.float64),
        it=np.array([1.,.8,.6,.4,.2] if intensity is None else intensity,dtype=np.float64),
        prec=prec,adduct=adduct,mode=mode)


def write_library(path,rows):
    pq.write_table(pa.Table.from_pylist(rows),path)
    return dict(expected_sha256=E.sha(path),expected_bytes=path.stat().st_size)


def run():
    cosine=original_cosine();checks={}
    with tempfile.TemporaryDirectory(prefix='E-matching-',dir=ROOT/'.cache/tmp-linux') as folder:
        folder=Path(folder);path=folder/'library.parquet'
        rows=[reference('CCO',mass=100.0005),reference('CCN'),
              reference('CCS',adduct='[M-H]-'),
              reference('CCC',adduct='[M+Na]+'),reference('CCCl',mass=float('nan')),
              reference('',key='blank'),reference('CCCC',mz=[10.,20.],intensity=[1.,1.]),
              reference('CCF',mass=500.)]
        expected=write_library(path,rows)
        qs={'positive':[query()], 'negative':[query(prec=98.992724,adduct='[M-H]-',mode=-1)]}
        hits,audit=E.score_enveda(qs,{},path,cosine,**expected)
        checks['actual_original_cosine_called']=audit['scored_pairs']>0
        checks['same_adduct_positive_match']=hits['positive']['adduct']=='[M+H]+' and hits['positive']['mode']==1
        checks['same_adduct_negative_match']=hits['negative']['adduct']=='[M-H]-' and hits['negative']['mode']==-1
        checks['stable_precursor_tie']=hits['positive']['reference_index']==1
        checks['full_metadata_scan']=audit['rows_scanned']==len(rows)==audit['source_rows_total']
        checks['peak_loading_bounded_to_windows']=audit['selected_reference_rows']<len(rows) and audit['usable_selected_reference_rows']<len(rows)
        checks['bad_mass_skipped']=audit['reference_skip_reasons']['invalid_reference_neutral_mass']==1
        checks['unsupported_reference_adduct_skipped']=audit['reference_skip_reasons']['unsupported_reference_adduct']==1
        checks['short_peaks_skipped']=audit['reference_skip_reasons']['short_reference_peaks']==1
        checks['blank_smiles_skipped']=audit['reference_skip_reasons']['empty_reference_smiles']==1
        checks['finite_serializable_audit']=bool(json.dumps(audit,allow_nan=False))
        h1,a1=E.score_enveda(qs,{},path,cosine,batch_size=1,**expected)
        checks['batch_boundary_invariance']=h1==hits and a1['query_best']==audit['query_best'] and a1['max_batch_rows']==1
        hprotected,aprotected=E.score_enveda(qs,{'positive':.90,'negative':1.},path,cosine,**expected)
        checks['original_library_protection']=not hprotected and not aprotected['scan_performed'] and aprotected['query_preparation']['eligible_queries']==0
        hbad,abad=E.score_enveda({'wrong':[query(adduct='[M+Na]+')],
            'wrong_mode':[query(mode=-1)],'bad_prec':[query(prec=float('nan'))],
            'bad_peaks':[query(intensity=[1.,float('inf'),1.,1.,1.])]}, {},path,cosine,**expected)
        checks['unsupported_query_adduct_skipped']=abad['query_preparation']['skipped_spectra']['unsupported_query_adduct']==1
        checks['adduct_mode_mismatch_skipped']=abad['query_preparation']['skipped_spectra']['query_adduct_mode_mismatch']==1
        checks['nonfinite_query_precursor_skipped']=abad['query_preparation']['skipped_spectra']['invalid_query_precursor']==1
        checks['nonfinite_query_peaks_skipped']=abad['query_preparation']['skipped_spectra']['invalid_query_peaks']==1
        checks['no_eligible_explicit_no_scan']=not hbad and not abad['scan_performed'] and abad['no_eligible_queries']
        for name,kw in [('wrong_hash',dict(expected_sha256='0'*64,expected_bytes=expected['expected_bytes'])),
                        ('wrong_size',dict(expected_sha256=expected['expected_sha256'],expected_bytes=expected['expected_bytes']+1))]:
            try:E.score_enveda(qs,{},path,cosine,**kw)
            except ValueError:checks[name+'_rejected']=True
            else:checks[name+'_rejected']=False
        try:E.score_enveda(qs,{},path,cosine,batch_size=8193,**expected)
        except ValueError:checks['unbounded_batch_rejected']=True
        else:checks['unbounded_batch_rejected']=False
        hnone,anone=E.score_enveda({'far':[query(prec=600.)]}, {},path,cosine,**expected)
        checks['no_precursor_match_preserved']=not hnone and anone['scored_pairs']==0
        # Below-threshold actual scores remain auditable but are not hits.
        belowpath=folder/'below.parquet';below=write_library(belowpath,[reference(mz=[10.,20.,30.,40.],intensity=[1.,1.,1.,1.])])
        low,alow=E.score_enveda({'low':[query(mz=[10.,20.,30.,40.],intensity=[100.,.0001,.0001,.0001])]}, {},belowpath,cosine,**below)
        checks['below_threshold_not_promoted']=not low and len(alow['query_best'])==1 and alow['query_best'][0]['cosine']<.8
        # Same raw precursor but opposite adduct is not matched.
        positivepath=folder/'positive.parquet';positive=write_library(positivepath,[reference()])
        cross,across=E.score_enveda({'cross':[query(prec=101.007276,adduct='[M-H]-',mode=-1)]},{},positivepath,cosine,**positive)
        checks['cross_adduct_rejected_despite_precursor']=not cross and across['scored_pairs']==0
        multi,amulti=E.score_enveda({'multi':[query(),query()]},{},positivepath,cosine,**positive)
        checks['earliest_query_tie']=multi['multi']['query_index']==0
        checks['actual_support_count']=multi['multi']['same_smiles_winning_spectra']==2
        # An exact boundary must survive the algebraic inverse-search optimization.
        boundary=query();boundary_mass=boundary['prec']+(boundary['prec']*E.PPM+E.DA)-E.CARRIER
        boundarypath=folder/'boundary.parquet';boundarypins=write_library(boundarypath,[reference(mass=boundary_mass)])
        bh,ba=E.score_enveda({'boundary':[boundary]},{},boundarypath,cosine,**boundarypins)
        checks['inclusive_mass_boundary']=bool(bh)
        result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
            source_sha256=E.sha(ROOT/'scripts/enveda_matching_20261110.py'),
            real_cosine_source='pinned Alex V12 original nested calc_cosine',
            examples=dict(hits=hits,metadata_audit=audit),no_gpu_network_or_truth=True)
    out=ROOT/'reports/enveda_matching_review_20261110';out.mkdir(parents=True,exist_ok=True)
    (out/'fixtures.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=result['status'],passed=sum(checks.values()),total=len(checks),failed=[k for k,v in checks.items() if not v])))
    assert all(checks.values())


if __name__=='__main__':run()
