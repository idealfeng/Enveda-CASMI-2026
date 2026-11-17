# CODE CELL 21 · Deep EDA
v5_negative=v5_metrics[(~v5_metrics.same_structure)&v5_metrics.same_adduct&
                       v5_metrics.same_instrument].copy()
v5_negative['high_similarity']=v5_negative.cosine>=.8

group=v5_negative.groupby('dimer').high_similarity.agg(['sum','count']).reindex([False,True],fill_value=0)
group['share']=group['sum']/group['count'].replace(0,np.nan)
fig=go.Figure()
fig.add_trace(go.Bar(x=['Other adducts','Dimeric adducts'],y=100*group['share'],
   marker_color=[BLUE,CORAL],
   text=[f'{int(x)}/{int(y)}' for x,y in zip(group['sum'],group['count'])],
   textposition='outside',
   hovertemplate='%{x}<br>Share with high cosine: %{y:.1f}%<br>%{text} pairs<extra></extra>'))
fig=style(fig,'Different Structures, Almost Identical Spectra?',
  'Fraction with cosine ≥ 0.80 among different-structure, near-precursor pairs',470)
fig.update_layout(yaxis_title='Pairs with cosine ≥ 0.80 (%)',yaxis_range=[0,max(30,100*group.share.max()*1.25)])
show_chart(fig)

high=v5_negative[v5_negative.high_similarity].copy()
n_dimer=int(high.dimer.sum())
if len(high):
    note('Finding · Check the Adduct',
         f'{len(high)} different-structure pairs have cosine ≥ 0.80; '
         f'{n_dimer} ({n_dimer/len(high):.1%}) are dimeric adducts. '
         'These are challenging pairs selected for similar precursor masses. '
         'Next, investigate the role of shared monomer-ion signals.',CORAL)
