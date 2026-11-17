# CODE CELL 50 · Deep EDA
# Experiment 33: same spectrum pairs, controlling for changing peak counts.
if len(v13_entropy_pairs):
    t=v13_entropy_pairs.copy()
    t['Peak count change, %']=100*(t['Peaks, high']-t['Peaks, low'])/t['Peaks, low'].clip(lower=1)
    t['Group']=np.where(t['Peak count change, %'].abs()<=20,
        'Change ≤ 20%', 'Change > 20%')
    fig=px.scatter(t,x='Peak count change, %',y='Δentropy',color='Group',
       color_discrete_map={'Change ≤ 20%':TEAL,'Change > 20%':CORAL},
       hover_data=['Structure','ΔCE, eV','Source'],opacity=.7)
    fig.add_hline(y=0,line_dash='dash',line_color='#8FA6A8')
    fig.add_vline(x=0,line_dash='dot',line_color='#8FA6A8')
    fig=style(fig,'Entropy or Just Peak Count?',
       'Same cohort as Experiment 32 · color shows the retained peak count change',470)
    fig.update_layout(xaxis_title='Peak count change as CE rises, %',yaxis_title='Δ normalized entropy')
    show_chart(fig)
    res=t.groupby('Group')['Δentropy'].agg(['size','median']).rename(
        columns={'size':'Structure count','median':'Median Δentropy'})
    display(res.round(3))
    note('Finding 33 · Inspect Both Groups',
         'If the effect disappears when peak count is almost unchanged, '
         'spectral processing rather than collision energy may explain part of the pattern.')
else:
    print('Experiment 33 skipped: Experiment 32 found no matched pairs.')
