# CODE CELL 63 · Deep EDA
# Paired comparisons within the same molecular structure.
_v18_t = v16_T.copy()
_v18_pair = (_v18_t.groupby(['key','group']).cos.median().unstack())
_v18_pair = _v18_pair.dropna(subset=['Same instrument type','Different instrument types']).copy()
_v18_pair['delta'] = _v18_pair['Same instrument type'] - _v18_pair['Different instrument types']
_v18_pair = _v18_pair.sort_values('delta')
_v18_yes = int((_v18_pair['delta']>0).sum())
_v18_med = float(_v18_pair['delta'].median())
fig,ax=plt.subplots(figsize=(11.4,6.2));v16_axes(fig,[ax])
for key,row in _v18_pair.iterrows():
    good=row['delta']>0
    color=VAQUA if good else VCORAL
    ax.plot([0,1],[row['Different instrument types'],row['Same instrument type']],color=color,alpha=.58,lw=1.7)
    ax.scatter([0,1],[row['Different instrument types'],row['Same instrument type']],s=36,color=color,zorder=4,edgecolor=VAX,linewidth=.5)
ax.set(xticks=[0,1],xticklabels=['Different instrument types','Same instrument type'],ylabel='Median cosine for the same structure',ylim=(-.06,1.07),xlim=(-.35,1.38))
ax.set_title('One Structure, Two Cross-Library Comparison Types',color=VTXT,fontweight='bold',fontsize=15,pad=18)
ax.text(1.04,.10,f'{_v18_yes} / {len(_v18_pair)}',color=VAQUA,fontsize=20,fontweight='bold')
ax.text(1.04,.04,'lines rise to the right',color=VMUT,fontsize=10)
fig.tight_layout();plt.show();plt.close(fig)
v16_caption(f'<b>Finding.</b> For <b>{_v18_yes} of {len(_v18_pair)}</b> structures, median cosine is higher when instrument types match. The median paired difference is <b>+{_v18_med:.3f}</b>. Some lines go the other way (coral), so this is not a clean causal instrument effect: libraries and acquisition protocols also differ.')
