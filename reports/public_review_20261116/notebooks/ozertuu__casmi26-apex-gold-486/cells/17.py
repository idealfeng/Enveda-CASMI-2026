# CODE CELL 08 · Deep EDA
try:
    from rdkit import Chem
    from rdkit.Chem import Draw
    _formula_gallery=meta.dropna(subset=['molecular_formula','normalized_smiles','inchikey14']).copy()
    _formula_gallery=_formula_gallery.drop_duplicates(['molecular_formula','inchikey14'])
    _ranked=_formula_gallery.groupby('molecular_formula').inchikey14.nunique().sort_values(ascending=False)
    v8_gallery_ok=False
    for _formula in _ranked.head(45).index:
        _g=_formula_gallery[_formula_gallery.molecular_formula==_formula]
        _mols=[];_keys=[]
        for _r in _g.itertuples(index=False):
            _m=Chem.MolFromSmiles(_r.normalized_smiles) if isinstance(_r.normalized_smiles,str) else None
            if _m is not None:
                _mols.append(_m);_keys.append(_r.inchikey14)
            if len(_mols)==6:break
        if len(_mols)>=4:
            display(Draw.MolsToGridImage(_mols,molsPerRow=3,subImgSize=(280,210),
               legends=[f'Structure {i+1}' for i in range(len(_mols))]))
            print(f'Shared formula: {_formula} | distinct connectivities in training: {len(formula_to_keys.get(_formula,set())):,} | shown: {len(_mols)}')
            v8_gallery_ok=True
            break
    if not v8_gallery_ok:
        print('The metadata sample contains fewer than four suitable SMILES for any one formula.')
except ImportError:
    print('RDKit is required for the molecular gallery.')
