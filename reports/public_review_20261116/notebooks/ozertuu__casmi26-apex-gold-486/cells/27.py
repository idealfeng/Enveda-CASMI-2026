# CODE CELL 14 · Deep EDA
# Symmetry control: one pair, both greedy-matching directions.
v7_direction=[]
for p in v5_metrics.sort_values('cosine',ascending=False).head(350).itertuples(index=False):
    a=v5_records.get(p.a);b=v5_records.get(p.b)
    if a is None or b is None:continue
    reverse,_=v5_cosine(b,a)
    if np.isfinite(reverse) and np.isfinite(p.cosine):
        v7_direction.append({'Similarity A→B':p.cosine,'Similarity B→A':reverse,
            'Same structure':bool(p.same_structure)})
v7_direction=pd.DataFrame(v7_direction)
if len(v7_direction):
    drift=np.abs(v7_direction['Similarity A→B']-v7_direction['Similarity B→A'])
    fig=px.scatter(v7_direction,x='Similarity A→B',y='Similarity B→A',
       color='Same structure',opacity=.7)
    fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',
       name='Perfect symmetry',line=dict(color=CORAL,dash='dash')))
    fig=style(fig,'Same Pair — Same Cosine?',
       'Up to 350 high-cosine pairs · greedy-matching symmetry check',465)
    fig.update_layout(xaxis_range=[-.02,1.02],yaxis_range=[-.02,1.02])
    show_chart(fig)
    display(pd.DataFrame({'Metric':['Pairs checked','Median |A→B − B→A|',
                                     '95th percentile of discrepancy','Pairs with discrepancy > 0.05'],
       'Result':[len(v7_direction),round(float(drift.median()),4),
                    round(float(drift.quantile(.95)),4),int((drift>.05).sum())]}))
