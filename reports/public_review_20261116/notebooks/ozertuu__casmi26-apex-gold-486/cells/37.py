# CODE CELL 19 · Deep EDA
def v8_lowmz_share(row,cutoff):
    mz=np.asarray(row['ms2_mzs'],dtype=float)
    it=np.asarray(row['ms2_normalized_intensities'],dtype=float)
    precursor=float(row['precursor_mz'])
    good=np.isfinite(mz)&np.isfinite(it)&(it>0)
    if not good.any() or not np.isfinite(precursor) or precursor<=0:return np.nan
    mz,it=mz[good],it[good]
    return float(it[mz<cutoff*precursor].sum()/it.sum())

v8_cutoffs=[.3,.4,.5,.6]
_frag_rows=[]
for pair in v5_pairs.itertuples(index=False):
    if pair.pair_type!='same_structure_energy_extremes':continue
    a=v5_records.get((int(pair.a_group),int(pair.a_offset)))
    b=v5_records.get((int(pair.b_group),int(pair.b_offset)))
    if a is None or b is None:continue
    if any(str(a[k])!=str(b[k]) for k in ['inchikey14','adduct','instrument_type','ingest_lib']):continue
    if str(a['adduct']) not in ('[M+H]+','[M-H]-','[M+Na]+','[M+NH4]+'):continue
    ea=v7_single_energy(a['collision_energy_ev'])
    eb=v7_single_energy(b['collision_energy_ev'])
    if not (np.isfinite(ea) and np.isfinite(eb) and abs(ea-eb)>=10):continue
    lo,hi=(a,b) if ea<eb else (b,a)
    rec={'key':str(a['inchikey14'])}
    for cut in v8_cutoffs:
        rec[f'{cut:.1f}']=v8_lowmz_share(hi,cut)-v8_lowmz_share(lo,cut)
    _frag_rows.append(rec)
v8_fragment_robust=pd.DataFrame(_frag_rows)
if len(v8_fragment_robust):
    v8_fragment_robust=v8_fragment_robust.groupby('key',as_index=False).median(numeric_only=True)
    _n=len(v8_fragment_robust)
    _rng=np.random.default_rng(SEED+886)
    _ci=[];_med=[];_positive=[]
    for cut in v8_cutoffs:
        values=v8_fragment_robust[f'{cut:.1f}'].dropna().to_numpy(float)
        _med.append(float(np.median(values)))
        _positive.append(float(np.mean(values>0)))
        bs=np.median(values[_rng.integers(0,len(values),(1300,len(values)))],axis=1)
        _ci.append(np.quantile(bs,[.025,.975]))
    _ci=np.asarray(_ci)
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=[100*x for x in v8_cutoffs],y=_med,
        mode='lines+markers',line=dict(color=TEAL,width=4),marker=dict(size=12),
        error_y=dict(type='data',symmetric=False,array=_ci[:,1]-_med,arrayminus=np.asarray(_med)-_ci[:,0]),
        hovertemplate='Cutoff: %{x:.0f}% precursor<br>Median shift: %{y:.2%}<extra></extra>'))
    fig.add_hline(y=0,line_color=CORAL,line_dash='dash')
    fig=style(fig,'Fragmentation Shifts Toward Lower m/z as Energy Increases',
        f'{_n} structures · single-energy spectra · 95% bootstrap intervals',455)
    fig.update_layout(xaxis_title='Low-mass cutoff (% precursor m/z)',
                      yaxis_title='Median increase in intensity share',yaxis_tickformat='.0%')
    show_chart(fig)
    display(pd.DataFrame({'Cutoff, %':[int(100*x) for x in v8_cutoffs],
        'Median fraction increase':_med,'Fraction of structures with an increase':_positive,
        '95% CI': [f'{x[0]:.3f} … {x[1]:.3f}' for x in _ci]}).round(3))
