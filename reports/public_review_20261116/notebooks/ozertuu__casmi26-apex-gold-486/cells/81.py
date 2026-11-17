# CODE CELL 43 · Deep EDA
try:
    from rdkit import Chem,DataStructs
    from rdkit.Chem import rdFingerprintGenerator
    _fp_gen=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048)
    _fp_cache={}
    def v8_fingerprint(row):
        key=str(row['inchikey14'])
        if key not in _fp_cache:
            smi=row['normalized_smiles']
            mol=Chem.MolFromSmiles(smi) if isinstance(smi,str) else None
            _fp_cache[key]=_fp_gen.GetFingerprint(mol) if mol is not None else None
        return _fp_cache[key]
    v8_molecular=[]
    for p in v8_metrics[(~v8_metrics.same_structure)&v8_metrics.same_adduct&
                        v8_metrics.same_instrument].itertuples(index=False):
        a=v5_records[p.a];b=v5_records[p.b]
        fa=v8_fingerprint(a);fb=v8_fingerprint(b)
        if fa is None or fb is None:continue
        tan=float(DataStructs.TanimotoSimilarity(fa,fb))
        v8_molecular.append({'Structural Tanimoto':tan,'MS/MS cosine':p.cosine_sym,
           'Adduct type':'Dimer' if p.dimer else 'Other',
           'Same formula':bool(p.same_formula),'InChIKey A':str(a['inchikey14']),
           'InChIKey B':str(b['inchikey14'])})
    v8_molecular=pd.DataFrame(v8_molecular)
    if len(v8_molecular):
        fig=px.scatter(v8_molecular,x='Structural Tanimoto',y='MS/MS cosine',
             color='Adduct type',color_discrete_map={'Dimer':CORAL,'Other':BLUE},
             symbol='Same formula',opacity=.78,
             hover_data=['InChIKey A','InChIKey B'])
        fig.add_hrect(y0=.8,y1=1.01,line_width=0,fillcolor='#F5D3B9',opacity=.22)
        fig=style(fig,'Spectra Can Match Even When Structures Differ',
            f'{len(v8_molecular)} structural pairs · Morgan Tanimoto radius=2 · MS/MS cosine',510)
        fig.update_layout(xaxis_range=[-.02,1.02],yaxis_range=[-.02,1.02])
        show_chart(fig)
        hard=v8_molecular[(v8_molecular['Structural Tanimoto']<.30)&
                         (v8_molecular['MS/MS cosine']>=.8)]
        print(f'Different structures: cosine ≥ 0.8 with Tanimoto < 0.30 — {len(hard)} out of {len(v8_molecular)} comparable pairs.')
        display(hard.sort_values('MS/MS cosine',ascending=False).head(10).round(3))
except ImportError:
    print('RDKit is required for Morgan fingerprints.')
