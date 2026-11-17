# CODE CELL 06 · Deep EDA
if len(counts):
    ordered=np.sort(counts)[::-1]
    proportions=[.001,.01,.05,.10]
    concentration=[]
    for share in proportions:
        k=max(1,int(np.ceil(share*len(ordered))))
        concentration.append({'Share of structures, %':100*share,'Share of spectra, %':100*ordered[:k].sum()/ordered.sum(),
                              'Structures':k,'Spectra':int(ordered[:k].sum())})
    v8_concentration=pd.DataFrame(concentration)
    fig=go.Figure(go.Bar(x=v8_concentration['Share of spectra, %'],
        y=[f"Top {x:g}%" for x in v8_concentration['Share of structures, %']],orientation='h',
        marker_color=[BLUE,TEAL,'#53A89F',GOLD],
        text=[f'{x:.1f}%' for x in v8_concentration['Share of spectra, %']],textposition='outside',
        hovertemplate='%{y}<br>Share of spectra: %{x:.2f}%<extra></extra>'))
    fig=style(fig,'A Minority of Structures Account for Most Spectra',
        'Exact full-training counts · observations from the most frequently measured structures',405)
    fig.update_layout(xaxis_title='Share of all spectra, %',yaxis_title='',xaxis_range=[0,53])
    show_chart(fig)
    display(v8_concentration.round(2))
    note('Finding · Molecules Have Unequal Weights',
         f'The top 10% of structures account for {v8_concentration.iloc[-1]["Share of spectra, %"]:.1f}% of all measurements. '
         'This is a meaningful difference between row-weighting and structure-weighting.')
