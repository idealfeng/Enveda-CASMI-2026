# CODE CELL 45 · Deep EDA
if len(counts):
    p_holdout=.2
    counts_clip=np.arange(1,min(60,int(np.max(counts)))+1)
    both=1-(1-p_holdout)**counts_clip-p_holdout**counts_clip
    fig=px.line(x=counts_clip,y=both,markers=True,labels={'x':'Spectra per structure (n)','y':'P(structure in both splits)'})
    fig=style(fig,'Structure-Overlap Risk Under a Random Split',f'Mathematical model: validation fraction = {p_holdout:.0%}',445)
    fig.update_yaxes(tickformat='.0%',range=[0,1.04])
    show_chart(fig)
    measured=np.mean(1-(1-p_holdout)**counts-p_holdout**counts)
    print(f'Mean overlap probability for a training structure: {measured:.3%}')
    print('Calculated under independent random assignment of rows.')
note('Practical Implication','Use an InChIKey14-grouped holdout to evaluate unseen structures; held-out-library transfer tests another important dimension.',CORAL)