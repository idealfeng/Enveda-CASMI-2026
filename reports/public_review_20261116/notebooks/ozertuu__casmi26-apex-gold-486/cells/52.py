# CODE CELL 26 · Deep EDA
# Masking control: compare groups using the same procedure.
def v7_residual_power(row):
    mz=np.asarray(row['ms2_mzs'],dtype=float)
    it=np.asarray(row['ms2_normalized_intensities'],dtype=float)
    mm,ii=v5_filter_ions(row,mz,it,remove_ion_envelopes=True)
    return float(np.dot(ii,ii)/(np.dot(it,it)+1e-12))

v7_groups={
    'Same structure, ΔCE ≤ 5 eV':v5_metrics[(v5_metrics.same_structure)&(v5_metrics.delta_e<=5)],
    'Different structures, dimer, cosine ≥ 0.8':v5_negative[(v5_negative.dimer)&(v5_negative.cosine>=.8)],
    'Different structures, non-dimer, cosine ≥ 0.8':v5_negative[(~v5_negative.dimer)&(v5_negative.cosine>=.8)],
    'Different structures, cosine < 0.8':v5_negative[v5_negative.cosine<.8]
}
v7_ablation=[]
for title,group in v7_groups.items():
    for p in group.head(150).itertuples(index=False):
        a=v5_records.get(p.a); b=v5_records.get(p.b)
        if a is None or b is None:continue
        score_after,_=v5_cosine(a,b,remove_ion_envelopes=True)
        residual=(v7_residual_power(a)+v7_residual_power(b))/2
        v7_ablation.append({'Group':title,'Before':p.cosine,
             'After':score_after if np.isfinite(score_after) else np.nan,
             'Retained signal power':residual})
v7_ablation=pd.DataFrame(v7_ablation)
if len(v7_ablation):
    med=v7_ablation.groupby('Group',sort=False).agg(
        n=('Before','size'),defined=('After','count'),before=('Before','median'),after=('After','median'),
        power=('Retained signal power','median')).reset_index()
    fig=go.Figure()
    fig.add_trace(go.Bar(x=med['Group'],y=med.before,name='Before masking',marker_color=BLUE))
    fig.add_trace(go.Bar(x=med['Group'],y=med.after,name='After masking',marker_color=CORAL))
    fig=style(fig,'Ion-Series Removal: Effect and Control',
        'Medians across comparable pairs · same masking procedure',525)
    fig.update_layout(barmode='group',xaxis_tickangle=-18,yaxis_title='Cosine similarity',
                      yaxis_range=[0,1.05])
    show_chart(fig)
    display(med.rename(columns={'n':'Pairs','before':'Cosine before','after':'Cosine after',
        'power':'Median retained power fraction','defined':'Pairs with remaining signal'}).round(4))
    note('Alternative-Explanation Control',
        'The retained-power column shows how much of the original signal '
        'was left for comparison after masking. Low values indicate '
        'little remaining signal, not proof of structural discrimination.')
else:
    print('No comparable pairs are available for the masking control.')