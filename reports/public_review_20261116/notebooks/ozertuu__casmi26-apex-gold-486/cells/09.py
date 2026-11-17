# CODE CELL 04 · Deep EDA
counts = np.asarray(list(struct_count.values()),dtype=np.int64)
q = np.quantile(counts,[.5,.9,.99]) if len(counts) else [np.nan]*3
summary=pd.DataFrame([
 ['Spectra · full training set',n_meta],
 ['InChIKey14 structures · full training set',len(struct_count)],
 ['Libraries · full training set',len(lib_count)],
 ['Median spectra per structure',round(float(q[0]),2)],
 ['P90 spectra per structure',round(float(q[1]),2)],
 ['P99 spectra per structure',round(float(q[2]),2)],
],columns=['Metric','Value'])
display(summary)
if len(counts):
    upper=max(2,np.quantile(counts,.995))
    fig=px.histogram(x=np.clip(counts,None,upper),nbins=65,color_discrete_sequence=[TEAL],labels={'x':'Spectra per structure (capped at P99.5)','y':'Structures'})
    fig=style(fig,'How Often Was Each Structure Measured?','Full training set · distribution capped at P99.5')
    fig.update_traces(marker_line_width=0)
    show_chart(fig)
