# CODE CELL 53 · Deep EDA
# Experiment 36: diagnostic reference-spectrum retrieval.
# Not competition MRR: the correct structure is included by design.
_v13_query=v13_records.dropna(subset=['precursor_mz']).copy()
_v13_query['v13_pmz']=pd.to_numeric(_v13_query.precursor_mz,errors='coerce')
_v13_query=_v13_query[_v13_query.v13_pmz.notna() & (_v13_query.v13_pmz>0)].copy()
_v13_samples=[]
_v13_unique=_v13_query.sort_values('v13_E').drop_duplicates('inchikey14',keep='first')
for key,g in _v13_query.groupby('inchikey14',sort=False):
    if len(g)<2:continue
    g=g.sort_values('v13_E')
    qry,truth=g.iloc[-1],g.iloc[0]
    if (qry.adduct!=truth.adduct or qry.instrument_type!=truth.instrument_type or
        qry.ingest_lib!=truth.ingest_lib):continue
    distract=_v13_unique[
        (_v13_unique.inchikey14!=key)&(_v13_unique.adduct==qry.adduct)&
        (_v13_unique.instrument_type==qry.instrument_type)&
        (_v13_unique.ingest_lib==qry.ingest_lib)&
        ((_v13_unique.v13_pmz-float(qry.v13_pmz)).abs()<=.2)
    ].copy()
    if len(distract)<2:continue
    distract=distract.assign(gap=(distract.v13_pmz-float(qry.v13_pmz)).abs()).nsmallest(24,'gap')
    qr=v5_records[(int(qry.row_group),int(qry.row_offset))]
    options=[(truth,True)]+[(r,False) for _,r in distract.iterrows()]
    scores=[]
    for candidate,is_true in options:
        cr=v5_records.get((int(candidate.row_group),int(candidate.row_offset)))
        if cr is None:continue
        sc,_=v8_symmetric_cosine(qr,cr)
        if np.isfinite(sc):scores.append((float(sc),bool(is_true)))
    if not scores or not any(is_true for _,is_true in scores):continue
    scores=sorted(scores,key=lambda z:z[0],reverse=True)
    rank=next(i+1 for i,(_,is_true) in enumerate(scores) if is_true)
    _v13_samples.append({'Structure':str(key),'Candidates':len(scores),
               'Rank':rank,'RR':1./rank,'ΔCE, eV':abs(float(qry.v13_E)-float(truth.v13_E)),
               'Adduct':str(qry.adduct)})
    if len(_v13_samples)>=200:break
v13_toy_rank=pd.DataFrame(_v13_samples)
if len(v13_toy_rank):
    fig=go.Figure()
    vc=v13_toy_rank['Rank'].clip(upper=6).value_counts().reindex(range(1,7),fill_value=0)
    fig.add_trace(go.Bar(x=['1','2','3','4','5','6+'],y=vc.values,
                         marker_color=[TEAL,BLUE,BLUE,BLUE,CORAL,CORAL],
                         text=vc.values,textposition='outside'))
    fig=style(fig,'Where Does the Correct Reference Rank in a Small Retrieval Test?',
       f'{len(v13_toy_rank)} queries · near-mass competing structures · best rank = 1',470)
    fig.update_layout(xaxis_title='Rank of the correct reference',yaxis_title='Number of queries')
    show_chart(fig)
    display(pd.DataFrame({'Metric':['Queries','Top-1 in selected retrieval',
         'Mean reciprocal rank','Median candidate count'],
         'Value':[len(v13_toy_rank),f"{(v13_toy_rank['Rank']==1).mean():.3f}",
             f"{v13_toy_rank.RR.mean():.3f}",f"{v13_toy_rank['Candidates'].median():.0f}"]}))
    note('Finding 36 · Diagnostic Retrieval Is Not the Leaderboard',
         'The correct structure is included by design, candidate lists are small, and familiar structures '
         'appear in the reference set. These figures are not competition generalization/MRR@25 estimates.')
else:
    print('No queries with at least two mass-matched competing structures under the chosen acquisition controls.')
