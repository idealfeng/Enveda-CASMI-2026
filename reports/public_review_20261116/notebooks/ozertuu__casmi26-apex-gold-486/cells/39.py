# CODE CELL 20 · Deep EDA
# For each structure: its own distant-energy pair versus a near-mass different-structure candidate.
v7_self=(v5_metrics[v5_metrics.same_structure & v5_metrics.same_lib &
     v5_metrics.same_adduct & v5_metrics.same_instrument &
     (v5_metrics.delta_e>=20)]
   .groupby('key_a').cosine.median())
v7_other=(v5_metrics[(~v5_metrics.same_structure) &
     v5_metrics.same_adduct & v5_metrics.same_instrument &
     (v5_metrics.precursor_gap<=MAX_MASS_GAP_DA)]
   .groupby('key_a').cosine.max())
v7_twins=pd.concat({'Same structure, ΔCE ≥ 20':v7_self,
                    'Different structure, nearby m/z':v7_other},axis=1).dropna()
if len(v7_twins):
    v7_twins['Other structure closer']=v7_twins.iloc[:,1]>v7_twins.iloc[:,0]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=v7_twins.iloc[:,0],y=v7_twins.iloc[:,1],
        mode='markers',marker=dict(size=8,color=np.where(v7_twins['Other structure closer'],CORAL,TEAL),
            opacity=.7),name='Matched structure'))
    fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',
        line=dict(color=INK,dash='dash'),name='Equal similarity'))
    fig=style(fig,'When Another Structure Looks More Similar Than Your Own',
        f'{len(v7_twins)} structures with both comparison types · challenging near-mass candidates',485)
    fig.update_layout(xaxis_title='Cosine · same structure, different energy',
       yaxis_title='Cosine · other structure, nearby m/z',
       xaxis_range=[-.02,1.02],yaxis_range=[-.02,1.02])
    show_chart(fig)
    count=int(v7_twins['Other structure closer'].sum())
    note('The Paradox in Numbers',
        f'For {count} out of {len(v7_twins)} structures ({count/len(v7_twins):.1%}) '
        'the selected other-structure spectrum had higher cosine than a spectrum of the same structure '
        'recorded at a more distant collision energy.')
else:
    print('The selected cohort contains no structures with both types of comparison.')