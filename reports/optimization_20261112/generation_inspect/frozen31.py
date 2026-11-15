'''## 3. Engine 2: two-ranker engine (BIO + AFIX)

This engine runs first in its own process, while GPU memory is still empty. It writes a top-40 list per molecule with tautomer-canonical InChIKey-14 keys.

- **Candidates** come from COCONUT, ChEBI/LIPID MAPS (BIO) and the training structures.
- **Evidence** comes from library matching (including adduct-shifted matches), analog propagation, prvsiyan's fingerprint models and MetFrag-lite fragment matching.
- **Ranking** blends two gradient-boosted rankers.
'''
