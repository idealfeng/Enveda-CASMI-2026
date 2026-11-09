
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
