# CODE CELL 09 · Deep EDA
# Actual formula-group sizes: full training set, not a spectral sample.
_v9_all_k=np.asarray(formula_sizes,dtype=int)
_v9_molecule_k=np.concatenate([np.repeat(k,k) for k in _v9_all_k if k>0]) if len(_v9_all_k) else np.array([],int)
if len(_v9_molecule_k):
    edges=[1,2,3,5,10,25,50,100,np.inf]
    categories=['1','2','3–4','5–9','10–24','25–49','50–99','100+']
    hist=[]
    for lo,hi,label in zip(edges[:-1],edges[1:],categories):
        arr=(_v9_molecule_k==1) if label=='1' else ((_v9_molecule_k>=lo)&(_v9_molecule_k<hi))
        hist.append({'Number of candidates per formula':label,'Structures':int(arr.sum()),'Share of structures, %':float(arr.mean()*100)})
    view=pd.DataFrame(hist)
    # Expected MRR@25 under a uniformly random candidate ordering: a mathematical reference.
    def random_rank_mrr(k):return float(np.sum(1/np.arange(1,min(int(k),25)+1))/k)
    example=pd.DataFrame({'Structures sharing a formula':[1,2,5,10,25,50,100]})
    example['Random-ranking MRR@25']=[random_rank_mrr(k) for k in example.iloc[:,0]]
    fig=go.Figure(go.Bar(x=view['Number of candidates per formula'],y=view['Share of structures, %'],marker_color=TEAL))
    fig=style(fig,'One Formula Still Leaves Multiple Candidate Structures',
        'One vote per structure · exact formula groups across the full training set',460)
    fig.update_layout(yaxis_title='Share of structures, %',xaxis_title='Distinct structures sharing the formula')
    show_chart(fig)
    display(view.round(2));display(example.round(4))
    note('Finding · How Many Candidates Remain?',
         f'{100*(_v9_molecule_k>1).mean():.1f}% of structures with consistent formulas have at least one competitor. '
         f'For {int((_v9_molecule_k>=25).sum()):,} structures have 25 or more formula-matched candidates.')
