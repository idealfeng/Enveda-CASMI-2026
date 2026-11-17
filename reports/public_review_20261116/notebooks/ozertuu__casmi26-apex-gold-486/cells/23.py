# CODE CELL 11 · Deep EDA
# Average recorded CE is a descriptive grouping label; it is not one physical event.
def mean_energy(x):
    try:
        if x is None: return float('nan')
        if isinstance(x,(list,tuple,np.ndarray)):
            vals=np.asarray(x,dtype=float)
        else:
            vals=np.asarray([x],dtype=float)
        vals=vals[np.isfinite(vals)]
        return float(vals.mean()) if len(vals) else float('nan')
    except (ValueError,TypeError):
        return float('nan')

focus_all['energy_mean'] = focus_all['collision_energy_ev'].map(mean_energy) if 'collision_energy_ev' in focus_all else np.nan
selected_parts=[]
for _,g in focus_all.groupby('inchikey14',sort=False):
    conditions=[c for c in ['adduct','instrument_type','ingest_lib'] if c in g]
    groups = list(g.groupby(conditions,dropna=False)) if conditions else [(None,g)]
    groups.sort(key=lambda pair:(pair[1].energy_mean.nunique(),len(pair[1])),reverse=True)
    main=groups[0][1].sort_values('energy_mean',na_position='last')
    n=min(5,len(main))
    take=np.unique(np.linspace(0,len(main)-1,n,dtype=int))
    indices=list(main.iloc[take].index)
    # Add examples from other adducts, instruments or source libraries.
    for _,other in groups[1:]:
        if len(indices) >= MAX_SPECTRA_PER_STRUCTURE:break
        indices.append(other.index[0])
    # Fill remaining slots with randomly chosen different records.
    leftover=g.loc[~g.index.isin(indices)]
    if len(indices)<MAX_SPECTRA_PER_STRUCTURE and len(leftover):
        extra=RNG_EXPORT.choice(leftover.index,size=min(MAX_SPECTRA_PER_STRUCTURE-len(indices),len(leftover)),replace=False)
        indices.extend(extra.tolist())
    selected_parts.append(g.loc[indices])
focused = pd.concat(selected_parts,ignore_index=True) if selected_parts else focus_all.head(0).copy()
focused['selection_role']='same_structure_focus'



# Mass-matched different-structure controls, with the same adduct and instrument when possible.
meta_neg = background.copy()
for c in ['adduct','instrument_type']:
    if c not in meta_neg: meta_neg[c]='unknown'
    if c not in focused: focused[c]='unknown'
    meta_neg[c]=meta_neg[c].fillna('unknown').astype(str)
    focused[c]=focused[c].fillna('unknown').astype(str)
meta_neg['_mass']=pd.to_numeric(meta_neg.precursor_mz,errors='coerce')
meta_neg=meta_neg[np.isfinite(meta_neg._mass)]
lookup={}
for key,g in meta_neg.groupby(['adduct','instrument_type'],sort=False):
    g=g.sort_values('_mass')
    lookup[key]=(g['_mass'].to_numpy(dtype=float),g)

negative_parts=[]; negative_pair_records=[]
for _,anchor in focused.drop_duplicates('inchikey14').iterrows():
    key=(str(anchor['adduct']),str(anchor['instrument_type']))
    if key not in lookup:continue
    try: mass=float(anchor['precursor_mz'])
    except (TypeError,ValueError):continue
    if not np.isfinite(mass):continue
    arr,table=lookup[key]
    pivot=np.searchsorted(arr,mass)
    lo=max(0,pivot-20);hi=min(len(arr),pivot+21)
    window=table.iloc[lo:hi]
    window=window[window.inchikey14 != anchor.inchikey14]
    if window.empty:continue
    diffs=(window._mass-mass).abs()
    j=diffs.idxmin()
    if diffs.loc[j]>MAX_MASS_GAP_DA:continue
    neg=window.loc[j].drop(labels=['_mass']).copy()
    negative_parts.append(neg)
    negative_pair_records.append({
        'pair_type':'different_structure_close_precursor',
        'a_group':int(anchor.row_group),'a_offset':int(anchor.row_offset),
        'b_group':int(neg.row_group),'b_offset':int(neg.row_offset),
        'precursor_gap_da':float(diffs.loc[j]),
    })
negatives=pd.DataFrame(negative_parts) if negative_parts else focused.head(0).copy()
if len(negatives):negatives['selection_role']='different_structure_control'
all_locs=pd.concat([focused,negatives],ignore_index=True)
all_locs=all_locs.drop_duplicates(['row_group','row_offset']).reset_index(drop=True)
print(f'Training metadata sample: {len(background):,} | focused spectra: {len(focused):,} | mass-matched controls: {len(negatives):,}')

# Build within-structure, same-acquisition-condition comparisons.
pairs=negative_pair_records.copy()
condition_fields=[c for c in ['inchikey14','adduct','instrument_type','ingest_lib'] if c in focused]
for _,g in focused.groupby(condition_fields,dropna=False):
    if len(g)<2:continue
    s=g.sort_values('energy_mean',na_position='last')
    a=s.iloc[0];b=s.iloc[-1]
    pairs.append({'pair_type':'same_structure_energy_extremes',
        'a_group':int(a.row_group),'a_offset':int(a.row_offset),
        'b_group':int(b.row_group),'b_offset':int(b.row_offset),
        'precursor_gap_da':abs(float(a.precursor_mz)-float(b.precursor_mz))})
    if len(s)>=3:
        x=s['energy_mean'].to_numpy(dtype=float)
        dist=np.abs(np.diff(x))
        if np.isfinite(dist).any():
            i=int(np.nanargmin(dist));a=s.iloc[i];b=s.iloc[i+1]
            pairs.append({'pair_type':'same_structure_energy_nearest',
                'a_group':int(a.row_group),'a_offset':int(a.row_offset),
                'b_group':int(b.row_group),'b_offset':int(b.row_offset),
                'precursor_gap_da':abs(float(a.precursor_mz)-float(b.precursor_mz))})
pair_df=pd.DataFrame(pairs,columns=['pair_type','a_group','a_offset','b_group','b_offset','precursor_gap_da'])


