# CODE CELL 13 · Deep EDA
# A single matching rule drives every comparison and the later isotope-envelope ablation.
from collections import Counter

_V5_ADDUCT_MASSES = {
    '[2M+H]+': 1.007276466621, '[2M+Na]+': 22.989218,
    '[2M+K]+': 38.963158, '[2M-H]-': -1.007276466621,
    '[2M+NH4]+': 18.033823,
}

def v5_energy(row):
    x=row['collision_energy_ev']
    return float(np.mean(x)) if x is not None and len(x) else np.nan

def v5_filter_ions(row, mz, it, remove_ion_envelopes=False):
    if not remove_ion_envelopes:
        return mz, it
    precursor=float(row['precursor_mz'])
    centers=[precursor]
    adduct=str(row['adduct'])
    if adduct in _V5_ADDUCT_MASSES:
        # For [2M+A], the expected [M+A] monomer ion is (precursor + mass(A)) / 2.
        centers.append((precursor + _V5_ADDUCT_MASSES[adduct])/2)
    keep=np.ones(len(mz),dtype=bool)
    for base in centers:
        for isotope in range(5):
            keep &= (np.abs(mz-(base+isotope*1.003355)) > .06)
    return mz[keep], it[keep]

def v5_cosine(a,b,tol=.02,remove_ion_envelopes=False):
    am=np.asarray(a['ms2_mzs'],dtype=float); ai=np.asarray(a['ms2_normalized_intensities'],dtype=float)
    bm=np.asarray(b['ms2_mzs'],dtype=float); bi=np.asarray(b['ms2_normalized_intensities'],dtype=float)
    am,ai=v5_filter_ions(a,am,ai,remove_ion_envelopes)
    bm,bi=v5_filter_ions(b,bm,bi,remove_ion_envelopes)
    if not len(ai) or not len(bi):
        return np.nan, 0
    used=set(); dot=0.; matched=0
    for i in np.argsort(ai)[::-1]:
        left=np.searchsorted(bm,am[i]-tol,'left')
        right=np.searchsorted(bm,am[i]+tol,'right')
        remaining=[j for j in range(left,right) if j not in used]
        if remaining:
            j=max(remaining,key=lambda k:bi[k]); used.add(j)
            dot+=ai[i]*bi[j];matched+=1
    return float(dot/(np.linalg.norm(ai)*np.linalg.norm(bi)+1e-12)),matched

v5_records = {(int(row.row_group),int(row.row_offset)):row
              for _,row in v5_specs.iterrows()}
v5_results=[]
for pair in v5_pairs.itertuples(index=False):
    a=v5_records.get((int(pair.a_group),int(pair.a_offset)))
    b=v5_records.get((int(pair.b_group),int(pair.b_offset)))
    if a is None or b is None:
        continue
    score,matches=v5_cosine(a,b)
    ea=v5_energy(a);eb=v5_energy(b)
    v5_results.append({
        'pair_type':pair.pair_type,
        'a':(int(pair.a_group),int(pair.a_offset)),
        'b':(int(pair.b_group),int(pair.b_offset)),
        'key_a':a.inchikey14,'key_b':b.inchikey14,
        'same_structure':a.inchikey14==b.inchikey14,
        'same_lib':a.ingest_lib==b.ingest_lib,
        'same_instrument':a.instrument_type==b.instrument_type,
        'same_adduct':a.adduct==b.adduct,
        'same_formula':a.molecular_formula==b.molecular_formula,
        'adduct':a.adduct,'lib':a.ingest_lib,
        'energy_a':ea,'energy_b':eb,
        'delta_e':abs(ea-eb) if np.isfinite(ea) and np.isfinite(eb) else np.nan,
        'precursor_gap':float(pair.precursor_gap_da),
        'peaks_a':a.retained_peaks,'peaks_b':b.retained_peaks,
        'cosine':score,'matched_peaks':matches,
        'dimer':str(a.adduct).startswith('[2M'),
    })
v5_metrics=pd.DataFrame(v5_results)
v5_metrics=v5_metrics[(v5_metrics.peaks_a>=10)&(v5_metrics.peaks_b>=10)].copy()
print('Comparable pairs (≥10 peaks per spectrum):',len(v5_metrics))
print(v5_metrics.pair_type.value_counts().to_string())
