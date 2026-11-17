# Exact .488 champion: production stages and read-only observation points

This source audit implements an independent observer. It did not run models, read holdout labels, or repeat produre1/2 experiments. The root agent separately owns production replay and evaluation.

Champion notebook: `submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb`. Formal submission **58156482**, Public **.488**.
Notebook SHA256: `2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7`.
Embedded frozen notebook SHA256: `d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88`.

The exact champion includes the original nested Engine/PC/E2 pipeline, dual-neural consensus, physical/MASS/prior/dedup/backfill processing, the guarded trained head, and the FINAL AB measured-library overlay. Older Flex runs, nested final25 exports, E004 postflight, and expanded-generation variants cannot replace this control.

## Observer integration

`scripts/champion_stage_observer_20261115.py` exposes `before_cell`, `after_cell`, `after_outer_cell`, `finish`, and optional `install_engine2`. The inner runner invokes the first two immediately around ORIGINAL cell execution. Installation happens after original inner cell37, after the cell27 determinism patch and original V1FE recording hooks. Original parameters, return objects and exception semantics are retained; the observer writes no cfg/model/threshold changes. The original generator budget is gen_n_analog=6 and gen_max_total=150.

Call `finish(scope, root, "inner")` after the original final export. Call `after_outer_cell` after each original outer cell and `finish(scope, root, "outer")` at the end. The observer writes separate evidence under `root/champion_stage_observer/{inner,outer,engine2}/`: actual-call JSONL traces, important before/after cell lists and score dictionaries, plus copies of CSV and original audits. It never reads truth or computes evaluation metrics.

E2 runs in its own child process. Without `install_engine2(E, root)` before original E.main, only ENG final40 is observable and E2 candidate recall cannot be separated from ranking. The current runner installs this hook immediately after importing E: its install-time configuration snapshot therefore precedes the original assignments. The generated runner source and actual E.main call define the active settings: RANK.W_A=(.35,.55), RANK.SEEDS=(0,1), CFG.N_ANALOG=200, w_pv=.88. This snapshot timing does not change algorithm behavior. The root agent fixed the two-level injection to pre-bake root as a literal.

PubChem remains observable only at the real child return. Internal PubChem catalog/search/filter failures are not inferred from missing returned proposals.

## Stage map

Cell numbers are zero-based. A colon suffix gives line numbers INSIDE that cell, rather than physical JSON file lines. Python file line numbers refer to the byte-pinned source.

| Stage | Exact source point | Evidence to retain |
|---|---|---|
| 00_recipe_materialisation | `outer cell12:64-73; cell14:1; MODULES runner.py:13-20` | Notebook/module/model/asset hashes; exact input/query order; runtime source paths; original cfg; no fast_static allowed. |
| 01_engine2_returned_and_prerank | `inner cell32:10-17; eng/eng_runner.py:18-34; casmi_engine.py:347-381` | Original E.main returned recs[mid].cand with pool smiles, original pv/ours scores and actual blend_scores output; ENG final40; exception/fallback flags. |
| 02_pubchem_returned | `inner cell34:8-19` | PC raw returned dictionary, candidate-specific promotion evidence, fz/pop scores and failure/empty coverage. |
| 03_engine_initialisation | `inner cell27:43-45; cell36:172-190; cell37:13-31` | Actual E.cfg, patched engine SHA, external reference state/pins, pool/library sizes, ranker features/model fingerprints. |
| 04_analog_retrieval | `casmi/engine.py:127-171; hooks_v1.py:49-56` | Actual returned analog SID, smiles, mass, sim, shift, NP flag; target mass and spectrum count. |
| 05_raw_generation | `hooks_v1.py:14-46,58-97; actual hooks_v1.derive_rec calls` | Each actual parent/delta/explicit kwargs and raw returned product SMILES; original derivation exceptions. |
| 06_generation_accepted | `hooks_v1.py:58-99; casmi/engine.py:173-208` | Accepted product smiles/key/formula/mass/parent/raw/combo, and original E._derlog duplicate rejections. |
| 07_pool_mass_window_and_candidates | `casmi/engine.py:210-233; run:243-255` | C.pid/key/smiles/formula/mass/is_gen/gen_sim/gen_steps/gen_tan in original row order; target/drop_pid. |
| 08_actual_160_feature_rank | `fe_v4/v1engine.py:144-158; inner cell37:26-31; cell39:26-36` | Candidate row binding, X/F shape/dtype/content SHA, feature names, original rank scores, full candidate rank indices/SMILES, BASE after cell39. |
| 09_pool_popularity | `inner cell39:39-56` | BASE final order/score/formula slots and pre-popularity actual ranker order. |
| 10_forward_model_scores | `inner cell41:65-128` | Actual ICE_SCORES/GL_SCORES, scored identities, missing/fallback/model-health status, source score files. |
| 11_pubchem_gate_merge | `inner cell43:48-89,91-100` | Pre/post CSV; BASE and PC; pubchem_promotion_audit including leader identity, old/new gate and candidate S/pop/rel. |
| 12_fusion_and_append | `inner cell45:15-55; cell48:8-77; cell49:23-53` | CSV before/after each cell; PREFUSION_LISTS/FUSION_OVERFLOW/BASE_TAIL_CANDIDATES; candidate_audit and experiment_audit. |
| 13_frag_factorial_rank2 | `inner cell51:1-37; cell52:27-173,208; cell53:4-41` | CSV after51/52/53, factorial audit, E2 leader and rank2 control CSV. |
| 14_nested_final_export | `MODULES export_evidence.py:7-43; inner runner.py:16-20` | submission_baseline0465.csv, frozen_candidate_evidence.parquet, effective_query_spectra.parquet, frozen_run_info.json. |
| 15_dual_neural_consensus | `outer cell14:56-85; cell12:117-127,166-238` | Actual neural_public/ours/combined parquet, model bundle hashes, outside-candidate scores/coverage, variants and current CSV. |
| 16_physical_leader | `outer cell15:7-20` | After14 and after15 CSV plus spectral_parallax_report and original control. |
| 17_mass_and_docprior_dedup_backfill | `outer cell19:5-41; cell20:27-80,151-194,196-282` | Before/after CSV; MASS_PEN/MASS_PPM/LIB_MAX; MERGE_REPORT; neural/prior inputs and outsider/LOTUS source fingerprints. |
| 18_mass_leader_rule | `outer cell22:33-59; cell29:15-54` | After20/22 CSV; MASS_LEAD_REPORT, RR8_REPORT, batch_variant_audit.json; actual preset/MASS settings. |
| 19_guarded_trained_head | `outer cell30:17-26; cell31:15-49; guarded_head_tail.py:42-75,98-161` | submission_guarded_tail_control.csv; tail evidence/scores/model audit; guarded_tail_runtime/audit; after30 CSV. |
| 20_ab_measured_library_overlay_FINAL | `outer cell32:5-16; external_library_overlay_20261109.py:105-164,170-206` | submission_external_control.csv/proposed.csv/final.csv, actual match records, protected/skipped reasons, runtime/audit and source library pins. |

## Visibility limits

- **01_engine2_returned_and_prerank**: Internal E2 capture requires install_engine2 after E import/config assignments and before E.main. After-cell32 alone only sees final40. No per-filter reasons inside compute_channels.
- **02_pubchem_returned**: PC is post-search output: this observer cannot distinguish PubChem pre-search catalog absence from internal filtering. It does not replace this child with a proxy.
- **03_engine_initialisation**: Exact champion uses original generator budget 6/150; generation r3/r4 12/300 is not this control. Reference cache fallbacks must be reported.
- **04_analog_retrieval**: This result is after analog retrieval filters; it does not expose all library entries before filtering.
- **05_raw_generation**: Returned raw products already reflect original transform/budget caps; no unexecuted transforms or counterfactual generation are inferred.
- **06_generation_accepted**: Existing rejection log gives duplicate reasons only. Non-duplicate raw-to-accepted losses remain unclassified until offline inspection; never label all missing as a mass failure.
- **07_pool_mass_window_and_candidates**: For catalog recall, separately join the immutable full pool offline. C alone cannot distinguish catalog absence from mass-window loss.
- **08_actual_160_feature_rank**: Record full ranked candidate list before top60; baseline frozen final25 evidence alone cannot measure ranker recall.
- **09_pool_popularity**: Cell-level transition includes both top60 key dedup and popularity; candidate array plus raw rank scores distinguishes losses.
- **10_forward_model_scores**: Dictionary absence is missing model coverage, not a zero score; no proxy/oracle substitution.
- **13_frag_factorial_rank2**: Existing e004 postflight cell50 precedes these rules and is not even the nested final, much less full .488.
- **14_nested_final_export**: This final25 is a restricted view, not all candidates, and still precedes dual-neural/MASS/head/AB.
- **15_dual_neural_consensus**: The private bundle is selected at runtime. Verify actual weights; filenames/author names cannot prove distinct models.
- **16_physical_leader**: PROVENANCE is disabled in this recipe; after17 status verifies it rather than assuming another reranker is active.
- **17_mass_and_docprior_dedup_backfill**: Cell20 bundles several changes. Cell-level delta cannot attribute gain to MASS alone; use frozen candidate score components/call-site observation for a later isolated attribution.
- **19_guarded_trained_head**: Head-only output is not champion final. No new candidate recall can be credited to this identity-preserving step.
- **20_ab_measured_library_overlay_FINAL**: Only after this stage is prediction the exact champion pipeline. AB candidate may be absent from every earlier pool; retain native identity alias and guard behavior.

## Offline error decomposition

Use the SAME pinned official identity on truth and every candidate: remove stereochemistry BEFORE tautomer canonicalisation, then IK14. Preserve the compatible heavy-atom-composition guard where used. Raw SMILES, Engine score_key, plain IK14, and full-formula equality are not interchangeable substitutes.

Bind records by official group/molecule_id, query spectrum IDs and order, stage/channel, original candidate row index, raw candidate SMILES, offline official identity, score/rank, source PID and immutable source/model/asset fingerprints. Freeze predictions and trace hashes before the separate evaluation process reads truth.

Error bins: catalog absent or not generated; catalog present but not retrieved or mass-window rejected; raw generated product not accepted; candidate present but below a retained cap; retained candidate lost or demoted in postprocessing; model unavailable/fallback/unsupported query; exact final correct. Only assign a rejection reason when observed. Query the fixed full catalog offline to distinguish catalog absence from the mass window: V.run output alone cannot do that.

Channels can add the answer late and later stages can rescue earlier losses. Save all loss/rescue transitions and report both first loss and the final responsible transition. A single monotone one-stage attribution would be misleading.

Outer cell20 bundles MASS, documentation/spectral/NP priors, identity deduplication and backfill. Its before/after metric delta cannot identify MASS alone. The guarded head preserves candidate identity membership and prefix7, so it cannot receive credit for candidate-recall gains. Only after outer cell32 AB is the prediction the complete champion.

Existing export_evidence contains only the nested final25 and misses candidates truncated earlier by the ranker. E004 postflight occurs at inner cell50, before remaining cells51/52/53, so it is insufficient for P0 even before outer postprocessing.

## Pins and acceptance

The JSON companion retains all module/model pins, visibility limits, observer entrypoint line numbers and required metrics. The embedded frozen notebook was byte-verified against `runs/generation_production_20261113_r2/kaggle/working/p2s_code/frozen_0465.ipynb`. That old run path is a SOURCE LOCATOR ONLY: its expanded-generation configuration and outputs are not exact-champion evidence.

Observer validation here was limited to AST syntax and an in-memory stub: original return-object identity was preserved, cfg6/150 stayed unchanged and expected actual-call events appeared. This is not a claim of successful real inference. The separate root replay must verify original asset/model/config pins and complete initialization through the AB final CSV. Compare observer-on/off final CSV bytes on the same fixed inputs before claiming behavioral parity.

Keep panel-local official MRR@25/top1/recall, Kaggle leaderboard score, and unknown hidden Class3 prevalence distinct. No new Kaggle score is claimed by this source map.
