# CODE CELL 37 · Deep EDA
def safe_peaks(row):
    try:
        mz=np.asarray(row['ms2_mzs'],dtype=float)
        yy=np.asarray(row['ms2_normalized_intensities'],dtype=float)
    except Exception:return np.array([]),np.array([])
    if mz.ndim!=1 or yy.ndim!=1 or len(mz)!=len(yy):return np.array([]),np.array([])
    good=np.isfinite(mz)&np.isfinite(yy)&(yy>=0)
    mz,yy=mz[good],yy[good]
    idx=np.argsort(mz)
    return mz[idx],yy[idx]

def sticks(mz, intensity, sign=1):
    X=[];Y=[]
    for m,v in zip(mz,intensity):X.extend([m,m,None]);Y.extend([0,sign*v,None])
    return X,Y

# Select a multi-spectrum example with acquisition conditions as comparable as possible
# Normalize missing values before grouping: NaN inside tuple keys can break get_group lookups.
spec['_inst_group']=spec.instrument_type.fillna('unknown').astype(str) if 'instrument_type' in spec else 'unknown'
spec['_adduct_group']=spec.adduct.fillna('unknown').astype(str)
keys=['inchikey14','_adduct_group','_inst_group']
groups=spec.dropna(subset=['inchikey14']).groupby(keys,dropna=False)
rank=[]
for key,g in groups:
    if len(g)<2:continue
    rank.append((len(g),g.mean_ev.nunique(),key))
rank.sort(key=lambda t:(t[1],t[0]),reverse=True)
selected_key=rank[0][2] if rank else None
example=groups.get_group(selected_key).sort_values('mean_ev').head(8).copy() if selected_key is not None else spec.head(1).copy()
print('Selected group:',selected_key,'| spectra:',len(example))