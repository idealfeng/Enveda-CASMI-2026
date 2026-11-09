"""CPU mechanics review of the real scorer adapter using a small fake encoder.

Synthetic fixture keys replace production encoder pins in memory. No production
checkpoint, query, truth, GPU, training, cloud run, or submission is used.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

BASELINE = r'''
import json
from pathlib import Path
import numpy as np,pandas as pd,torch
class Features:
 @staticmethod
 def peaks(mz,it,prec,max_peaks):
  if mz is None:raise ValueError('bad fixture peaks')
  x=np.zeros((max_peaks,4),dtype=np.float32)
  x[:len(mz),0]=np.asarray(mz,dtype=np.float32)/float(prec)
  return x,len(mz)
 @staticmethod
 def metadata(prec,adduct,mode,ce):
  return np.asarray([prec/1000.,float(ce)/100.,1.,0.],dtype=np.float32),{'H':0,'Na':1}[adduct]
 @staticmethod
 def structure(smiles,bits):
  fp=np.zeros(bits,dtype=np.float32)
  fp[[len(smiles)%192,(len(smiles)*7)%192]]=1.
  return smiles,fp
class Model:
 def encode_molecules(self,fp):return torch.nn.functional.normalize(fp[:,:192],dim=-1)
 def encode_spectra(self,x,lengths,meta,adduct):
  z=torch.arange(192,dtype=x.dtype,device=x.device)[None]+x[:,0,0,None]+meta[:,0,None]
  z=torch.nn.functional.normalize(z.sin(),dim=-1)
  p=torch.arange(2048,dtype=x.dtype,device=x.device)[None]*.001+x[:,0,0,None]
  return z,p
def load_model(bundle,checkpoint,device):
 return Model(),Features(),dict(embedding=192,max_peaks=96,min_peaks=1,temperature=.1,fp_score_weight=2.,fp_bits=2048)
def score(bundle,checkpoint,evidence,queries,output,device='cpu'):
 model,feat,cfg=load_model(bundle,checkpoint,device)
 df=pd.read_parquet(evidence);q=pd.read_parquet(queries);parts=[]
 for mid,g in df.groupby('molecule_id',sort=False):
  g=g.sort_values('baseline_rank',kind='stable').copy();g['neural_ok']=False
  for col in ('neural_cos','neural_fp','neural_score','neural_std','n_spectra','n_adducts'):g[col]=0.
  if not g.processed.iloc[0]:parts.append(g);continue
  group=q[q.molecule_id==mid];records=[]
  for r in group.itertuples(index=False):
   try:
    pk,n=feat.peaks(r.ms2_mzs,r.ms2_normalized_intensities,r.precursor_mz,96)
    meta,ad=feat.metadata(r.precursor_mz,r.adduct,r.ionization_mode,r.collision_energy_ev);records.append((pk,n,meta,ad))
   except (ValueError,TypeError):continue
  if not records:parts.append(g);continue
  F=torch.tensor(np.stack([feat.structure(s,2048)[-1] for s in g.smiles]));M=model.encode_molecules(F)
  x=torch.tensor(np.stack([r[0] for r in records]));lengths=torch.tensor([r[1] for r in records]);meta=torch.tensor(np.stack([r[2] for r in records]));ad=torch.tensor([r[3] for r in records])
  z,p=model.encode_spectra(x,lengths,meta,ad);cos=(z@M.T).numpy();fps=(p@F.T/2048).numpy();base=cos/.1+2*fps
  g['neural_cos'],g['neural_fp']=cos.mean(0),fps.mean(0);g['neural_score'],g['neural_std']=base.mean(0),base.std(0)
  g['n_spectra'],g['n_adducts'],g['neural_ok']=len(records),group.adduct.nunique(),True;parts.append(g)
 pd.concat(parts,ignore_index=True).to_parquet(output,index=False)
'''


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    import numpy as np
    import pandas as pd
    import torch
    torch.set_num_threads(4)
    folder=ROOT/'reports/learned_head_adapter_fixture_20261108'
    folder.mkdir(parents=True,exist_ok=False)
    source=ROOT/'scripts/learned_head_score.py';source_sha=sha(source)
    module=load('_review_actual_head_adapter',source)
    module.__file__=str(folder/'learned_head_score.py')
    baseline=folder/'fixture_original_scorer.py';baseline.write_text(BASELINE,encoding='utf-8')
    head_source=folder/'candidate_multispectrum_head.py'
    shutil.copyfile(ROOT/'scripts/candidate_multispectrum_head.py',head_source)
    head_module=load('_review_actual_head_class',head_source)
    pub,ours=folder/'public_encoder',folder/'v2_encoder';pub.mkdir();ours.mkdir()
    (pub/'final_model.pt').write_bytes(b'PUBLIC SYNTHETIC ENCODER DISPATCH FIXTURE')
    (ours/'final_model.pt').write_bytes(b'V2 SYNTHETIC ENCODER DISPATCH FIXTURE')
    module.PUBLIC_SHA,module.V2_SHA=sha(pub/'final_model.pt'),sha(ours/'final_model.pt')
    head=head_module.CandidateMultiSpectrumHead();head_file=folder/'fixture_head.pt'
    def save_head(step=500):
        torch.save(dict(encoder_sha256=module.V2_SHA,step=step,seed=7,
            head_config=head_module.head_config(),state_dict=head.state_dict()),head_file)
    save_head()
    runtime=dict(baseline_scorer_file=baseline.name,baseline_scorer_sha256=sha(baseline),
        head_model_file=head_source.name,head_model_sha256=sha(head_source),required_step=500,
        heads=[dict(file=head_file.name,sha256=sha(head_file))])
    runtime_path=folder/'runtime.json'
    def save_runtime(value=None):runtime_path.write_text(json.dumps(value or runtime),encoding='utf-8')
    save_runtime()
    ev=pd.DataFrame(dict(molecule_id=['a']*3+['b']*3+['unprocessed']*2,
        smiles=['C','CC','CCC']*2+['CCCC','CCCCC'], baseline_rank=[3,1,2,1,3,2,1,2], processed=[True]*6+[False]*2))
    q=pd.DataFrame(dict(molecule_id=['a','a','b'],ms2_mzs=[[20.,30.],[40.,50.],[25.,35.]],
        ms2_normalized_intensities=[[1.,.5]]*3,precursor_mz=[200.,200.,300.],adduct=['H','Na','H'],
        ionization_mode=['positive']*3,collision_energy_ev=[20.,40.,30.]))
    ep,qp=folder/'evidence.parquet',folder/'query.parquet';ev.to_parquet(ep,index=False);q.to_parquet(qp,index=False)
    fakebase=load('_review_fixture_base',baseline)
    old=folder/'old.parquet';fakebase.score(ours,'final_model.pt',ep,qp,old,'cpu')
    checks={}
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    def score(bundle,filename):
        out=folder/filename;module.score(bundle,'final_model.pt',ep,qp,out,'cpu',runtime_path=runtime_path);return out
    public_out=score(pub,'public.parquet')
    public_audit=json.loads(Path(str(public_out)+'.head_audit.json').read_text())
    check('actual_public_dispatch_passthrough',public_audit['role']=='public_passthrough' and not public_audit['head_applied'])
    check('public_passthrough_values_equal',pd.read_parquet(old).equals(pd.read_parquet(public_out)))
    learned=score(ours,'zero_head.parquet');a,b=pd.read_parquet(old),pd.read_parquet(learned)
    audit=json.loads(Path(str(learned)+'.head_audit.json').read_text())
    check('v2_dispatch_applies_actual_head_class',audit['role']=='learned_v2' and audit['head_applied'] and audit['heads'][0]['step']==500)
    check('zero_head_original_mean_equal',np.allclose(a.neural_score,b.neural_score,atol=1e-6,rtol=1e-6))
    check('candidate_keys_and_order_preserved',a[['molecule_id','smiles']].equals(b[['molecule_id','smiles']]))
    check('original_diagnostics_equal',all(np.allclose(a[col],b[col],atol=1e-6,rtol=1e-6) for col in
        ['neural_cos','neural_fp','neural_std','n_spectra','n_adducts']))
    check('processed_coverage_equal',a.neural_ok.equals(b.neural_ok) and audit['scored_queries']==2 and audit['scored_candidate_rows']==6)
    def rejects(name,call):
        rejected=False
        try:call()
        except (ValueError,RuntimeError):rejected=True
        check(name,rejected)
    # All rejection cases invoke the actual adapter, not a reimplemented validator.
    bad=dict(runtime,heads=[dict(file=head_file.name,sha256='0'*64)]);save_runtime(bad)
    rejects('rejects_wrong_head_sha',lambda:score(ours,'bad_sha.parquet'))
    save_runtime();save_head(step=499);runtime['heads'][0]['sha256']=sha(head_file);save_runtime()
    rejects('rejects_wrong_training_step',lambda:score(ours,'bad_step.parquet'))
    save_head();runtime['heads'][0]['sha256']=sha(head_file);save_runtime()
    unknown=folder/'unknown_encoder';unknown.mkdir();(unknown/'final_model.pt').write_bytes(b'UNKNOWN')
    rejects('rejects_unknown_encoder',lambda:score(unknown,'unknown.parquet'))
    bad=dict(runtime,head_model_sha256='0'*64);save_runtime(bad)
    rejects('rejects_wrong_head_source',lambda:score(ours,'bad_source.parquet'));save_runtime()
    q=q[q.molecule_id!='b'];q.to_parquet(qp,index=False)
    fallback=score(ours,'partial_input.parquet');fallback_frame=pd.read_parquet(fallback)
    fallback_audit=json.loads(Path(str(fallback)+'.head_audit.json').read_text())
    check('invalid_query_fallback_explicit_and_scoped',len(fallback_audit['errors'])==1
        and fallback_audit['errors'][0]['molecule_id']=='b' and fallback_audit['scored_queries']==1
        and fallback_frame[fallback_frame.molecule_id=='a'].neural_ok.all()
        and not fallback_frame[fallback_frame.molecule_id=='b'].neural_ok.any())
    check('reviewed_adapter_source_unchanged',sha(source)==source_sha)
    report=dict(status='passed',checks=checks,adapter_source_sha256=source_sha,
        head_source_sha256=sha(head_source),zero_head_max_error=float(np.abs(a.neural_score-b.neural_score).max()),
        synthetic_encoder_fixture=True,production_encoder_pins_overridden_in_memory=True,
        real_model_inference=False,training_performed=False,cloud_write_performed=False,
        caveat='Mechanics only; real encoder zero-head parity and hidden full coverage remain separate checks.')
    (folder/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
