# CODE CELL 49 · Deep EDA
# Experiment 32: spectral entropy with matched structure and acquisition context.
from itertools import combinations

def v13_entropy(row):
    yy=np.asarray(row['ms2_normalized_intensities'], dtype=float)
    yy=yy[np.isfinite(yy)&(yy>0)]
    if len(yy)<3 or yy.sum()<=0: return np.nan
    p=yy/yy.sum()
    return float(-(p*np.log(p)).sum()/np.log(len(p)))

v13_records=v5_specs.copy()
v13_records['v13_E']=v13_records['collision_energy_ev'].map(mean_energy)
v13_records['v13_H']=[v13_entropy(r) for _,r in v13_records.iterrows()]
v13_records=v13_records[v13_records['selection_role'].eq('same_structure_focus') &
                         v13_records.v13_E.notna() & v13_records.v13_H.notna()].copy()
_v13_e=[]
for keys,g in v13_records.groupby(['inchikey14','adduct','instrument_type','ingest_lib'],dropna=False,sort=False):
    g=g.sort_values('v13_E')
    if len(g)<2:continue
    low,high=g.iloc[0],g.iloc[-1]
    delta=float(high.v13_E-low.v13_E)
    if delta < 10:continue
    _v13_e.append({'Structure':str(keys[0]),'Source':str(keys[3]),
                   'ΔCE, eV':delta,'Low energy':low.v13_H,
                   'High energy':high.v13_H,'Δentropy':high.v13_H-low.v13_H,
                   'Peaks, low':len(low.ms2_mzs),'Peaks, high':len(high.ms2_mzs)})
v13_entropy_pairs=pd.DataFrame(_v13_e)
if len(v13_entropy_pairs):
    d=v13_entropy_pairs['Δentropy'].to_numpy(dtype=float)
    rng=np.random.default_rng(20261113)
    bootstrap=np.median(rng.choice(d,size=(1200,len(d)),replace=True),axis=1)
    lo,hi=np.quantile(bootstrap,[.025,.975])
    fig=make_subplots(rows=1,cols=2,subplot_titles=('Within-structure matched pairs','Intensity distribution shift'))
    for _,p in v13_entropy_pairs.head(90).iterrows():
        fig.add_trace(go.Scatter(x=[0,1],y=[p['Low energy'],p['High energy']],
          mode='lines',line=dict(color='rgba(52,118,126,.25)',width=1),showlegend=False,
          hovertemplate=f"Structure: {p['Structure']}<br>Entropy: %{{y:.3f}}<extra></extra>"),row=1,col=1)
    fig.add_trace(go.Box(y=d,boxpoints='all',jitter=.32,pointpos=0,
       marker=dict(color=TEAL,size=4,opacity=.4),line=dict(color=BLUE),name='Δentropy',showlegend=False),row=1,col=2)
    fig.add_hline(y=0,line_dash='dash',line_color=CORAL,row=1,col=2)
    fig=style(fig,'Collision Energy and Spectral Entropy',f'One pair per structure · n={len(d)} · structure-level bootstrap',height=460)
    fig.update_xaxes(tickvals=[0,1],ticktext=['Low CE','High CE'],row=1,col=1)
    fig.update_yaxes(title_text='Normalized entropy',range=[0,1.05],row=1,col=1)
    fig.update_yaxes(title_text='Δentropy',row=1,col=2)
    show_chart(fig)
    display(pd.DataFrame({'Check':['Matched structures','Median Δentropy','95% bootstrap CI'],
        'Result':[len(d),f'{np.median(d):+.3f}',f'[{lo:+.3f}; {hi:+.3f}]']}))
    note('Finding 32 · Entropy is not identifiability',
         f'Across {len(d)} matched structures, the median paired difference was {np.median(d):+.3f}. '
         f'Bootstrap interval [{lo:+.3f}, {hi:+.3f}]. This concerns intensity distribution, not MRR@25.')
else:
    print('Experiment 32: no within-structure pairs with ΔCE ≥ 10 eV under matched acquisition conditions.')
