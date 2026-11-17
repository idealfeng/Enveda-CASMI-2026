# CODE CELL 28 · Deep EDA
def v9_power_matched_row(row):
    mz=np.asarray(row['ms2_mzs'],dtype=float)
    it=np.asarray(row['ms2_normalized_intensities'],dtype=float)
    if len(it)==0:return dict(row)
    target=v7_residual_power(row)
    p=it**2
    total=float(p.sum())
    keep=np.ones(len(p),dtype=bool)
    if not np.isfinite(target) or total<=0:return dict(row)
    residual=1.0
    for idx in np.argsort(p)[::-1]:
        if residual<=target+1e-12:break
        keep[idx]=False
        residual-=float(p[idx]/total)
    out=dict(row)
    out['ms2_mzs']=mz[keep]
    out['ms2_normalized_intensities']=it[keep]
    return out

_v9_placebo_pairs=v8_metrics[(~v8_metrics.same_structure)&v8_metrics.same_adduct&
    v8_metrics.same_instrument&v8_metrics.dimer&(v8_metrics.cosine_sym>=.8)].copy()
_v9_placebo_pairs=_v9_placebo_pairs.sort_values(['key_a','key_b']).head(100)
_v9_placebo=[]
for p in _v9_placebo_pairs.itertuples(index=False):
    a,b=v5_records[p.a],v5_records[p.b]
    original=p.cosine_sym
    chemical=v8_symmetric_cosine(a,b,mask=True)[0]
    placebo=v8_symmetric_cosine(v9_power_matched_row(a),v9_power_matched_row(b))[0]
    remaining=(v7_residual_power(a)+v7_residual_power(b))/2
    _v9_placebo.append({'Original':original,'Ion-series mask':chemical,'Power-matched control':placebo,
                        'Remaining power':remaining,'A':str(p.key_a),'B':str(p.key_b)})
_v9_placebo=pd.DataFrame(_v9_placebo)
if len(_v9_placebo):
    compare=[('Original',BLUE),('Ion-series mask',CORAL),('Power-matched control',TEAL)]
    fig=go.Figure()
    for name,col in compare:
        data=_v9_placebo[name].dropna()
        fig.add_trace(go.Bar(x=[name],y=[float(data.median()) if len(data) else 0],
              marker_color=col,name=name))
    fig=style(fig,'Does Similarity Vanish Simply Because Most Signal Was Removed?',
        f'{len(_v9_placebo)} dimeric distinct-structure pairs with original cosine ≥ 0.8',465)
    fig.update_layout(yaxis_title='Median cosine for defined comparisons',
                      yaxis_range=[0,1.05],showlegend=False)
    show_chart(fig)
    display(pd.DataFrame([{'Condition':name,'Pairs with defined cosine':int(_v9_placebo[name].notna().sum()),
        'Median cosine':float(_v9_placebo[name].median()) if _v9_placebo[name].notna().any() else np.nan}
          for name,_ in compare]).round(4))
    print(f'Median remaining power after ion masking: {_v9_placebo["Remaining power"].median():.3%}.')
    print('Pairs with no remaining peaks are not assigned an artificial zero cosine.')
    if _v9_placebo['Ion-series mask'].notna().any() and _v9_placebo['Power-matched control'].notna().any():
        note('Finding · Power-Matched Control',
          f'Median cosine after ion masking = {_v9_placebo["Ion-series mask"].median():.3f}; '
          f'after power-matched removal = {_v9_placebo["Power-matched control"].median():.3f}. '
          'Their difference reveals how much of the masking effect remains after controlling for the power of removed peaks.')
else:print('No dimeric pairs with cosine ≥ 0.8 were found in this selected set.')
