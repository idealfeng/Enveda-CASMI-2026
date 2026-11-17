# CODE CELL 16 · Deep EDA
# Within-structure comparison: near (<=5 eV) vs far (>=20 eV).
v5_positive=v5_metrics[(v5_metrics.same_structure)&(v5_metrics.same_adduct)&
                       (v5_metrics.same_instrument)&(v5_metrics.same_lib)&
                       v5_metrics.delta_e.notna()].copy()
v5_near=v5_positive[v5_positive.delta_e<=5].groupby('key_a').cosine.median()
v5_far=v5_positive[v5_positive.delta_e>=20].groupby('key_a').cosine.median()
v5_paired=pd.DataFrame({'Near (≤5 eV)':v5_near,'Far (≥20 eV)':v5_far}).dropna()

fig=go.Figure()
fig.add_trace(go.Scatter(x=v5_paired['Near (≤5 eV)'],y=v5_paired['Far (≥20 eV)'],
    mode='markers',name='Same structure',
    marker=dict(size=7,color=TEAL,opacity=.57,line=dict(width=.35,color='white')),
    hovertemplate='Near: %{x:.3f}<br>Far: %{y:.3f}<extra></extra>'))
fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',
    line=dict(color=CORAL,dash='dash',width=2),name='Equal similarity'))
fig=style(fig,'Same Structure, Different Spectral Fingerprints',
    f'{len(v5_paired)} structures · within-structure comparisons',490)
fig.update_layout(xaxis_title='Cosine · close energies',yaxis_title='Cosine · distant energies',
                  xaxis_range=[-0.02,1.02],yaxis_range=[-0.02,1.02])
show_chart(fig)

if len(v5_paired):
    improvement=(v5_paired['Near (≤5 eV)']>v5_paired['Far (≥20 eV)']).mean()
    display(pd.DataFrame({'Measure':['Structures compared','Median cosine · close energies',
        'Median cosine · distant energies','Fraction with higher cosine at close energies'],
        'Observed':[len(v5_paired),round(v5_paired['Near (≤5 eV)'].median(),3),
                    round(v5_paired['Far (≥20 eV)'].median(),3),f'{improvement:.1%}']}))
    note('Finding · The Role of Collision Energy',
         f'At close energies, cosine is higher for {improvement:.1%} '
         f'out of {len(v5_paired)} structures. This difference is observed '
         'under matched measurement conditions.')
