# CODE CELL 62 · Deep EDA
# Summarize errors by chemical formula, not as independent rows.
_v18_r = v16_R.copy()
_v18_r['mistake'] = _v18_r['rank'].ne(1).astype(int)
_v18_f = _v18_r.groupby('formula', sort=True).agg(n=('mistake','size'), mistakes=('mistake','sum'))
_v18_hist = _v18_f['mistakes'].value_counts().to_dict()
_v18_n_bad = int(_v18_f['mistakes'].gt(0).sum())
_v18_total_bad = int(_v18_f['mistakes'].sum())
_v18_micro = float(_v18_r['rank'].eq(1).mean())
_v18_macro = float((1 - _v18_f['mistakes']/_v18_f['n']).mean())
# Cluster bootstrap: resample whole molecular formulas.
_v18_rng = np.random.default_rng(20261111)
_v18_m = _v18_f['mistakes'].to_numpy()
_v18_n = _v18_f['n'].to_numpy()
_v18_boot = np.empty(2500)
for _v18_i in range(len(_v18_boot)):
    _v18_ix = _v18_rng.integers(0, len(_v18_f), size=len(_v18_f))
    _v18_boot[_v18_i] = 1 - _v18_m[_v18_ix].sum() / _v18_n[_v18_ix].sum()
_v18_ci = np.quantile(_v18_boot, [.025,.975])
fig, (ax, ay) = plt.subplots(1,2,figsize=(13.2,4.7),gridspec_kw={'width_ratios':[1.0,1.18]})
v16_axes(fig,[ax,ay])
_v18_cats=['0','1','2','3+']
_v18_vals=[int((_v18_f['mistakes']==0).sum()),int((_v18_f['mistakes']==1).sum()),int((_v18_f['mistakes']==2).sum()),int((_v18_f['mistakes']>=3).sum())]
ax.bar(_v18_cats,_v18_vals,color=[VAQUA,VBLUE,VCORAL,VGOLD],width=.64)
for i,n in enumerate(_v18_vals):ax.text(i,n+2,str(n),ha='center',color=VTXT,fontweight='bold',fontsize=11)
ax.set(ylabel='Number of formulas',xlabel='Wrong duels per formula',ylim=(0,max(_v18_vals)*1.19))
ax.set_title('Where Do Errors Cluster?',color=VTXT,fontweight='bold',pad=13)
_v18_accuracy=[_v18_micro*100,_v18_macro*100]
ay.hlines([1,0],xmin=85,xmax=100,color='#314962',linewidth=1.4,alpha=.75)
ay.scatter(_v18_accuracy,[1,0],color=[VAQUA,VBLUE],s=165,zorder=4,edgecolors=VAX,linewidth=1.2)
ay.errorbar([_v18_micro*100],[1],xerr=[[(_v18_micro-_v18_ci[0])*100],[(_v18_ci[1]-_v18_micro)*100]],fmt='none',ecolor=VGOLD,elinewidth=2.5,capsize=6)
for i,n in zip([1,0],_v18_accuracy):ay.text(n+.4,i,f'{n:.1f}%',color=VTXT,va='center',fontsize=12,fontweight='bold')
ay.set(yticks=[1,0],yticklabels=['Per duel','Per formula'],xlim=(85,101),ylim=(-.65,1.65),xlabel='Correct decisions, %')
ay.set_title('Same Errors, Different Weighting',color=VTXT,fontweight='bold',pad=13)
fig.suptitle('274 Duels, but Only 164 Molecular Formulas',color=VTXT,fontweight='bold',fontsize=16,x=.05,ha='left')
fig.tight_layout(rect=[0,0,1,.92]);plt.show();plt.close(fig)
v16_caption(f'<b>Finding.</b> All <b>{_v18_total_bad}</b> errors belong to only <b>{_v18_n_bad}</b> out of {len(_v18_f)} formulas. Accuracy is <b>{_v18_micro:.1%}</b> per duel and <b>{_v18_macro:.1%}</b> with equal weight per formula. A formula-cluster bootstrap gives a <b>{_v18_ci[0]:.1%}–{_v18_ci[1]:.1%}</b> interval for duel accuracy; this is a descriptive estimate for the selected diagnostic panel.')
