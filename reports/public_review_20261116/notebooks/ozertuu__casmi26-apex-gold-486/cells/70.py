# CODE CELL 36 · Deep EDA
SPEC_COLS=[c for c in ['spectrum_id','molecule_id','inchikey14','normalized_smiles','ingest_lib',
 'instrument_type','adduct','precursor_mz','collision_energy_ev','ms2_mzs',
 'ms2_normalized_intensities','molecular_formula'] if c in SCHEMA]
rg_ids=np.linspace(0,max(0,pf.num_row_groups-1),min(SPECTRAL_ROW_GROUPS,pf.num_row_groups),dtype=int)
rg_ids=sorted(set(map(int,rg_ids)))
parts=[]
for rg in rg_ids:
    frame=pf.read_row_group(rg,columns=SPEC_COLS).to_pandas()
    indexes=np.unique(np.r_[np.arange(min(SPECTRAL_HEAD_PER_GROUP,len(frame))),
        RNG.choice(len(frame),size=min(SPECTRAL_RANDOM_PER_GROUP,len(frame)),replace=False)])
    parts.append(frame.iloc[indexes].copy())
    del frame; gc.collect()
spec=pd.concat(parts,ignore_index=True)
spec['energies']=spec.collision_energy_ev.map(energy_list) if 'collision_energy_ev' in spec else [[] for _ in range(len(spec))]
spec['mean_ev']=spec.energies.map(lambda z:float(np.mean(z)) if z else np.nan)
print('Illustrative sample:',len(spec),'spectra | row groups:',rg_ids)