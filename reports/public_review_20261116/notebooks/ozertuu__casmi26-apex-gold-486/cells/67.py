# CODE CELL 34 · Deep EDA
def energy_list(v):
    if v is None: return []
    if isinstance(v,(list,tuple,np.ndarray)):
        z=v
    else:
        try: z=[v] if pd.notna(v) else []
        except Exception: z=[]
    out=[]
    for el in z:
        try:
            val=float(el)
            if np.isfinite(val):out.append(val)
        except (TypeError,ValueError):pass
    return out

meta['energies']=meta.collision_energy_ev.map(energy_list) if 'collision_energy_ev' in meta else [[] for _ in range(len(meta))]
meta['n_energies']=meta.energies.map(len)
meta['mean_ev']=meta.energies.map(lambda z:float(np.mean(z)) if z else np.nan)
if 'ingest_lib' in meta:
    d=meta.loc[meta.mean_ev.notna(),['ingest_lib','mean_ev']].copy()
    common=d.ingest_lib.value_counts().head(7).index
    d=d[d.ingest_lib.isin(common)]
    if len(d):
        fig=px.box(d,x='ingest_lib',y='mean_ev',color='ingest_lib',points=False)
        fig=style(fig,'Collision Energies Differ Across Sources','Sample · mean energy for merged records',455)
        fig.update_xaxes(tickangle=-20)
        show_chart(fig)
print('Spectra with multiple recorded energy values:',int((meta.n_energies>1).sum()))
note('Interpretation','When collision energy is recorded as an array, its mean is a summary, not the energy of one collision event.',GOLD)