# CODE CELL 12 · Deep EDA
# Stream peak arrays through memory-bounded batches; no full 3 GB pandas load.
peak_cols=['ms2_mzs','ms2_normalized_intensities']
peak_records=[]
for rg,g in all_locs.groupby('row_group',sort=True):
    offsets=np.sort(g.row_offset.to_numpy(dtype='int64'))
    offset=0
    for batch in pfile.iter_batches(batch_size=2048,row_groups=[int(rg)],columns=peak_cols):
        a=np.searchsorted(offsets,offset,side='left')
        b=np.searchsorted(offsets,offset+batch.num_rows,side='left')
        if b>a:
            wanted=offsets[a:b]-offset
            taken=batch.take(pa.array(wanted,type=pa.int64())).to_pydict()
            for i,pos in enumerate(offsets[a:b]):
                mz=np.asarray(taken['ms2_mzs'][i],dtype=np.float64)
                it=np.asarray(taken['ms2_normalized_intensities'][i],dtype=np.float64)
                if len(mz)!=len(it):continue
                original_len=len(mz)
                valid=np.isfinite(mz)&np.isfinite(it)&(it>=0)
                mz,it=mz[valid],it[valid]
                if len(mz)>MAX_PEAKS_PER_SPECTRUM:
                    keep=np.argpartition(it,-MAX_PEAKS_PER_SPECTRUM)[-MAX_PEAKS_PER_SPECTRUM:]
                    mz,it=mz[keep],it[keep]
                sort=np.argsort(mz)
                peak_records.append({'row_group':int(rg),'row_offset':int(pos),
                   'ms2_mzs':mz[sort].tolist(),
                   'ms2_normalized_intensities':it[sort].astype('float32').tolist(),
                   'original_peaks':int(original_len),'retained_peaks':int(len(mz))})
        offset += batch.num_rows
    if (int(rg)+1)%10==0 or int(rg)+1==pfile.num_row_groups:
        print(f'Peak extraction: group {int(rg)+1}/{pfile.num_row_groups}; spectra={len(peak_records):,}')

peak_df=pd.DataFrame(peak_records)
if len(peak_df):
    selected_spectra=all_locs.merge(peak_df,on=['row_group','row_offset'],how='inner',validate='one_to_one')
else:
    selected_spectra=all_locs.head(0).copy()

v5_specs = selected_spectra
v5_pairs = pair_df
assert not v5_specs.empty and not v5_pairs.empty, "Cohort extraction returned no comparable spectra."
assert v5_specs.ms2_mzs.map(len).eq(v5_specs.ms2_normalized_intensities.map(len)).all()
assert v5_specs.ms2_mzs.map(len).eq(v5_specs.retained_peaks).all()
print(f"Spectra for comparison: {len(v5_specs):,} spectra / {v5_pairs.pair_type.value_counts().to_dict()}")
print(f"Long spectra truncated to {MAX_PEAKS_PER_SPECTRUM} most intense peaks: "
      f"{(v5_specs.original_peaks > v5_specs.retained_peaks).sum():,} rows")
