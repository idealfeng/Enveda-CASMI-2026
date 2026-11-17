# CODE CELL 38 · Deep EDA
fig=go.Figure()
labels=[]
for i,(_,row) in enumerate(example.iterrows()):
    mz,iv=safe_peaks(row);xx,yy=sticks(mz,iv)
    label=f"Spectrum {i+1} | CE={row.mean_ev:.1f}eV" if pd.notna(row.mean_ev) else f'Spectrum {i+1} | CE unknown'
    labels.append(label)
    fig.add_trace(go.Scatter(x=xx,y=yy,mode='lines',name=label,visible=(i==0),line=dict(color=TEAL,width=1.5),hoverinfo='x+y'))
if len(fig.data)>1:
    fig.update_layout(updatemenus=[dict(type='dropdown',x=1,xanchor='right',y=1.20,
      buttons=[dict(label=lab,method='update',args=[{'visible':[j==i for j in range(len(fig.data))]}]) for i,lab in enumerate(labels)])])
fig=style(fig,'MS/MS Laboratory · Selected Spectrum','First recorded spectrum shown; measurement conditions are listed below',455)
fig.update_layout(xaxis_title='m/z',yaxis_title='Normalized intensity',showlegend=False)
show_chart(fig)
display(example[[c for c in ['spectrum_id','ingest_lib','adduct','instrument_type','mean_ev','precursor_mz'] if c in example]].reset_index(drop=True))
note('Observation','Notice which peaks disappear or intensify as energy changes; the measurement conditions appear below the figure.')