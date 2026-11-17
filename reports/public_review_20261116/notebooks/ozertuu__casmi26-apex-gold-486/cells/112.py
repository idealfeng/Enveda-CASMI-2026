# CODE CELL 58 · Deep EDA
d=v16_R.copy()
base=d['rank']==1
fix=int(((d.linear!=1)&base).sum());breaks=int(((d.linear==1)&(~base)).sum())
fixidf=int(((d['idf']==1)&(~base)).sum());breakidf=int(((d['idf']!=1)&base).sum())
fix20=int(((d.top20==1)&(~base)).sum());break20=int(((d.top20!=1)&base).sum())
fig,(ax,ay)=plt.subplots(1,2,figsize=(12.9,4.8));v16_axes(fig,[ax,ay])
labels=['√I corrected\na linear-I error','Linear I corrected\na √I error']
vals=[fix,breaks];bb=ax.bar([0,1],vals,color=[VAQUA,VCORAL],width=.56)
for bar,n in zip(bb,vals):ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+.4,str(n),color=VTXT,fontsize=14,fontweight='bold',ha='center')
ax.set(xticks=[0,1],xticklabels=labels,ylim=(0,max(vals)+3),ylabel='Number of duels')
ax.set_title('Which queries flipped the decision?',fontweight='bold')
rows=['Linear I','Top 20','IDF'];f=[fix,fix20,fixidf];b=[breaks,break20,breakidf]
y=np.arange(3);ax2=ay.barh(y-.18,f,.32,color=VAQUA,label='win for √I')
ay.barh(y+.18,b,.32,color=VCORAL,label='win for alternative')
ay.set(yticks=y,yticklabels=rows,xlabel='Number of decisions flipped')
ay.set_title('How many duels changed winner?',fontweight='bold')
ay.legend(facecolor=VAX,edgecolor='#42617E',labelcolor=VTXT,fontsize=9)
fig.suptitle('Ablation: peak weights matter as much as m/z matching',x=.05,ha='left',fontsize=16,color=VTXT,fontweight='bold')
fig.tight_layout(rect=[0,0,1,.91]);display(fig);plt.close(fig)
v16_caption('<b>Paired check.</b> Switching from raw intensity to √I corrected <b>12</b> choices and broke <b>1</b> on the same panel. Additional IDF weighting produced no net gain: <b>one error corrected and one introduced</b>. A rare peak is not necessarily a structurally informative peak.')
