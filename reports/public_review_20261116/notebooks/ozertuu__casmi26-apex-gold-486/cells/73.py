# CODE CELL 39 · Deep EDA
if len(example)>=2:
    upper=example.iloc[0];lower=example.iloc[1]
    mz1,iv1=safe_peaks(upper);mz2,iv2=safe_peaks(lower)
    x1,y1=sticks(mz1,iv1,+1);x2,y2=sticks(mz2,iv2,-1)
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=x1,y=y1,mode='lines',line=dict(color=TEAL,width=1.5),name='Spectrum A'))
    fig.add_trace(go.Scatter(x=x2,y=y2,mode='lines',line=dict(color=CORAL,width=1.5),name='Spectrum B'))
    fig.add_hline(y=0,line_color=INK,line_width=1.2)
    fig=style(fig,'Mirror Comparison of Two Spectra of One Structure','Negative intensity is used only for the mirror plot · measurement conditions are shown in the table',470)
    fig.update_layout(xaxis_title='m/z',yaxis_title='Normalized intensity (mirrored)',yaxis_range=[-1.15,1.15])
    show_chart(fig)
else:
    print('At least two spectra are needed for a mirror plot.')
try:
    from rdkit import Chem
    from rdkit.Chem import Draw
    smiles=example.iloc[0].get('normalized_smiles')
    mol=Chem.MolFromSmiles(smiles) if isinstance(smiles,str) else None
    if mol is not None:
        display(HTML('<b style="color:#173047">2D structure of the selected molecule</b>'))
        display(Draw.MolToImage(mol,size=(390,250)))
except ImportError:
    print('RDKit is unavailable: no molecular structure image.')