# CODE CELL 42 · Deep EDA
try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    HAS_RDKIT=True
except ImportError:
    HAS_RDKIT=False

chem = pd.DataFrame()
if HAS_RDKIT and {'inchikey14','normalized_smiles'}.issubset(meta.columns):
    distinct=meta.dropna(subset=['inchikey14','normalized_smiles']).drop_duplicates('inchikey14').copy()
    distinct=distinct.sample(n=min(MAX_MOLS_FOR_RDKIT,len(distinct)),random_state=SEED)
    rec=[]
    for row in distinct.itertuples(index=False):
        smi=getattr(row,'normalized_smiles',None)
        mol=Chem.MolFromSmiles(smi) if isinstance(smi,str) else None
        if mol is None: continue
        rec.append({'inchikey14':getattr(row,'inchikey14'),'library':getattr(row,'ingest_lib','unknown'),
                    'smiles':smi,'exact_mass':Descriptors.ExactMolWt(mol),
                    'heavy_atoms':mol.GetNumHeavyAtoms(), 'rings':rdMolDescriptors.CalcNumRings(mol),
                    'hbd':rdMolDescriptors.CalcNumHBD(mol),'fsp3':rdMolDescriptors.CalcFractionCSP3(mol),
                    'aromatic_atoms':sum(a.GetIsAromatic() for a in mol.GetAtoms())})
    chem=pd.DataFrame(rec)
    print('RDKit structures profiled:',len(chem))
else:
    print('RDKit or structure columns unavailable: molecule descriptors skipped')
if len(chem):
    fig=px.scatter(chem,x='exact_mass',y='fsp3',color='library',hover_data=['rings','heavy_atoms','hbd'],opacity=.5,
       category_orders={'library':chem.library.value_counts().index.tolist()})
    fig=style(fig,'Chemical Space of Training Structures','Sample · one point per structure; Fsp3 = fraction of sp³ carbons',510)
    fig.update_traces(marker=dict(size=7))
    show_chart(fig)
    display(chem.groupby('library').agg(n=('inchikey14','size'),mass_median=('exact_mass','median'),fsp3_median=('fsp3','median'),rings_median=('rings','median')).round(2).sort_values('n',ascending=False).head(12))
note('What the Plot Reveals','Even molecules with the same mass can have very different connectivity and fragmentation pathways.')