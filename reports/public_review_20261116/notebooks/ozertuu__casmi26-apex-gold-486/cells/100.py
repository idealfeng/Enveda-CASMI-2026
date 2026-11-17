# CODE CELL 52 · Deep EDA
# Experiment 35: listed neutral losses versus a near-mass negative control.
_v13_losses=np.array([18.010565,17.026549,27.994915,43.989829,32.026215,27.010899])
_v13_loss_pool=v13_records.copy()
_v13_loss_pool['v13_pmz']=pd.to_numeric(_v13_loss_pool.precursor_mz,errors='coerce')
_v13_loss_pool=_v13_loss_pool[_v13_loss_pool.v13_pmz.notna() & (_v13_loss_pool.v13_pmz>0)].copy()
_v13_rng=np.random.default_rng(20261114)

def v13_loss_fraction(row,precursor,tol=.01):
    mz=np.asarray(row.ms2_mzs,dtype=float)
    it=np.asarray(row.ms2_normalized_intensities,dtype=float)
    valid=np.isfinite(mz)&np.isfinite(it)&(it>0)&(mz<float(row.precursor_mz))
    mz,it=mz[valid],it[valid]
    if len(it)<6 or it.sum()<=0:return np.nan
    gaps=precursor-mz
    hit=((gaps[:,None]>0)&(np.abs(gaps[:,None]-_v13_losses[None,:])<=tol)).any(axis=1)
    return float(it[hit].sum()/it.sum())

_v13_rows=[]
_v13_sample=_v13_loss_pool.sample(n=min(450,len(_v13_loss_pool)),random_state=20261114)
for row in _v13_sample.itertuples(index=False):
    pool=_v13_loss_pool[(_v13_loss_pool.adduct==row.adduct) &
       (_v13_loss_pool.inchikey14!=row.inchikey14) &
       ((_v13_loss_pool.v13_pmz-row.v13_pmz).abs().between(0.03,25))]
    if len(pool)==0:continue
    control=pool.iloc[int(_v13_rng.integers(0,len(pool)))].v13_pmz
    observed=v13_loss_fraction(row,float(row.v13_pmz))
    decoy=v13_loss_fraction(row,float(control))
    if np.isfinite(observed) and np.isfinite(decoy):
        _v13_rows.append({'Structure':str(row.inchikey14),'Observed':observed,
                          'Control':decoy,'Difference':observed-decoy})
v13_losses_test=pd.DataFrame(_v13_rows)
if len(v13_losses_test):
    fig=px.scatter(v13_losses_test,x='Control',y='Observed',opacity=.6,
                   hover_data=['Structure'],color_discrete_sequence=[TEAL])
    fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',name='Equality',
                 line=dict(color=CORAL,dash='dash')))
    fig=style(fig,'Neutral Losses: Observed Signal vs Negative Control',
          f'{len(v13_losses_test)} spectra · precursor mass from a different molecule with the same adduct',470)
    fig.update_layout(xaxis_title='Intensity fraction · decoy',
                      yaxis_title='Intensity fraction · actual precursor',
                      xaxis_range=[-.02,1.02],yaxis_range=[-.02,1.02])
    show_chart(fig)
    display(pd.DataFrame({'Measurement':['Matched spectra','Median fraction, actual precursor',
                'Median fraction, decoy','Median paired difference'],
           'Result':[len(v13_losses_test),
                        f"{v13_losses_test['Observed'].median():.3f}",
                        f"{v13_losses_test['Control'].median():.3f}",
                        f"{v13_losses_test['Difference'].median():+.3f}"]}))
    note('Finding 35 · Mass Match ≠ Proven Fragmentation Pathway',
         'Using a decoy precursor tests chance matches, '
         'but does not validate fragment formulas or prove a reaction mechanism.')
else:print('Not enough mass-matched precursors for the negative control.')
