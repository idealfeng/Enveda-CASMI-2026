# CODE CELL 60 · Deep EDA
d=v16_T.copy();labels=['Same instrument type','Different instrument types']
fig,ax=plt.subplots(figsize=(11.5,5));v16_axes(fig,[ax])
vals=[d.loc[d.group.eq(label),'cos'].to_numpy(dtype=float) for label in labels]
parts=ax.violinplot(vals,showmedians=False,showextrema=False,showmeans=False,widths=.75)
for part,color in zip(parts['bodies'],[VAQUA,VCORAL]):part.set_facecolor(color);part.set_edgecolor(color);part.set_alpha(.63)
rng=np.random.default_rng(26)
for i,(z,col) in enumerate(zip(vals,[VAQUA,VCORAL]),1):
    ax.scatter(i+rng.uniform(-.16,.16,len(z)),z,s=13,c=col,alpha=.24,edgecolors='none')
    ax.scatter([i],[np.median(z)],s=105,marker='D',color=VGOLD,zorder=5,edgecolors=VAX)
    ax.text(i,np.median(z)-.11,f'median {np.median(z):.3f}',color=VTXT,fontsize=12,ha='center',fontweight='bold')
ax.set(xticks=[1,2],xticklabels=[f'{l}\n(n={len(v)})' for l,v in zip(labels,vals)],ylim=(-.02,1.03),ylabel='Spectral cosine · √I / ±0.02 Da')
fig.suptitle('Same structure does not imply identical library conditions',fontsize=16,color=VTXT,fontweight='bold',x=.05,ha='left')
fig.tight_layout(rect=[0,0,1,.92]);display(fig);plt.close(fig)
v16_caption('<b>Observed.</b> Among <b>168</b> cross-library pairs with the same recorded instrument type, median cosine is <b>0.995</b>; among <b>155</b> pairs with different instrument types, it is <b>0.708</b>. The compounds and libraries are not identical across groups, so this is evidence consistent with domain shift and possible protocol similarities, not an isolated estimate of instrument effects.')
