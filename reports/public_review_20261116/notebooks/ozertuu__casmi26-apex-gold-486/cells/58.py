# CODE CELL 29 · Deep EDA
_v9_rng=np.random.default_rng(SEED+909)
_v9_candidates=v8_metrics[(~v8_metrics.same_structure)&v8_metrics.same_adduct&v8_metrics.same_instrument&
                          v8_metrics.cosine_sym.notna()].copy()
_v9_candidates=_v9_candidates.sort_values('cosine_sym',ascending=False)
_v9_first=_v9_candidates.head(24)
_v9_last=_v9_candidates.tail(24)
_v9_perm_pairs=pd.concat([_v9_first,_v9_last],ignore_index=True).drop_duplicates(subset=['a','b'])
_v9_perm=[]
for p in _v9_perm_pairs.itertuples(index=False):
    a,b=v5_records[p.a],v5_records[p.b]
    obs=float(p.cosine_sym)
    shuffle=[]
    for repeat in range(25):
        tmp=dict(b)
        intens=np.asarray(b['ms2_normalized_intensities'],dtype=float).copy()
        _v9_rng.shuffle(intens)
        tmp['ms2_normalized_intensities']=intens
        score,_=v8_symmetric_cosine(a,tmp)
        if np.isfinite(score):shuffle.append(score)
    if shuffle:
        _v9_perm.append({'Observed cosine':obs,'Median shuffled cosine':float(np.median(shuffle)),
          'Δ observed − control':obs-float(np.median(shuffle)),
          'Group':'Dimer' if p.dimer else 'Other adduct'})
_v9_permutation=pd.DataFrame(_v9_perm)
if len(_v9_permutation):
    fig=px.scatter(_v9_permutation,x='Median shuffled cosine',y='Observed cosine',color='Group',
                  color_discrete_map={'Dimer':CORAL,'Other adduct':BLUE},opacity=.85)
    fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',line=dict(color='#9BAEAE',dash='dash'),
                             showlegend=False))
    fig=style(fig,'Matching Peak Positions Are Not the Whole Spectral Fingerprint',
         f'{len(_v9_permutation)} pairs of distinct structures · 25 intensity shuffles per pair',465)
    fig.update_layout(xaxis_title='Median cosine after shuffling peak intensities',
                      yaxis_title='Original cosine',xaxis_range=[-.02,1.03],yaxis_range=[-.02,1.03])
    show_chart(fig)
    display(_v9_permutation.groupby('Group',observed=True).agg(
        n=('Δ observed − control','size'),median_shift=('Δ observed − control','median'))
        .rename(columns={'n':'Pairs','median_shift':'Median cosine difference'}).round(4))
    note('Finding · The Role of Relative Intensities',
         f'Across {len(_v9_permutation)} pairs, median (observed cosine − shuffled control) = '
         f'{_v9_permutation["Δ observed − control"].median():.3f}. '
         'This measures the contribution of intensity placement at fixed peak masses.')
