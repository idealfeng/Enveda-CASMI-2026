"""Independent fingerprint/output audit and native MSG-cache competence canary.

Uses sixteen fixed, evenly spaced validation rows. No parameter or metric search,
training, test split, CASMI source mutation, or submission.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import argparse, ast, hashlib, json, sys, tarfile, time

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'assets/research/mist_msg_20261114/source'
ARCHIVE=ROOT/'assets/research/mist_msg_20261114/exposure/msg_compact.tar.gz'
CHECKPOINT=ROOT/'assets/research/mist_msg_20261114/checkpoints/mist_msg_noaug.ckpt'
OUT=ROOT/'runs/mist_fingerprint_audit_20261115'
REPORT=ROOT/'reports/mist_fingerprint_audit_20261115'
OFFICIAL_SITE=ROOT/'.cache/rdkit-official-linux-2026033'
if OFFICIAL_SITE.exists():sys.path.insert(0,str(OFFICIAL_SITE))
sys.path.insert(0,str(SOURCE/'src'))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def extract_val():
    if sha(ARCHIVE)!='a19e657a802cf5869d97b3486c7ce41021cba9c9a6279818e5d186307e3e7a35':raise ValueError('Compact archive pin')
    OUT.mkdir(parents=True,exist_ok=True)
    names={'form_vec.npy','ion_vec.npy','intens.npy','peak_type.npy','lengths.npy','instruments.npy','fingerprints.npy','names.npy','structure_ids.npy','manifest.json'}
    extracted=[];size=0
    with tarfile.open(ARCHIVE,'r:gz') as tar:
        for member in tar:
            parts=PurePosixPath(member.name).parts
            if PurePosixPath(member.name).is_absolute() or '..' in parts or member.issym() or member.islnk():raise ValueError('Unsafe archive member')
            if not member.isfile() or parts[:4]!=('data','compact','msg','val') or parts[-1] not in names:continue
            if not 0<=member.size<=32<<20:raise ValueError('Member size')
            size+=member.size
            if size>64<<20:raise ValueError('Total extraction cap')
            path=(OUT/'native_val'/Path(*parts[4:])).resolve()
            if not path.is_relative_to(OUT.resolve()):raise ValueError('Path escape')
            raw=tar.extractfile(member).read(member.size+1)
            if len(raw)!=member.size:raise ValueError('Length mismatch')
            if path.exists() and path.read_bytes()!=raw:raise ValueError('Existing evidence differs')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            extracted.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=len(raw),sha256=sha(path)))
    save(REPORT/'native_val_extraction.json',dict(status='extracted_native_val_only',archive_sha256=sha(ARCHIVE),files=extracted,no_test_extracted=True))

def main():
    import numpy as np,pandas as pd,rdkit
    from rdkit import Chem,DataStructs
    from rdkit.Chem import rdFingerprintGenerator
    if rdkit.__version__!='2026.03.3':raise ValueError('Official RDKit required')
    REPORT.mkdir(parents=True,exist_ok=True);extract_val()
    atlas=SOURCE/'src/mist/data/atlas.py';tree=ast.parse(atlas.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('morgan4096_packed','unpack_fingerprints')]
    official_generator=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=4096)
    scope=dict(np=np,Chem=Chem,DataStructs=DataStructs,_MORGAN_4096=official_generator,AtlasFeatureError=ValueError)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact_pinned_official_fp_functions','exec'),scope)
    adapter_generator=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=4096,includeChirality=False)
    scores_path=ROOT/'runs/mist_active_evaluation_20261114/inference/candidate_scores.parquet'
    table=pd.read_parquet(scores_path);diffs=[];bitcounts=[]
    for smi in table.smiles.unique():
        official=scope['unpack_fingerprints'](scope['morgan4096_packed'](smi))
        dense=np.zeros(4096,dtype=np.uint8);DataStructs.ConvertToNumpyArray(adapter_generator.GetFingerprint(Chem.MolFromSmiles(smi)),dense)
        if not np.array_equal(official,dense):diffs.append(smi)
        bitcounts.append(int(dense.sum()))
    casmi=np.load(ROOT/'runs/mist_active_evaluation_20261114/inference/spectrum_formula_probabilities.npy',allow_pickle=False)
    formula_means=np.load(ROOT/'runs/mist_active_evaluation_20261114/inference/formula_mean_probabilities.npy',allow_pickle=False)
    def stats(a):
        clip=np.clip(a,1e-8,1-1e-8)
        return dict(rows=int(a.shape[0]),min=float(a.min()),max=float(a.max()),mean=float(a.mean()),
                    on_probability_sum_mean=float(a.sum(1).mean()),mean_bit_std_across_rows=float(a.std(0).mean()),
                    row_l2_from_global_mean=float(np.linalg.norm(a-a.mean(0),axis=1).mean()),
                    binary_entropy_mean=float((-(clip*np.log(clip)+(1-clip)*np.log(1-clip))).mean()))
    result=dict(status='fingerprint_contract_checked',checked_at_utc=datetime.now(timezone.utc).isoformat(),
                fingerprint_candidates=int(table.smiles.nunique()),fp_definition_exact_equal=not diffs,fp_differences=diffs,
                candidate_on_bits_min=min(bitcounts),candidate_on_bits_max=max(bitcounts),
                casmi_probability_statistics=stats(casmi),formula_probability_statistics=stats(formula_means),
                pins=dict(atlas=sha(atlas),scaled_model=sha(SOURCE/'src/mist/models/scaled_mist.py'),metrics=sha(SOURCE/'src/mist/metrics.py'),candidate_scores=sha(scores_path)))
    import torch
    from mist.models.scaled_mist import ScaledMIST,count_parameters
    device=torch.device('cuda')
    if not torch.cuda.is_available():raise RuntimeError('Actual CUDA requested for native canary')
    torch.set_num_threads(4);torch.manual_seed(0)
    if sha(CHECKPOINT)!='6f8df582df36aa4a984f120efee14ee0a62f3a7723caa770b856a6e704236727':raise ValueError('Checkpoint pin')
    ckpt=torch.load(CHECKPOINT,map_location='cpu',weights_only=True)
    model=ScaledMIST(**ckpt['config']['model']);model.load_state_dict(ckpt['ema_model'],strict=True);model.to(device).eval()
    step=ckpt.get('step');kind=ckpt.get('checkpoint_kind');source_checkpoint_sha=ckpt.get('source_checkpoint_sha256')
    del ckpt
    part=OUT/'native_val/part_00000'
    arrays={n:np.load(part/(n+'.npy'),allow_pickle=False,mmap_mode='r') for n in ['form_vec','ion_vec','intens','peak_type','lengths','instruments','fingerprints','names','structure_ids']}
    indices=np.linspace(0,len(arrays['lengths'])-1,16,dtype=int)
    mapping=dict(form_vec=('form_vec',np.float32),ion_vec=('ion_vec',np.int64),intens=('intens',np.float32),types=('peak_type',np.int64),num_peaks=('lengths',np.int64),instruments=('instruments',np.int64))
    pred=[];start=time.monotonic()
    with torch.inference_mode():
        for offset in range(0,len(indices),4):
            chosen=indices[offset:offset+4]
            batch={k:torch.from_numpy(np.asarray(arrays[n][chosen],dtype=dtype).copy()).to(device) for k,(n,dtype) in mapping.items()}
            p,_=model(batch);pred.append(p.float().cpu().numpy())
    torch.cuda.synchronize();seconds=time.monotonic()-start;pred=np.concatenate(pred)
    truth=scope['unpack_fingerprints'](arrays['fingerprints'][indices])
    def soft(a,b):
        inter=(a*b).sum(1);return inter/np.maximum((a+b-a*b).sum(1),1e-8)
    def cosine(a,b):return (a*b).sum(1)/np.maximum(np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1),1e-8)
    perm=np.roll(np.arange(16),1)
    np.save(OUT/'native_val_probabilities.npy',pred,allow_pickle=False)
    np.save(OUT/'native_val_targets.npy',truth,allow_pickle=False)
    result.update(status='completed_fp_and_native_val_canary',native_canary=dict(split='val',indices=indices.tolist(),
        names=arrays['names'][indices].tolist(),structure_ids=arrays['structure_ids'][indices].tolist(),
        checkpoint_step=step,checkpoint_kind=kind,source_checkpoint_sha256=source_checkpoint_sha,
        strict_parameter_count=count_parameters(model),seconds=seconds,probability_statistics=stats(pred),
        actual_target_on_bits=truth.sum(1).astype(int).tolist(),true_soft_tanimoto=soft(pred,truth).tolist(),
        permuted_soft_tanimoto=soft(pred,truth[perm]).tolist(),true_cosine=cosine(pred,truth).tolist(),permuted_cosine=cosine(pred,truth[perm]).tolist(),
        mean_true_soft_tanimoto=float(soft(pred,truth).mean()),mean_permuted_soft_tanimoto=float(soft(pred,truth[perm]).mean()),
        mean_true_cosine=float(cosine(pred,truth).mean()),mean_permuted_cosine=float(cosine(pred,truth[perm]).mean()),
        finite=bool(np.isfinite(pred).all()),dtype=str(pred.dtype)),
        source_and_target_contract_aligned=True,new_training=False,test_split_used=False,casmi_metric_tuning=False,
        limitation='Sixteen native validation inputs are an output-competence diagnostic, not an independent benchmark or Kaggle improvement. CASMI truth not consumed here.')
    save(REPORT/'verification.json',result)
    print(json.dumps({k:result[k] for k in ['status','fp_definition_exact_equal','fingerprint_candidates','casmi_probability_statistics']}))
    print(json.dumps(result['native_canary']))

if __name__=='__main__':main()
