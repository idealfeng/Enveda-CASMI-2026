# CODE CELL 61 · Deep EDA
d=v16_R.copy();base=d['rank'].eq(1);rare=d['idf'].eq(1)
ct=pd.crosstab(base.map({True:'Correct √I',False:'Incorrect √I'}),rare.map({True:'Correct IDF',False:'Incorrect IDF'}))
ct=ct.reindex(index=['Correct √I','Incorrect √I'],columns=['Correct IDF','Incorrect IDF'],fill_value=0)
fig,ax=plt.subplots(figsize=(8.8,4.7));v16_axes(fig,[ax])
arr=ct.to_numpy(dtype=int);ax.imshow(arr,cmap='YlGnBu',vmin=0,vmax=max(arr.max(),1))
for i in range(2):
 for j in range(2):
  ax.text(j,i,str(arr[i,j]),ha='center',va='center',color='#10182C' if arr[i,j]>arr.max()*.35 else VTXT,fontsize=18,fontweight='bold')
ax.set(xticks=[0,1],yticks=[0,1],xticklabels=ct.columns,yticklabels=ct.index,xlabel='After rare-peak weighting',ylabel='Standard √I cosine')
ax.grid(False);ax.set_title('One gain, one loss — no net improvement',color=VTXT,fontweight='bold',pad=14)
fig.tight_layout();display(fig);plt.close(fig)
v16_caption('<b>A negative result is still evidence.</b> IDF corrected <b>one</b> incorrect choice and turned <b>one</b> correct choice into an error. Top-1 therefore remains <b>256 of 274</b> on this panel. This does not invalidate rarity weighting generally; it does not justify claiming an improvement here.')
