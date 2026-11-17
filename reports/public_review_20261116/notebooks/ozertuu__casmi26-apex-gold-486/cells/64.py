# CODE CELL 32 · Deep EDA
_libs=v5_domain.ingest_lib.value_counts().head(8).index
_insts=v5_domain.instrument_type.value_counts().head(10).index
_v8_cross=pd.crosstab(v5_domain.ingest_lib,v5_domain.instrument_type)
_v8_cross=_v8_cross.reindex(index=_libs,columns=_insts,fill_value=0)
_v8_rate=_v8_cross.div(_v8_cross.sum(axis=1).replace(0,np.nan),axis=0)*100
fig=go.Figure(go.Heatmap(z=_v8_rate.to_numpy(),x=_v8_rate.columns.tolist(),
    y=_v8_rate.index.tolist(),
    colorscale=[[0,'#F1F8F9'],[.25,'#BCE7E4'],[.6,'#438D9C'],[1,'#0C5B78']],
    colorbar=dict(title='Share, %'),
    customdata=_v8_cross.to_numpy(),
    hovertemplate='Source: %{y}<br>Instrument: %{x}<br>Fraction: %{z:.1f}%<br>Sample records: %{customdata}<extra></extra>'))
fig=style(fig,'Each Library Has Its Own Instrument Profile',
    'Within each row, shares across shown instruments sum to 100%',515)
fig.update_layout(xaxis_tickangle=-35,yaxis_title='',xaxis_title='Instrument type')
show_chart(fig)
