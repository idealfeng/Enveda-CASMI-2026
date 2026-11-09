# Final NP membership bonus ablation

Baseline: the original MASS-only recipe reproduced by this account at Public 0.481. The prepared branch changes `NP_W` from 0.12 to 0.0 in the final `pxm_merge` ranks 2–25 scoring term. The public/v2 models, candidate generation, physical leader rule, final mass leader correction, POP/SPEC terms, library gate and all original outsider/LOTUS empty-slot filling are unchanged.

This is not removal of every natural-product signal: upstream trained models, structure catalogs and LOTUS candidates remain. Any measured effect is conditional on this complete old MASS recipe.

Only original cells 4 and 20 change. Cell 20 records actual NP score calls and contributions, while preserving score values exactly at a fixed weight. The observer is appended separately and checks the dynamic hidden sample count. In hidden mode it rejects skipped/restored merge paths, zero actual scoring calls or nonzero NP contribution. In fast commit mode it explicitly reports no model execution.

Bounded actual-function fixtures passed 16 checks, including equality before/after instrumentation at both weights, an expected tail-order change, unchanged leaders/candidate sets, the actual fast observer, a two-query hidden observer, and rejection of nonzero NP contribution, no scoring and silent fallback. These are implementation checks, not model/score evidence. No validation labels or locked holdout were read. No model inference, training, cloud run or competition submission was performed by this preparation script.

The manifest-driven engine's plan-only `local_preflight` passed. The root agent can merge `branch_spec.json` into the fixed daily manifest and independently review the stage before launch.

- Builder: `scripts/build_mass_np_ablation_20261108.py`
- Fixture runner: `scripts/review_mass_np_ablation_20261108.py`
- Fixture evidence: `reports/mass_np_ablation_fixture_20261108/verification.json`
- Batch preflight: `reports/mass_np_ablation_fixture_20261108/batch_engine_preflight.json`
- Notebook SHA256: `ad43e44f60b933b3ec5fa85cb349346da198e96c94c4113b0023594bee076bc7`
