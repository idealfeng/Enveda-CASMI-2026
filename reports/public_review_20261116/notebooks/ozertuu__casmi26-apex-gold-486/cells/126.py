# CODE CELL 65 · Deep EDA
# Collect summary numbers from the experiments already run.
last=[]
last.append(('Training spectra',f'{n_meta:,}','full training set'))
last.append(('Distinct structures',f'{len(struct_count):,}','full training set'))
if len(counts):
    last.append(('Structures with repeated spectra',f'{(counts>1).mean():.1%}','full training set'))
if 'formula_structures' in globals():
    last.append(('Structures sharing a formula with another structure',
        f'{shared_structures/max(1,formula_structures):.1%}','full training set, consistent formula'))
if 'v5_paired' in globals():
    last.append(('Structures with close/distant-energy controls',len(v5_paired),'selected pairs'))
if 'v5_high' in globals():
    last.append(('Different structures with cosine ≥ 0.8',len(v5_high),'selected pairs'))
if 'v7_ablation' in globals():
    last.append(('Masking-control comparisons',len(v7_ablation),'selected pairs'))
display(pd.DataFrame(last,columns=['Measurement','Result','Basis']))