# CODE CELL 05 · Deep EDA
# Full training set: concentration of measurements across molecular structures.
if len(counts):
    ordered=np.sort(counts.astype(np.float64))
    share_struct=np.arange(len(ordered)+1)/len(ordered)
    share_spectra=np.r_[0,ordered.cumsum()/ordered.sum()]
    n_top=max(1,int(np.ceil(.01*len(ordered))))
    top_1=float(ordered[-n_top:].sum()/ordered.sum())
    single=int(np.sum(counts==1))
    repeated=int(np.sum(counts>1))
    gini=float(1 - 2*ordered.cumsum().sum()/(len(ordered)*ordered.sum()) + 1/len(ordered))
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=share_struct*100,y=share_spectra*100,mode='lines',
        fill='tozeroy',line=dict(color=TEAL,width=3),name='Cumulative share of spectra'))
    fig.add_trace(go.Scatter(x=[0,100],y=[0,100],mode='lines',
        line=dict(color=CORAL,dash='dash',width=2),name='Equal measurements per structure'))
    fig=style(fig,'Not All Structures Are Measured Equally Often',
        'Full training set · structures sorted by number of spectra',485)
    fig.update_layout(xaxis_title='Share of structures, %',yaxis_title='Share of spectra, %')
    show_chart(fig)
    display(pd.DataFrame({
        'Metric':['Structures with one spectrum','Structures with repeated spectra',
                      'Spectra from the top 1% of structures','Gini coefficient of spectra per structure'],
        'Result':[f'{single:,}',f'{repeated:,} ({repeated/len(counts):.1%})',
                     f'{top_1:.1%}',f'{gini:.3f}']
    }))
    note('What the Long Tail Reveals',
        f'The most frequently measured 1% of structures contribute {top_1:.1%} spectra. '
        'This changes what a randomly selected row means in validation.')