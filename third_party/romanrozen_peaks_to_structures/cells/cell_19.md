## v4 · Taxonomic consistency on ranks 2–25

Natural products of one extract share their producing organisms, and the hidden test comes from biological extracts.
The molecules whose leader is a library hit (best library match ≥ `TAX_ANCHOR_LIB`, the same 0.87 gate as the final
layer's library bonus) are the anchors. The genera that LOTUS reports for their leaders
(`lotus_structure_genus.parquet` of Dmitrii Gluzdov's knowledge table, already attached to this notebook) form the test
set's genus profile: each anchor spreads one unit over its genera, and anchors found in more than `TAX_SPECIFIC_MAX`
genera carry no taxonomic information and are left out. A candidate on ranks 2–25 gets
`TAX_W · (1 − exp(−S / TAX_SCALE))`, where S is the largest profile mass among its own genera with the molecule's own
anchor left out. This is the taxonomically informed annotation idea of Rutz et al. (2019) with the organism inferred
from the test set itself, which the host allows (unsupervised processing across test spectra at inference time).

The bonus is one more term of the final layer's ranks 2–25 score, next to the documentation prior, so rank 1 never
moves. It switches itself off unless at least `TAX_MIN_SPECIFIC` anchors are specific and the share of them that
shares a genus with another anchor is above the 95th percentile of random anchor sets of the same size (drawn from the
knowledge table's structures with training spectra, where library-matched anchors come from) and above the floor
`TAX_MIN_COOCCUR`: the test set must be more clustered by organism than chance. A missing table, a missing column or
any error also switch it off, and the answer is then the public 0.480 answer exactly. The commit run's 12 visible molecules are synthetic library
compounds, so the gate is expected to stay closed there; the scoring rerun decides on the hidden test.