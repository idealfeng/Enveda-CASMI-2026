# CODE CELL 46 · Deep EDA
if len(counts):
    pval=0.2
    # Conditional on a selected validation spectrum: at least one other row of the same structure is in training.
    chance=1-pval**(counts.astype(np.float64)-1)
    heldout_weighted=float(np.average(chance,weights=counts))
    structure_mean=float(np.mean(chance))
    print(f'Expected fraction of validation spectra whose structure is already represented in training: {heldout_weighted:.2%}')
    print(f'Mean structure-weighted probability (equal weight per structure): {structure_mean:.2%}')
    bins=[(1,1),(2,2),(3,5),(6,10),(11,20),(21,50),(51,10**9)]
    rows=[]
    for lo,hi in bins:
        take=(counts>=lo)&(counts<=hi)
        if take.any():
            rows.append({'Group':f'{lo}–{hi if hi<10**9 else "∞"}',
                'Structures':int(take.sum()),'Spectra':int(counts[take].sum()),
                'Probability of a familiar structure':float(np.average(chance[take],weights=counts[take]))})
    by_count=pd.DataFrame(rows)
    fig=px.bar(by_count,x='Group',y='Probability of a familiar structure',
       hover_data=['Structures','Spectra'],text='Spectra')
    fig=style(fig,'How Random Splitting Changes the Evaluation Task',
        'Full training set · theoretical probability of a familiar validation structure',445)
    fig.update_layout(yaxis_tickformat='.0%',yaxis_range=[0,1.02],
        xaxis_title='Spectra per structure',yaxis_title='Fraction of validation with a structure in training')
    show_chart(fig)
    display(by_count.round(3))