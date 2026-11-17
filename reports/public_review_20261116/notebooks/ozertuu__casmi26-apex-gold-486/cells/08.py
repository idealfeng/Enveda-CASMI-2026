# CODE CELL 03 · Deep EDA
METACOLS = [c for c in ['spectrum_id','molecule_id','inchikey14','normalized_smiles',
    'ingest_lib','instrument_type','ionization_mode','adduct','precursor_mz',
    'collision_energy_ev','precursor_error_ppm','num_peaks','molecular_formula'] if c in SCHEMA]
struct_count = Counter(); lib_count = Counter(); adduct_count = Counter(); instrument_count = Counter()
lib_structures = defaultdict(set); key_formulas = defaultdict(set); meta_samples=[]; n_meta=0
for rg in range(pf.num_row_groups):
    frame = pf.read_row_group(rg,columns=METACOLS).to_pandas()
    n_meta += len(frame)
    struct_count.update(frame['inchikey14'].dropna().astype(str).tolist())
    for col,dct in [('ingest_lib',lib_count),('adduct',adduct_count),('instrument_type',instrument_count)]:
        if col in frame: dct.update(frame[col].fillna('unknown').astype(str).tolist())
    if {'ingest_lib','inchikey14'}.issubset(frame):
        for lib,g in frame.groupby('ingest_lib',dropna=False):
            lib_structures[str(lib)].update(g['inchikey14'].dropna().astype(str).unique())
    if {'inchikey14','molecular_formula'}.issubset(frame):
        unique_pairs=frame[['inchikey14','molecular_formula']].dropna().drop_duplicates()
        for ik,formula in unique_pairs.itertuples(index=False,name=None):
            ik=str(ik).strip();formula=str(formula).strip()
            if ik and formula and ik.lower()!='nan' and formula.lower()!='nan':
                key_formulas[ik].add(formula)
    meta_samples.append(frame.sample(n=min(META_SAMPLE_PER_ROW_GROUP,len(frame)),random_state=SEED+rg))
    del frame
    if rg%5==4: print(f'Metadata: processed {rg+1}/{pf.num_row_groups} row groups')
meta = pd.concat(meta_samples,ignore_index=True)
assert n_meta==pf.metadata.num_rows
print('FULL TRAIN:',f'{n_meta:,}','spectra |',f'{len(struct_count):,}','distinct InChIKey14 structures')
print('DIAGNOSTIC SAMPLE:',f'{len(meta):,}','rows; sample across Parquet row groups')