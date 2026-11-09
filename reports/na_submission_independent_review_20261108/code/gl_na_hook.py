"""Preserve the H-only GL run; add independently scored real Na+ evidence."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

RUNNER_SHA='5c4f74313ac54263d05d987c39d012d81ec57c5f35e1095ecd49a5bcb6440fca'
CHECKPOINT_SHA='9192e4c2eeafe83317d5a2c2641e1fc4d68934488757a4faafeb66f2ab397a12'
SOURCE_ADAPTATION='Preserve H-only GL inputs/order; independently score real Na and merge by actual finite per-candidate spectrum counts'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def finite(value):return isinstance(value,(int,float)) and math.isfinite(value)


def select_items(items,adducts=('[M+H]+','[M+Na]+')):
    result=[]
    for item in items:
        spectra=[s for s in item['spectra'] if s.get('adduct') in adducts]
        if spectra:result.append(dict(item,spectra=spectra))
    return result


def run_counted_gl(pkg_dir,items,workdir='/kaggle/working/gl_work',device='cuda',budget_s=4000.,
                   site='/kaggle/working/ice_site',wheels=None,extra_args=()):
    """Original GL CLI/order with the proven score AST observer, recording finite counts."""
    package,workdir=Path(pkg_dir),Path(workdir)
    if sha(package/'gl_runner.py')!=RUNNER_SHA:raise ValueError('GL runner pin differs')
    workdir.mkdir(parents=True,exist_ok=True)
    fin,fout=workdir/'gl_in.json',workdir/'gl_out.json'
    counts=workdir/'gl_finite_counts.json'
    for p in (fout,Path(str(fout)+'.meta.json'),counts):p.unlink(missing_ok=True)
    write(fin,items)
    cmd=[sys.executable,str(Path(__file__).parent/'gl_counted_runner.py'),str(package),str(fin),str(fout),
         '--counts-json',str(counts),'--device',device,'--budget',str(float(budget_s)),'--site',site]
    if wheels:cmd+=['--wheels',str(wheels)]
    cmd+=list(extra_args)
    result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                          timeout=budget_s+300 if budget_s>0 else None)
    print(result.stdout[-3000:],flush=True)
    if result.returncode or not counts.is_file():raise RuntimeError('Counted GL subprocess did not complete')
    meta=read(str(fout)+'.meta.json')
    if meta.get('status')!='ok' or meta.get('errors'):raise RuntimeError('Counted GL model run failed')
    return read(fout)


def merge_scores(h,na,h_counts,na_counts):
    """No-Na queries are copied exactly; each candidate uses its own finite count."""
    out={mid:dict(scores) for mid,scores in h.items()}
    for mid,scores in na.items():
        target=out.setdefault(mid,{})
        for smi,nv in scores.items():
            hv=target.get(smi)
            hn=h_counts.get(mid,{}).get(smi,0)
            nn=na_counts.get(mid,{}).get(smi,0)
            for value,count in ((hv,hn),(nv,nn)):
                if type(count)!=int or count<0 or finite(value)!=(count>0):
                    raise ValueError('Mean/count validity differs')
            if hn and nn:target[smi]=(float(hv)*hn+float(nv)*nn)/(hn+nn)
            elif nn:target[smi]=nv
            elif hn:target[smi]=hv
            else:target[smi]=None
    return out


def extend_with_na(package,items,h,root,ice_package,budget_s=1800.):
    root=Path(root);package=Path(package)
    h_path=root/'gl_work/gl_out.json'
    h_sha=sha(h_path)
    hc=read(root/'gl_work/gl_finite_counts.json')
    na_items=select_items(items,('[M+Na]+',))
    na={};nc={}
    if na_items:
        na=run_counted_gl(package,na_items,workdir=root/'gl_na_work',device='cuda',budget_s=budget_s,
                          site=str(root/'ice_site'),wheels=str(Path(ice_package)/'wheels'),extra_args=['--any-rdkit'])
        nc=read(root/'gl_na_work/gl_finite_counts.json')
    combined=merge_scores(h,na,hc,nc)
    na_mids={str(i['mid']) for i in na_items}
    expected=select_items(items)
    checks=dict(original_runner_pin=sha(package/'gl_runner.py')==RUNNER_SHA,
                original_checkpoint_pin=sha(package/'ckpt/glacier.pt')==CHECKPOINT_SHA,
                original_h_output_unchanged=sha(h_path)==h_sha,
                non_na_query_scores_exactly_unchanged=all(combined[m]==v for m,v in h.items() if m not in na_mids),
                exact_na_query_set=set(na)==na_mids,
                exact_na_candidate_sets=all(set(na.get(str(i['mid']),{}))==set(i['cands']) for i in na_items),
                actual_finite_candidate_counts=True,
                original_candidate_sets=all(set(combined.get(str(i['mid']),{}))==set(i['cands']) for i in expected),
                original_h_input_selection=read(root/'gl_work/gl_in.json')==select_items(items,('[M+H]+',)),
                real_na_input_selection=not na_items or read(root/'gl_na_work/gl_in.json')==na_items)
    for mid,d in h.items():
        for smi,v in d.items():
            count=hc.get(mid,{}).get(smi,0)
            checks['actual_finite_candidate_counts'] &= type(count)==int and count>=0 and finite(v)==(count>0)
    checks['actual_finite_candidate_counts']=bool(checks['actual_finite_candidate_counts'])
    write(root/'gl_na_combined.json',combined)
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
        aggregation='(H_mean * H_actual_finite_count + Na_mean * Na_actual_finite_count) / total_count per candidate',
        h_budget_seconds=4000,na_budget_seconds=budget_s,na_queries=len(na_items),
        na_spectra=sum(len(i['spectra']) for i in na_items),
        combined_queries=len(combined),combined_candidate_rows=sum(len(d) for d in combined.values()),
        original_h_output_sha256=h_sha,combined_sha256=sha(root/'gl_na_combined.json'),
        original_runner_sha256=RUNNER_SHA,original_checkpoint_sha256=CHECKPOINT_SHA,
        source_adaptation=SOURCE_ADAPTATION,pretrained_na_coverage_known=False)
    write(root/'gl_na_runtime.json',report)
    if not all(checks.values()):raise RuntimeError('GL Na evidence merge failed audit: '+repr(checks))
    return combined,report


def replace_once(text,before,after):
    if text.count(before)!=1:raise ValueError('Expected one adaptation site: '+before[:80])
    return text.replace(before,after)


def adapt_cell41(text):
    text=replace_once(text,'    GL_SCORES = gl_fuse.run_gl(GL_PKG, gl_items,',
                      '    GL_SCORES = run_counted_gl(GL_PKG, gl_items,')
    text=replace_once(text,'# N1A complement: Seyit Kaan Gunes; integration as in Ahmed Berat Ozer v15 / guhongbin v465.',
        "GL_SCORES, GL_NA_REPORT = extend_with_na(GL_PKG, items, GL_SCORES, '/kaggle/working', ICE_PKG, budget_s=1800.)\n"
        '# N1A complement: Seyit Kaan Gunes; integration as in Ahmed Berat Ozer v15 / guhongbin v465.')
    text=replace_once(text,
        "    if not IS_RERUN:\n        assert not _n1_clash, ('N1 molecule already scored by the H1 run', _n1_clash[:5])",
        "    _glna_real_na_mids = {str(it['mid']) for it in items if any(s.get('adduct') == '[M+Na]+' for s in it['spectra'])}\n"
        "    _n1_real = {m: v for m, v in _n1_real.items() if m not in _n1_clash}\n"
        "    if not IS_RERUN:\n        assert set(_n1_clash) <= _glna_real_na_mids, ('Unexpected real-GL/proxy clash', _n1_clash[:5])")
    return 'from gl_na_hook import run_counted_gl, extend_with_na\nGL_NA_REPORT = {}\n'+text
