# CODE CELL 07 · Deep EDA
# Molecular formula → number of distinct structures, counted across the full training set.
formula_to_keys=defaultdict(set)
ambiguous_formula_keys={k for k,fs in key_formulas.items() if len(fs)!=1}
for key,formulas in key_formulas.items():
    if len(formulas)==1:
        formula_to_keys[next(iter(formulas))].add(key)
formula_sizes=np.asarray([len(keys) for keys in formula_to_keys.values()],dtype=np.int64)
formula_structures=sum(len(v) for v in formula_to_keys.values())
shared_formulas={f:keys for f,keys in formula_to_keys.items() if len(keys)>1}
shared_structures=sum(len(v) for v in shared_formulas.values())
print('Structures with a consistent formula:',f'{formula_structures:,}')
print('Structures assigned multiple formulas across source rows:',f'{len(ambiguous_formula_keys):,}')
if len(formula_sizes):
    tbl=pd.DataFrame({'Structures per formula':formula_sizes})
    tbl['Number of structures']=tbl['Structures per formula'].clip(upper=20).astype(str)
    tbl.loc[tbl['Structures per formula']>=20,'Number of structures']='20+'
    freq=tbl['Number of structures'].value_counts()
    categories=sorted(freq.index,key=lambda s:20 if s=='20+' else int(s))
    fig=go.Figure(go.Bar(x=categories,y=freq.reindex(categories).values,marker_color=BLUE))
    fig=style(fig,'How Many Structures Can Share One Formula?',
        'Full training set · distinct InChIKey14 · 20+ category combined',475)
    fig.update_layout(xaxis_title='Distinct structures per formula',yaxis_title='Number of molecular formulas')
    show_chart(fig)
    display(pd.DataFrame({
        'Metric':['Formulas','Structures sharing a formula with another structure',
                      'Maximum structures for one formula','Structures excluded (inconsistent formula)'],
        'Result':[f'{len(formula_to_keys):,}',
                     f'{shared_structures:,} ({shared_structures/max(1,formula_structures):.1%})',
                     f'{formula_sizes.max():,}',f'{len(ambiguous_formula_keys):,}']
    }))
    display(pd.DataFrame([{'Formula':f,'Distinct structures':len(keys)}
        for f,keys in sorted(shared_formulas.items(),key=lambda kv:len(kv[1]),reverse=True)[:12]]))
    note('Another Layer of Ambiguity',
        f'{shared_structures/max(1,formula_structures):.1%} of structures with a consistent formula '
        'have at least one different structure with the same elemental formula in training.')