# CODE CELL 15 · Deep EDA
from bisect import bisect_left,bisect_right

def v8_symmetric_cosine(a,b,tol=MZ_TOL_DA,mask=False):
    def xy(row):
        mz=np.asarray(row['ms2_mzs'],dtype=np.float64)
        inten=np.asarray(row['ms2_normalized_intensities'],dtype=np.float64)
        if mask:
            mz,inten=v5_filter_ions(row,mz,inten,True)
        good=np.isfinite(mz)&np.isfinite(inten)&(inten>=0)
        mz,inten=mz[good],inten[good]
        order=np.argsort(mz)
        return mz[order],inten[order]
    am,ai=xy(a);bm,bi=xy(b)
    if not len(ai) or not len(bi):return np.nan,0
    na=np.linalg.norm(ai);nb=np.linalg.norm(bi)
    if na==0 or nb==0:return np.nan,0
    edges=[]
    for i,m in enumerate(am):
        lo=bisect_left(bm,m-tol);hi=bisect_right(bm,m+tol)
        for j in range(lo,hi):edges.append((ai[i]*bi[j],i,j))
    edges.sort(key=lambda x:x[0],reverse=True)
    used_a=set();used_b=set();dot=0.;matches=0
    for value,i,j in edges:
        if i not in used_a and j not in used_b:
            used_a.add(i);used_b.add(j);dot+=value;matches+=1
    return float(dot/(na*nb)),matches

v8_metrics=v5_metrics.copy()
v8_metrics['cosine_sym']=[v8_symmetric_cosine(v5_records[a],v5_records[b])[0]
                            for a,b in zip(v8_metrics.a,v8_metrics.b)]
_v8_valid=v8_metrics.dropna(subset=['cosine','cosine_sym'])
if len(_v8_valid):
    _diff=(_v8_valid.cosine-_v8_valid.cosine_sym).abs()
    print(f'Check: {len(_diff)} pairs: median |Δcosine| = {_diff.median():.4f} · 95th percentile = {_diff.quantile(.95):.4f} · Δ > 0.05: {int((_diff>.05).sum())}')
    if _diff.quantile(.95)>.005:
        fig=px.scatter(_v8_valid,x='cosine',y='cosine_sym',color='dimer',opacity=.6,
            labels={'cosine':'Original greedy cosine','cosine_sym':'Symmetric cosine','dimer':'Dimeric adduct'})
        fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',line=dict(color=CORAL,dash='dash'),
            showlegend=False))
        fig=style(fig,'Same Chemistry, Two Ways to Match Peaks',
            f'{len(_v8_valid)} comparable pairs · checking metric stability',460)
        fig.update_layout(xaxis_range=[-.03,1.03],yaxis_range=[-.03,1.03])
        show_chart(fig)
    else:
        note('Peak-Matching Control',
             'The difference between the two algorithms is small for these selected pairs. '             'We examine adducts, energies, and structures instead of mistaking a greedy-matching artifact for chemistry.')
