# CODE CELL 64 · Deep EDA
# Paired association between two measures of spectral change.
_v18_e=v16_E.copy()
_v18_e['cos_drop']=_v18_e['near_cos']-_v18_e['far_cos']
_v18_e['new_signal_gain']=_v18_e['far_novel']-_v18_e['near_novel']
_v18_ranked = _v18_e[['cos_drop','new_signal_gain']].rank(method='average')
_v18_rho = float(_v18_ranked.corr().iloc[0,1])
_v18_concord = (_v18_e['cos_drop']>0)&(_v18_e['new_signal_gain']>0)
_v18_neg=int((~_v18_concord).sum())
fig,ax=plt.subplots(figsize=(10.5,6.1));v16_axes(fig,[ax])
ax.scatter(_v18_e.loc[_v18_concord,'new_signal_gain']*100,_v18_e.loc[_v18_concord,'cos_drop'],s=43,c=VAQUA,alpha=.67,edgecolors='none',label='Both changes in the expected direction')
ax.scatter(_v18_e.loc[~_v18_concord,'new_signal_gain']*100,_v18_e.loc[~_v18_concord,'cos_drop'],s=48,c=VCORAL,alpha=.82,edgecolors='none',label='A discordant change')
ax.axhline(0,color=VGOLD,alpha=.65,lw=1.0,ls='--');ax.axvline(0,color=VGOLD,alpha=.65,lw=1.0,ls='--')
ax.set(xlabel='Extra unmatched-peak intensity, pp (far − near)',ylabel='Drop in cosine (near − far)')
ax.set_title('New Peaks Accompany a Loss of Similarity',fontsize=16,color=VTXT,fontweight='bold',pad=16)
ax.text(.04,.94,f'Spearman ρ = {_v18_rho:.3f}',color=VGOLD,fontsize=15,fontweight='bold',transform=ax.transAxes,va='top')
ax.legend(loc='lower right',facecolor=VAX,edgecolor='#36526B',labelcolor=VTXT,fontsize=9)
fig.tight_layout();plt.show();plt.close(fig)
v16_caption(f'<b>Finding.</b> Across <b>{len(_v18_e)}</b> structures, the rank correlation between the two changes is <b>ρ = {_v18_rho:.3f}</b>. Cosine declines as the energy gap increases in <b>{int((_v18_e.cos_drop>0).sum())}</b> structures, while the unmatched-intensity share rises in <b>{int((_v18_e.new_signal_gain>0).sum())}</b>. This is consistent with a shared spectral shift, not proof of causality.')
