# CODE CELL 47 · Deep EDA
if len(counts):
    _holdouts=[.1,.2,.3,.5]
    _chance=[float(np.average(1-p**(counts.astype(float)-1),weights=counts)) for p in _holdouts]
    fig=go.Figure(go.Scatter(x=[100*p for p in _holdouts],y=[100*p for p in _chance],
       mode='lines+markers+text',text=[f'{100*x:.2f}%' for x in _chance],
       textposition='bottom center',line=dict(color=TEAL,width=4),marker=dict(size=12),
       hovertemplate='Validation share: %{x:.0f}%<br>Structure already in training: %{y:.2f}%<extra></extra>'))
    fig=style(fig,'Random Row Splits Usually Leave Familiar Structures',
       'Exact full training set · expected value weighted by spectra per structure',450)
    fig.update_layout(xaxis_title='Validation fraction, %',yaxis_title='Expected fraction of familiar structures, %',
                      yaxis_range=[min(75,100*min(_chance)-3),100],xaxis_range=[0,55])
    show_chart(fig)
    display(pd.DataFrame({'Validation, %':[int(p*100) for p in _holdouts],
           'Structure present in training (expected, %)':[100*p for p in _chance]}).round(3))
