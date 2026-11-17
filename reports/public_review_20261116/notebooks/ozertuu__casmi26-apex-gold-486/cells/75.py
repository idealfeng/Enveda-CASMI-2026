# CODE CELL 40 · Deep EDA
LOSSES={'H₂O':18.010565,'NH₃':17.026549,'CO':27.994915,'CO₂':43.989829,'CH₃OH':32.026215,'HCN':27.010899}
if len(example):
    row=example.iloc[0]; mz,iv=safe_peaks(row)
    precursor=float(row.precursor_mz)
    loss=precursor-mz
    good=(loss>0)&(iv>=0.03)
    hits=[]
    for name, mass in LOSSES.items():
        idx=np.where(good & (np.abs(loss-mass)<=MZ_TOL_DA))[0]
        for j in idx:hits.append({'Candidate':name,'Exact neutral-loss mass, Da':mass,'Observed loss, Da':loss[j],
                                  'Deviation, mDa':1000*(loss[j]-mass),'Intensity':iv[j]})
    fig=go.Figure(go.Scatter(x=loss[good],y=iv[good],mode='markers',marker=dict(size=8,color=TEAL,opacity=.65),name='observed'))
    for name,mass in LOSSES.items():fig.add_vline(x=mass,line_dash='dash',line_color=BLUE,opacity=.45,annotation_text=name,annotation_position='top')
    fig=style(fig,'Which Neutral Losses Appear in This Spectrum?','One spectrum · ±0.02 Da tolerance · singly charged ions',445)
    fig.update_layout(xaxis_title='Precursor m/z − fragment m/z, Da',yaxis_title='Normalized intensity')
    fig.update_xaxes(range=[0,max(70,float(np.quantile(loss[good],.90))) if good.any() else 70])
    show_chart(fig)
    display(pd.DataFrame(hits).sort_values('Intensity',ascending=False) if hits else pd.DataFrame({'Message':['No matches were found in this spectrum at the chosen tolerance.']}))
note('What the Mass Gaps Suggest','The same neutral-loss mass can have multiple chemical explanations. Confirming fragment formulas is a separate step.',GOLD)