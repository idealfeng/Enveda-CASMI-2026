# CODE CELL 31 · Deep EDA
v5_domain=background.copy()
v5_domain['mean_energy']=v5_domain.collision_energy_ev.map(
    lambda v:float(np.mean(v)) if v is not None and len(v) else np.nan)
v5_domain_summary=(v5_domain.groupby('ingest_lib',dropna=False)
   .agg(n=('num_peaks','size'),median_peaks=('num_peaks','median'),
        q25=('num_peaks',lambda v:v.quantile(.25)),q75=('num_peaks',lambda v:v.quantile(.75)),
        ce_available=('mean_energy',lambda v:v.notna().mean()),
        top_instrument=('instrument_type',lambda v:v.value_counts().index[0] if len(v.dropna()) else 'unknown'))
   .sort_values('n',ascending=False))
v5_domain_summary=v5_domain_summary[v5_domain_summary.n>=400].copy()
fig=go.Figure(go.Bar(
    x=v5_domain_summary.index.astype(str),y=v5_domain_summary.median_peaks,
    marker_color=[TEAL if x=='enveda-180' else BLUE for x in v5_domain_summary.index],
    customdata=np.column_stack([v5_domain_summary.n,v5_domain_summary.ce_available,
                               v5_domain_summary.top_instrument]),
    hovertemplate='%{x}<br>Median peaks: %{y:.0f}<br>Sample n: %{customdata[0]}'
                  '<br>CE recorded: %{customdata[1]:.0%}<br>Main instrument: %{customdata[2]}<extra></extra>'))
fig=style(fig,'One Dataset, Different Measurement Conditions',
   'Median peak count by library · 100k metadata sample',465)
fig.update_layout(xaxis_tickangle=-30,yaxis_title='Median peaks per spectrum')
show_chart(fig)
display(v5_domain_summary[['n','median_peaks','q25','q75','ce_available','top_instrument']]
        .rename(columns={'n':'Sample n','median_peaks':'Median peaks','q25':'P25','q75':'P75',
                         'ce_available':'Recorded CE','top_instrument':'Most common instrument'})
        .round(2))
note('Libraries and Instruments Are Linked',
     'Differences between libraries may reflect instruments, chemical composition, and signal processing. '
     'Test transfer to a held-out source.')
