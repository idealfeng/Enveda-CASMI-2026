# Official scoring evidence

Original source: https://www.kaggle.com/code/metric/casmi-mean-reciprocal-rank

The anonymous Kaggle `kernels/pull` API returned version 14 on 2026-11-04. The unmodified response, metadata, notebook source and SHA-256 receipt are in `official_metric_20261104/`. This is a source archive, not a reimplementation. `metric.py` is our local helper and is tested against this archived source.

The source explicitly removes stereochemistry **before** tautomer canonicalization, then compares InChIKey14. It drops empty/whitespace semicolon fields before counting guesses. Nonempty invalid SMILES and duplicate identities occupy ranks; the first correct guess scores reciprocal rank. More than 25 remaining guesses is rejected. The safe optimization gate is heavy-atom composition, not full molecular formula, because charge/protonation variants can share the scorer identity.

Our evaluator adds stricter local artifact validation: it requires exactly the truth molecule IDs, validates the truth's stored identity against its SMILES, and fails on a wrong RDKit version. Official V14 warns on a version mismatch and can score missing IDs as zero; we refuse these conditions so an incomplete run cannot appear to be a completed experiment. We support a single normalized answer per query, while official V14 also contains support for comma-delimited accepted alternatives in solution rows. We do not install packages automatically or modify candidate order during scoring.

Formula-only results are oracle diagnostics. Candidate-recall decomposition requires an explicitly supplied pre-ranking audit; absence remains unknown. Bootstrap intervals resample paired molecules, not spectra.
