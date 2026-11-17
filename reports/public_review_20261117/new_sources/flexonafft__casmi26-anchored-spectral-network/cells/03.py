# Training molecules: structures of identity fold 0, which FPNet fold 0 never saw. Molecules with a timsTOF spectrum or
# an Enveda library (the hidden test is Enveda's timsTOF data) are taken first; the rest are a random fill.
import numpy as np
import pandas as pd
import pyarrow.dataset as pds
import pyarrow.parquet as pq

SEED, N_TESTLIKE, N_TOTAL = 0, 3000, 5000
names = set(pq.ParquetFile(COMP / 'train.parquet').schema_arrow.names)
st = pd.read_parquet(FOLDS, columns=['inchikey14', 'fold_identity']).drop_duplicates('inchikey14')
hold = set(st.inchikey14[st.fold_identity == 0])
cols = [c for c in ('inchikey14', 'normalized_smiles', 'instrument_type', 'ingest_lib') if c in names]
tr = pq.read_table(COMP / 'train.parquet', columns=cols).to_pandas()
tr = tr[tr.inchikey14.isin(hold)].reset_index(drop=True)
for c in ('instrument_type', 'ingest_lib'):
    if c in tr:
        print(c, tr[c].astype(str).value_counts().head(12).to_dict())
tr['tims'] = tr.instrument_type.astype(str).str.contains('tims', case=False) if 'instrument_type' in tr else False
tr['enveda'] = tr.ingest_lib.astype(str).str.contains('enveda', case=False) if 'ingest_lib' in tr else False
g = tr.groupby('inchikey14', sort=True).agg(smiles=('normalized_smiles', 'first'), tims=('tims', 'max'), enveda=('enveda', 'max'))
g['testlike'] = g.tims | g.enveda
rng = np.random.default_rng(SEED)
a_ = g.index[g.testlike].values
b_ = g.index[~g.testlike].values
pick = list(rng.choice(a_, min(N_TESTLIKE, len(a_)), replace=False))
pick += list(rng.choice(b_, min(N_TOTAL - len(pick), len(b_)), replace=False))
KEYS = sorted(set(pick))
del tr
print(f'fold-0 structures {len(g):,} (test-like {int(g.testlike.sum()):,}); picked {len(KEYS):,}')

spec_cols = [c for c in ('inchikey14', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities', 'adduct', 'ionization_mode',
                         'collision_energy_ev', 'instrument_type') if c in names]
sp = pds.dataset(str(COMP / 'train.parquet')).to_table(columns=spec_cols, filter=pds.field('inchikey14').isin(KEYS)).to_pandas()
SPECTRA = {}
for r in sp.to_dict('records'):
    SPECTRA.setdefault(r['inchikey14'], []).append(r)
for k, rs in SPECTRA.items():   # timsTOF spectra first, then the file order; at most MAX_SPECTRA as in the overlay
    rs.sort(key=lambda r: 0 if 'tims' in str(r.get('instrument_type', '')).lower() else 1)
    SPECTRA[k] = rs[:IR.MAX_SPECTRA]
del sp
print(f'spectra for {len(SPECTRA):,} molecules, {time.time() - T0:.0f} s')