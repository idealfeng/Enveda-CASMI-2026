## v8 · timsTOF mass-accuracy prior (table for ranks 2–25)

Every candidate of every final list gets its mass error against the molecule's neutral mass (median over its spectra,
from `test.parquet`'s precursor m/z and adduct, with the same constants the timsTOF band was measured with). Beyond `MASS_FREE` ppm of `MASS_CENTER` the final layer's
ranks 2–25 score loses up to `MASS_W` (full at `MASS_FULL` ppm). Isomers share a mass, so only candidates of other
formulas move. The rank-1 rule runs after the final layer (next section).