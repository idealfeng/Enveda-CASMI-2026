# CODE CELL 24 · Deep EDA
def v9_toppeak_power(row):
    y=np.asarray(row['ms2_normalized_intensities'],dtype=float)
    y=y[np.isfinite(y)&(y>=0)]
    q=float(np.dot(y,y))
    return float(np.max(y*y)/q) if len(y) and q>0 else np.nan
_v9_peak_power={key:v9_toppeak_power(row) for key,row in v5_records.items()}
_v9_dominance=_v9_negs.copy()
_v9_dominance['Strongest-peak power fraction']=[np.nanmean([_v9_peak_power.get(a,np.nan),_v9_peak_power.get(b,np.nan)])
                                                for a,b in zip(_v9_dominance.a,_v9_dominance.b)]
_v9_dominance['High cosine']=_v9_dominance.cosine_sym>=.8
_v9_dominance['Group']=np.where(_v9_dominance.dimer,'Dimer','Other adduct')
_v9_dominance=_v9_dominance.dropna(subset=['Strongest-peak power fraction','cosine_sym'])
if len(_v9_dominance):
    fig=px.scatter(_v9_dominance,x='Strongest-peak power fraction',y='cosine_sym',
                   color='Group',color_discrete_map={'Dimer':CORAL,'Other adduct':BLUE},
                   opacity=.7,hover_data=['key_a','key_b'])
    fig=style(fig,'When One Peak Dominates, Cosine Can Mislead',
              f'{len(_v9_dominance)} distinct-structure control pairs',460)
    fig.update_layout(xaxis_title='Mean fraction of squared intensity in the strongest peak',
                      yaxis_title='Symmetric cosine')
    show_chart(fig)
    t=_v9_dominance.assign(quarter=lambda d:pd.cut(d['Strongest-peak power fraction'],
                    bins=[0,.25,.50,.75,1.000001],labels=['0–25%','25–50%','50–75%','75–100%'],include_lowest=True))
    _v9_dom_summary=t.groupby(['Group','quarter'],observed=True).agg(
        **{'Number of pairs':('High cosine','size'),'Fraction with cosine ≥ 0.8':('High cosine','mean')}).reset_index()
    display(_v9_dom_summary.round(3))
    if len(_v9_dom_summary):
        print('Compare both the percentage and the number of pairs in each group.')
