# CODE CELL 35 · Deep EDA
if 'precursor_error_ppm' in meta and 'ingest_lib' in meta:
    ppm=meta[['ingest_lib','precursor_error_ppm']].copy()
    ppm['ppm']=pd.to_numeric(ppm.precursor_error_ppm,errors='coerce')
    ppm=ppm.dropna(subset=['ppm']);ppm=ppm[np.isfinite(ppm.ppm)]
    ppm['abs_ppm']=ppm.ppm.abs()
    common=ppm.ingest_lib.value_counts().head(8).index
    s=ppm[ppm.ingest_lib.isin(common)].copy()
    if len(s):
        s['log10_abs_ppm']=np.log10(s.abs_ppm.clip(lower=1e-4))
        fig=px.box(s,x='ingest_lib',y='log10_abs_ppm',color='ingest_lib',points=False)
        fig=style(fig,'Precursor Mass Accuracy by Data Source','Sample · log10 of absolute mass error (ppm)',450)
        fig.update_xaxes(tickangle=-23)
        show_chart(fig)
        display(s.groupby('ingest_lib').abs_ppm.agg(['count','median',lambda v:(v>10).mean()]).rename(columns={'<lambda_0>':'share_above_10ppm'}).sort_values('median').round(4))
note('Important','Mass error is calculated using the known structure. It is a diagnostic quality measure, not a readily available test feature.',CORAL)