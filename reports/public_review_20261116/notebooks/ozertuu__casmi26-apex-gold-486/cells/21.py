# CODE CELL 10 · Deep EDA
# Build a reproducible, enriched cohort. Full-train counts are already available above.
# Selection deliberately resembles the V4 research pack: results remain reproducible in forks.
SEED_EXPORT = 20261109
RNG_EXPORT = np.random.default_rng(SEED_EXPORT)
METADATA_SAMPLE_ROWS = 100_000
TARGET_STRUCTURES = 650
MAX_SPECTRA_PER_STRUCTURE = 8
MAX_PEAKS_PER_SPECTRUM = 350
MAX_MASS_GAP_DA = 0.20
pfile, cols = pf, set(SCHEMA)

keys_multi = [k for k,n in struct_count.items() if n >= 2 and k not in ('nan','None','')]
keys_multi.sort(key=lambda k:(-struct_count[k], k))
target = list(keys_multi[:min(140,len(keys_multi))])

def add_random(pool, how_many):
    pool = [k for k in pool if k not in target]
    if not pool: return
    idx = RNG_EXPORT.choice(len(pool), size=min(how_many,len(pool)), replace=False)
    target.extend(pool[int(i)] for i in idx)

high = [k for k in keys_multi if struct_count[k] >= 8]
medium = [k for k in keys_multi if 3 <= struct_count[k] < 8]
low = [k for k in keys_multi if struct_count[k] == 2]
add_random(high,210)
add_random(medium,210)
add_random(low,90)

prior_libraries = globals().get('lib_structures')
if isinstance(prior_libraries, dict):
    membership = Counter(k for members in prior_libraries.values() for k in members)
    shared = [k for k,v in membership.items() if v >= 2 and struct_count.get(k,0) >= 2]
    add_random(shared,120)
add_random(keys_multi, max(0,TARGET_STRUCTURES-len(target)))
target = set(target[:TARGET_STRUCTURES])
print('Selected structures:',len(target))


meta_columns = [c for c in ['spectrum_id','molecule_id','inchikey14','normalized_smiles',
    'ingest_lib','instrument_type','ionization_mode','adduct','precursor_mz','collision_energy_ev',
    'precursor_error_ppm','num_peaks','molecular_formula'] if c in cols]
prob = min(1.0,METADATA_SAMPLE_ROWS / max(1,pfile.metadata.num_rows))
background_parts=[]; focus_parts=[]

for rg in range(pfile.num_row_groups):
    data = pfile.read_row_group(rg,columns=meta_columns).to_pandas()
    n = len(data)
    sample_n = min(n,round(n*prob))
    sample_loc = RNG_EXPORT.choice(n,size=sample_n,replace=False) if sample_n else np.array([],dtype=int)
    bg = data.iloc[sample_loc].copy()
    bg['row_group'] = rg
    bg['row_offset'] = sample_loc.astype('int32')
    background_parts.append(bg)
    focus = data[data['inchikey14'].isin(target)]
    if not focus.empty:
        # At most five candidates per structure per row group; avoids excessive RAM.
        sub=[]
        for _,g in focus.groupby('inchikey14',sort=False):
            if len(g)>5:
                chosen = RNG_EXPORT.choice(len(g),size=5,replace=False)
                g = g.iloc[chosen]
            sub.append(g)
        picked=pd.concat(sub)
        picked=picked.copy()
        picked['row_group']=rg
        picked['row_offset']=picked.index.astype('int32')
        focus_parts.append(picked)
    del data, bg, focus
    if (rg+1)%10 == 0 or rg+1 == pfile.num_row_groups:
        print(f'Metadata scan: {rg+1}/{pfile.num_row_groups} row groups')
    gc.collect()

background = pd.concat(background_parts,ignore_index=True)
focus_all = pd.concat(focus_parts,ignore_index=True) if focus_parts else background.head(0).copy()
del background_parts,focus_parts


print(f"Research cohort: {len(background):,} random metadata rows; "
      f"{len(focus_all):,} provisional records from {len(target)} targeted structures.")
