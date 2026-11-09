## 4. What this run did

The table counts, layer by layer, how many answer lists changed against the layer before. In the commit run the
pipeline ranks only the first 12 visible molecules (the rest are placeholders), and the visible molecules are copies
of training spectra, so every leader has a library match of 1.0 and the fragment check's rank-1 rule cannot fire;
only its swaps can. The neural fusion can still move a leader (the V1 row). The last row is the merge: the 0.75 order with the fragment check's leader moves from the V2 order; with no leader move in the commit run it equals the 0.75 order. The hidden rerun that produced the
score runs every molecule and is not shown to anyone.