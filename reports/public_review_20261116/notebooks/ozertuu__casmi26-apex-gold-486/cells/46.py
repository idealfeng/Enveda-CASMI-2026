# CODE CELL 23 · Deep EDA
_v9_tol=[0.005,0.01,0.02,0.05,0.10]
_v9_negs=v8_metrics[(~v8_metrics.same_structure)&v8_metrics.same_adduct&v8_metrics.same_instrument].copy()
_v9_negs=_v9_negs.dropna(subset=['precursor_gap'])
_v9_negs=_v9_negs[_v9_negs.precursor_gap<=.2]
# Fixed ordering and a fixed number of pairs across tolerance settings.
_v9_negs=_v9_negs.sort_values(['key_a','key_b','a']).head(600)
_v9_tol_records=[]
for tol in _v9_tol:
    for pair in _v9_negs.itertuples(index=False):
        s,_=v8_symmetric_cosine(v5_records[pair.a],v5_records[pair.b],tol=tol)
        if np.isfinite(s):
            _v9_tol_records.append({'Tolerance, Da':tol,'Dimeric':bool(pair.dimer),'Cosine':s,
                                    'A':str(pair.key_a),'B':str(pair.key_b)})
_v9_tolerance=pd.DataFrame(_v9_tol_records)
if len(_v9_tolerance):
    _rates=(_v9_tolerance.assign(high=lambda d:d.Cosine>=.8)
             .groupby(['Tolerance, Da','Dimeric'],as_index=False)
             .agg(n=('high','size'),high=('high','sum'),rate=('high','mean')))
    fig=go.Figure()
    for is_dimer,name,col in [(False,'Other adducts',BLUE),(True,'Dimeric adducts',CORAL)]:
        sub=_rates[_rates['Dimeric']==is_dimer]
        if len(sub):fig.add_trace(go.Scatter(x=sub['Tolerance, Da'],y=sub.rate*100,mode='lines+markers',name=name,
                                             marker=dict(color=col,size=8),line=dict(color=col,width=2.5)))
    fig=style(fig,'Does the m/z Tolerance Change Apparent False Similarity?',
         f'{len(_v9_negs)} pairs of distinct structures · same pairs at every threshold',460)
    fig.update_layout(xaxis_title='Peak-matching tolerance, Da',yaxis_title='Pairs with cosine ≥ 0.8, %')
    show_chart(fig)
    display(_rates.round(4))
    for label,flag in [('dimeric',True),('other',False)]:
        base=_rates[(_rates['Tolerance, Da']==.02)&(_rates['Dimeric']==flag)]
        if len(base):
            print(f'At ±0.02 Da: {int(base.high.iloc[0])}/{int(base.n.iloc[0])} pairs {label} adduct pairs have cosine ≥ 0.8.')
else:print('No eligible pairs in the selected comparison set.')
