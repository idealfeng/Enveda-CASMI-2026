# CODE CELL 51 · Deep EDA
# Experiment 34: a cross-library comparability ladder.
_v13_cross=[];_v13_inner=[]
_v13_transfer=v5_specs[v5_specs['selection_role'].eq('same_structure_focus')].copy()
_v13_transfer['v13_E']=_v13_transfer['collision_energy_ev'].map(mean_energy)
for key,g in _v13_transfer.groupby('inchikey14',sort=False):
    if len(g)<2:continue
    g=g.head(8)
    for a,b in combinations(g.itertuples(index=False),2):
        d=abs(float(a.v13_E)-float(b.v13_E)) if np.isfinite(a.v13_E) and np.isfinite(b.v13_E) else np.nan
        row={'Structure':str(key),'Different libraries':str(a.ingest_lib)!=str(b.ingest_lib),
             'Same adduct':str(a.adduct)==str(b.adduct),
             'Same instrument':str(a.instrument_type)==str(b.instrument_type),
             'ΔCE ≤ 5 eV':d<=5,'a':(int(a.row_group),int(a.row_offset)),
             'b':(int(b.row_group),int(b.row_offset))}
        (_v13_cross if row['Different libraries'] else _v13_inner).append(row)
v13_cross=pd.DataFrame(_v13_cross)
v13_inner=pd.DataFrame(_v13_inner)
steps=[('Same structure',lambda d:np.ones(len(d),dtype=bool)),
       ('+ Same adduct',lambda d:d['Same adduct']),
       ('+ Same instrument',lambda d:d['Same adduct'] & d['Same instrument']),
       ('+ ΔCE ≤ 5 eV',lambda d:d['Same adduct'] & d['Same instrument'] & d['ΔCE ≤ 5 eV'])]
if len(v13_cross):
    ladder=[]
    for label,f in steps:
        sub=v13_cross[f(v13_cross)]
        ladder.append({'Control':label,'Pairs':len(sub),'Structures':sub['Structure'].nunique()})
    display(pd.DataFrame(ladder))
    fig=go.Figure(go.Bar(x=[r['Control'] for r in ladder],y=[r['Structures'] for r in ladder],
       marker_color=[BLUE,TEAL,'#399F91',CORAL],
       text=[f"{r['Structures']} structures" for r in ladder],textposition='outside'))
    fig=style(fig,'Comparability Ladder: What Can Be Compared Across Libraries?',
              'Same structure does not imply identical acquisition conditions · diagnostic cohort',480)
    fig.update_layout(yaxis_title='Unique structures',xaxis_tickangle=-10)
    show_chart(fig)
    # Matched pairs: within versus across source libraries.
    selected=[]
    for label,frame in [('Across libraries',v13_cross),('Within library',v13_inner)]:
        if frame.empty:continue
        sub=frame[steps[-1][1](frame)].sort_values('Structure').drop_duplicates('Structure').head(300)
        for p in sub.itertuples(index=False):
            sc,_=v8_symmetric_cosine(v5_records[p.a],v5_records[p.b])
            if np.isfinite(sc):selected.append({'Control':label,'Structure':p[0],'Cosine':sc})
    panel=pd.DataFrame(selected)
    if len(panel) and panel['Control'].nunique()==2:
        fig=px.box(panel,x='Control',y='Cosine',points='all',color='Control',
                   color_discrete_sequence=[TEAL,CORAL])
        fig=style(fig,'One `inchikey14`: Within vs Across Libraries',
                  'Same adduct and instrument · ΔCE ≤ 5 eV · at most one pair per structure and group',440)
        fig.update_layout(yaxis_range=[0,1.04]);show_chart(fig)
        display(panel.groupby('Control').Cosine.agg(['count','median']).rename(columns={'count':'Pairs','median':'Median cosine'}))
    else:print('Not enough matched observations in both groups for a controlled cosine comparison.')
else:
    print('No cross-library pairs of the same structure were found in the diagnostic cohort.')
