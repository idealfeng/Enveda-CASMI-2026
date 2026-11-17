# CODE CELL 25 · Deep EDA
# Re-score only the high-cosine negative pairs, using precisely the same matching routine.
v5_high=v5_negative[v5_negative.cosine>=.8].copy()
v5_high['masked_cosine']=[v5_cosine(v5_records[a],v5_records[b],
                               remove_ion_envelopes=True)[0]
                               for a,b in zip(v5_high.a,v5_high.b)]

fig=go.Figure()
for is_dimer,color,title in [(True,CORAL,'Dimeric adduct'),(False,BLUE,'Other adduct')]:
    g=v5_high[v5_high.dimer==is_dimer]
    fig.add_trace(go.Scatter(x=g.cosine,y=g.masked_cosine,mode='markers',name=f'{title} (n={len(g)})',
        marker=dict(color=color,size=9,opacity=.74,line=dict(width=.5,color='white')),
        customdata=np.stack([g.key_a,g.key_b],axis=1) if len(g) else None,
        hovertemplate='Original: %{x:.3f}<br>After masking: %{y:.3f}<extra></extra>'))
fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',
   line=dict(color='#9DACB6',width=1.5,dash='dash'),showlegend=False))
fig=style(fig,'Removing Ion Series: What Drove the High Similarity?',
   'Ion-series masking among different-structure pairs with high original cosine',480)
fig.update_layout(xaxis_title='Original cosine',yaxis_title='Cosine after ion-series masking',
                  xaxis_range=[-.02,1.02],yaxis_range=[-.02,1.02])
show_chart(fig)
if len(v5_high):
    m0=v5_high.cosine.median();m1=v5_high.masked_cosine.median()
    note('Finding · High Cosine Does Not Mean Rich Structural Evidence',
       f'For {len(v5_high)} different-structure pairs, median cosine changed '
       f'from {m0:.3f} to {m1:.4f} after masking the ion series. '
       'The next control shows how much original signal survived '
       'after removing these peaks.')
