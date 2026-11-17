# CODE CELL 57 · Deep EDA
d=v16_R.copy()
variants=[('√ intensity','rank',VAQUA),('Raw intensity','linear',VCORAL),('Top 20 peaks','top20',VBLUE),('Peak rarity (IDF)','idf',VGOLD)]
acc=[float((d[col]==1).mean()) for _,col,_ in variants]
fig,ax=plt.subplots(figsize=(11.5,4.9));v16_axes(fig,[ax])
bars=ax.bar(np.arange(len(acc)),acc,color=[z[2] for z in variants],width=.58,alpha=.92)
ax.axhline(.5,color='#9FB8C9',linestyle='--',alpha=.6,label='random two-way choice')
for b,v in zip(bars,acc):ax.text(b.get_x()+b.get_width()/2,v+.02,f'{v:.1%}',ha='center',color=VTXT,fontweight='bold',fontsize=13)
ax.set(ylim=(0,1.07),xticks=np.arange(len(acc)),xticklabels=[x[0] for x in variants],ylabel='Top-1 in diagnostic duels')
ax.legend(facecolor=VAX,edgecolor='#42617E',labelcolor=VTXT,loc='lower right',fontsize=10)
fig.suptitle('Choose one of two: 274 isomer duels',x=.055,ha='left',fontsize=17,color=VTXT,fontweight='bold')
fig.tight_layout(rect=[0,0,1,.92]);display(fig);plt.close(fig)
v16_caption('<b>Result.</b> With square-root intensity weighting, the correct structure wins <b>256 of 274</b> duels (93.4%). There are <b>18 errors</b>, examined below. This is a choice between <b>two</b> known isomers, not the official MRR@25 benchmark.')
