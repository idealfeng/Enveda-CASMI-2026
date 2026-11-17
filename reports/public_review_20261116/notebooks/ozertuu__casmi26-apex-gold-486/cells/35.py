# CODE CELL 18 · Deep EDA
# Additional fragmentation dimension: change in the low-m/z intensity fraction within each molecule.
def v7_small_mass_fraction(row):
    mz=np.asarray(row['ms2_mzs'],dtype=float)
    it=np.asarray(row['ms2_normalized_intensities'],dtype=float)
    try: precursor=float(row['precursor_mz'])
    except (TypeError,ValueError): return np.nan
    if not (np.isfinite(precursor) and precursor>0 and len(mz)==len(it)):
        return np.nan
    valid=np.isfinite(mz)&np.isfinite(it)&(it>0)
    if not valid.any():return np.nan
    mz,it=mz[valid],it[valid]
    return float(it[mz<.5*precursor].sum()/it.sum())

def v7_single_energy(x):
    try:
        vals=np.asarray(x,dtype=float).reshape(-1)
        vals=vals[np.isfinite(vals)]
        return float(vals[0]) if len(vals)==1 else np.nan
    except (TypeError,ValueError):
        return np.nan

v7_fragments=[]
for pair in v5_pairs.itertuples(index=False):
    if pair.pair_type!='same_structure_energy_extremes':continue
    a=v5_records.get((int(pair.a_group),int(pair.a_offset)))
    b=v5_records.get((int(pair.b_group),int(pair.b_offset)))
    if a is None or b is None:continue
    if any(str(a[k])!=str(b[k]) for k in ['inchikey14','adduct','instrument_type','ingest_lib']):continue
    if str(a['adduct']) not in ('[M+H]+','[M-H]-','[M+Na]+','[M+NH4]+'):
        continue
    ea,eb=v7_single_energy(a['collision_energy_ev']),v7_single_energy(b['collision_energy_ev'])
    if not (np.isfinite(ea) and np.isfinite(eb) and abs(ea-eb)>=10):continue
    lo,hi=(a,b) if ea<eb else (b,a)
    low=v7_small_mass_fraction(lo); high=v7_small_mass_fraction(hi)
    if not (np.isfinite(low) and np.isfinite(high)):continue
    v7_fragments.append({'Structure':str(a['inchikey14']), 'Lower energy':low,
        'Higher energy':high,'Energy gap':abs(eb-ea)})
v7_frag=pd.DataFrame(v7_fragments)
if len(v7_frag):
    v7_frag=v7_frag.groupby('Structure',as_index=False)[['Lower energy','Higher energy','Energy gap']].median()
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=v7_frag['Lower energy'],y=v7_frag['Higher energy'],
        mode='markers',marker=dict(color=BLUE,size=8,opacity=.62),name='Same structure'))
    fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',
        line=dict(color=CORAL,dash='dash'),name='No change'))
    fig=style(fig,'How Much Signal Shifts Toward Low-Mass Fragments?',
        f'{len(v7_frag)} structures · same conditions except collision energy',470)
    fig.update_layout(xaxis_title='Low-m/z fraction at lower energy',
                      yaxis_title='Low-m/z fraction at higher energy',
                      xaxis_range=[-.02,1.02],yaxis_range=[-.02,1.02])
    show_chart(fig)
    diff=v7_frag['Higher energy']-v7_frag['Lower energy']
    display(pd.DataFrame({'Metric':['Structures','Median shift in low-mass fragment fraction',
                                      'Structures with increasing low-mass fragment fraction'],
        'Value':[len(v7_frag),round(float(diff.median()),4),f'{(diff>0).mean():.1%}']}))
else:
    print('Not enough comparable single-energy spectra for this control.')