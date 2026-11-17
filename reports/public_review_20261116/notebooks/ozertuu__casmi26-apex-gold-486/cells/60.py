# CODE CELL 30 · Deep EDA
# Favor a mass-matched, same-formula, same-library example with known similar CE.
options=v5_high[(v5_high.same_formula)&(v5_high.same_lib)&
                (v5_high.delta_e<=10)&(v5_high.precursor_gap<=.01)&
                v5_high.dimer&(v5_high.matched_peaks>=5)].copy()
options['drop']=options.cosine-options.masked_cosine
if options.empty:
    options=v5_high.copy()
    options['drop']=options.cosine-options.masked_cosine
if len(options):
    chosen=options.sort_values(['drop','cosine'],ascending=False).iloc[0]
    aa=v5_records[chosen.a];bb=v5_records[chosen.b]
    fig=go.Figure()
    def v5_sticks(row,sign=1):
        xx=[];yy=[]
        for m,y in zip(row.ms2_mzs,row.ms2_normalized_intensities):
            xx.extend([m,m,None]);yy.extend([0,sign*y,None])
        return xx,yy
    x,y=v5_sticks(aa,+1)
    fig.add_trace(go.Scatter(x=x,y=y,mode='lines',line=dict(color=TEAL,width=1.4),name='Molecule A'))
    x,y=v5_sticks(bb,-1)
    fig.add_trace(go.Scatter(x=x,y=y,mode='lines',line=dict(color=CORAL,width=1.4),name='Molecule B'))
    mono=_V5_ADDUCT_MASSES.get(str(aa.adduct))
    if mono is not None:
        mono=(float(aa.precursor_mz)+mono)/2
        fig.add_vrect(x0=mono-.07,x1=mono+4*1.003355+.07,
                      fillcolor='gold',opacity=.14,line_width=0)
    fig.add_hline(y=0,line_color=INK,line_width=1)
    fig=style(fig,'Two Structures, One Dominant Ion Pattern',
       f'Cosine = {chosen.cosine:.3f} · after masking = {chosen.masked_cosine:.3f} · adduct {aa.adduct}',490)
    fig.update_layout(xaxis_title='Fragment m/z',yaxis_title='Normalized intensity (mirrored)',
                      yaxis_range=[-1.12,1.12])
    show_chart(fig)
    display(pd.DataFrame({'Property':['InChIKey14','Molecular formula','Adduct','Instrument',
         'Library','Energy (mean, eV)','Precursor m/z','Number of peaks'],
         'Molecule A':[aa.inchikey14,aa.molecular_formula,aa.adduct,aa.instrument_type,
                       aa.ingest_lib,round(v5_energy(aa),2),round(aa.precursor_mz,4),aa.retained_peaks],
         'Molecule B':[bb.inchikey14,bb.molecular_formula,bb.adduct,bb.instrument_type,
                       bb.ingest_lib,round(v5_energy(bb),2),round(bb.precursor_mz,4),bb.retained_peaks]}))
    try:
        from rdkit import Chem,DataStructs
        from rdkit.Chem import Draw, AllChem
        ma=Chem.MolFromSmiles(aa.normalized_smiles)
        mb=Chem.MolFromSmiles(bb.normalized_smiles)
        if ma is not None and mb is not None:
            fpa=AllChem.GetMorganFingerprintAsBitVect(ma,2,nBits=2048)
            fpb=AllChem.GetMorganFingerprintAsBitVect(mb,2,nBits=2048)
            tan=DataStructs.TanimotoSimilarity(fpa,fpb)
            display(Draw.MolsToGridImage([ma,mb],molsPerRow=2,
                subImgSize=(330,240),legends=['Molecule A','Molecule B']))
            note('Structure Versus Spectrum',
                 f'Morgan-fingerprint Tanimoto (radius 2): {tan:.3f}. The structures differ, '
                 f'but the original cosine is {chosen.cosine:.3f}. '
                 'Shared adduct-derived ions may explain the match.')
    except ImportError:
        print('RDKit is unavailable: molecular images were not generated.')
