# CODE CELL 33 · Deep EDA
if lib_count:
    top=pd.DataFrame(lib_count.most_common(18),columns=['Library','Spectra'])
    fig=px.bar(top.sort_values('Spectra'),x='Spectra',y='Library',orientation='h',text='Spectra')
    fig=style(fig,'Where Did the Training Spectra Come From?','Full training set · one row per spectrum',540)
    fig.update_traces(texttemplate='%{text:,.0f}',textposition='outside',cliponaxis=False)
    show_chart(fig)
if {'ingest_lib','adduct'}.issubset(meta):
    tab=pd.crosstab(meta.ingest_lib.fillna('unknown').astype(str),meta.adduct.fillna('unknown').astype(str))
    tab=tab.loc[tab.sum(1).nlargest(9).index,tab.sum(0).nlargest(8).index]
    frac=tab.div(tab.sum(axis=1),axis=0)*100
    fig=px.imshow(frac,aspect='auto',text_auto='.0f',color_continuous_scale='Teal',labels={'x':'Adduct','y':'Library','color':'Share of spectra, %'})
    fig=style(fig,'Adducts Are Unevenly Distributed Across Libraries','Sample · within-library shares',510)
    show_chart(fig)