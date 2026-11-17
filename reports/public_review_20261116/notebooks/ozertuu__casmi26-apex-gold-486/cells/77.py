# CODE CELL 41 · Deep EDA
def greedy_cosine(row_a,row_b,tol=MZ_TOL_DA):
    am,ai=safe_peaks(row_a);bm,bi=safe_peaks(row_b)
    if not len(am) or not len(bm):return np.nan,0
    # 1:1 greedy on descending intensity; sampled demo, not exact optimal bipartite matching
    ia=np.argsort(ai)[::-1]; used=set();dot=0.0;n=0
    for k in ia:
        near=np.where(np.abs(bm-am[k])<=tol)[0]
        near=[j for j in near if j not in used]
        if not near:continue
        j=max(near,key=lambda jj:bi[jj]);used.add(j)
        dot+=ai[k]*bi[j];n+=1
    return float(dot/(np.linalg.norm(ai)*np.linalg.norm(bi)+1e-12)),n
if len(example)>=2:
    anchor=example.iloc[0];same=example.iloc[1]
    alternatives=spec[(spec.inchikey14!=anchor.inchikey14)&(spec.adduct==anchor.adduct)].copy()
    alternatives['mass_gap']=(pd.to_numeric(alternatives.precursor_mz,errors='coerce')-float(anchor.precursor_mz)).abs()
    alternatives=alternatives.sort_values('mass_gap').head(1)
    a_cos,a_match=greedy_cosine(anchor,same)
    rows=[{'Pair':'Same structure · two spectra','Cosine':a_cos,'Matched peaks':a_match,'Δ precursor m/z':abs(float(anchor.precursor_mz)-float(same.precursor_mz))}]
    if len(alternatives):
        b=alternatives.iloc[0];b_cos,b_match=greedy_cosine(anchor,b)
        rows.append({'Pair':'Different structures · nearby mass','Cosine':b_cos,'Matched peaks':b_match,'Δ precursor m/z':float(b.mass_gap)})
    display(pd.DataFrame(rows).round(4))
else:
    print('Comparison skipped: no two records sharing an InChIKey14 and instrument/adduct group were found in the diagnostic sample.')
note('Compare the Two','Pay attention to measurement conditions; their comparability matters as much as the cosine score.')