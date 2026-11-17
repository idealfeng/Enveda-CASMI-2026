# CODE CELL 22 · Deep EDA
_neg=v8_metrics[(~v8_metrics.same_structure)&v8_metrics.same_adduct&
     v8_metrics.same_instrument].copy()
_neg['high_sym']=_neg.cosine_sym>=.8
_v8_ag=_neg.groupby('dimer').high_sym.agg(['sum','count']).reindex([False,True],fill_value=0)
def v8_wilson(k,n,z=1.96):
    if n==0:return np.nan,np.nan
    p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den
    spread=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return mid-spread,mid+spread
_rate=[]
for is_dimer,label in [(False,'Other adducts'),(True,'Dimeric adducts')]:
    k=int(_v8_ag.loc[is_dimer,'sum']);n=int(_v8_ag.loc[is_dimer,'count'])
    lo,hi=v8_wilson(k,n)
    _rate.append({'Group':label,'High cosine':k,'Total pairs':n,
                  'Fraction':k/n if n else np.nan,'lower':lo,'upper':hi})
v8_adduct_rate=pd.DataFrame(_rate)
fig=go.Figure(go.Bar(x=v8_adduct_rate['Group'],y=v8_adduct_rate['Fraction']*100,
    marker_color=[BLUE,CORAL],
    text=[f'{int(x)}/{int(y)}' for x,y in zip(v8_adduct_rate['High cosine'],v8_adduct_rate['Total pairs'])],
    textposition='outside',error_y=dict(type='data',symmetric=False,
       array=(v8_adduct_rate['upper']-v8_adduct_rate['Fraction'])*100,
       arrayminus=(v8_adduct_rate['Fraction']-v8_adduct_rate['lower'])*100)))
fig=style(fig,'Dimeric Adducts More Often Produce Near-Perfect Look-Alikes',
    'Different structures · nearby masses · matched adduct and instrument type',475)
fig.update_layout(yaxis_title='Pairs with cosine ≥ 0.80, %',
                  yaxis_range=[0,100],xaxis_title='')
show_chart(fig)
display(v8_adduct_rate[['Group','High cosine','Total pairs','Fraction']].round(3))
