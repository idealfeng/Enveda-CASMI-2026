# CODE CELL 56 · Deep EDA
d=v16_E.copy()
d['delta']=d.far_novel-d.near_novel
fig,(ax,ay)=plt.subplots(1,2,figsize=(13.5,5.0),gridspec_kw={'width_ratios':[1.1,.9]})
v16_axes(fig,[ax,ay])
ax.plot([0,1],[0,1],color='#637C93',ls='--',lw=1,label='equality')
ax.scatter(d.near_novel,d.far_novel,c=VAQUA,s=27,alpha=.52,edgecolors='none')
ax.set(xlim=(-.03,1.03),ylim=(-.03,1.03),xlabel='Unmatched intensity fraction · near CE',ylabel='Unmatched intensity fraction · far CE')
ax.set_title('Same structures, more unmatched fragments',fontweight='bold',fontsize=12)
vals=[d.near_novel.values,d.far_novel.values]
parts=ay.violinplot(vals,showmeans=False,showmedians=False,showextrema=False)
for p,col in zip(parts['bodies'],[VBLUE,VCORAL]):p.set_facecolor(col);p.set_edgecolor(col);p.set_alpha(.55)
for i,(z,col) in enumerate(zip(vals,[VBLUE,VCORAL]),1):
    ay.scatter(i,np.median(z),c=VGOLD,s=95,zorder=5,marker='D',edgecolors=VBG)
    ay.text(i,np.median(z)+.06,f'{np.median(z):.1%}',ha='center',color=VTXT,fontsize=12,fontweight='bold')
ay.set(xticks=[1,2],xticklabels=['Near CE','Far CE'],ylim=(0,1),ylabel='Intensity fraction in unmatched peaks')
ay.set_title('Distribution across 221 structures',fontweight='bold',fontsize=12)
fig.suptitle('Collision energy changes spectral composition, not just cosine',color=VTXT,fontweight='bold',fontsize=17,x=.04,ha='left')
fig.tight_layout(rect=[0,0,1,.92]);display(fig);plt.close(fig)
v16_caption('<b>Observed.</b> Median unmatched-intensity fraction: <b>2.5%</b> for near energies and <b>43.0%</b> for far energies. The median within-structure difference is <b>+35.0 percentage points</b>, with a 95% bootstrap interval of <b>+28.0 to +40.6 points</b>. This characterizes the selected diagnostic set, not an increase in identification accuracy.')
