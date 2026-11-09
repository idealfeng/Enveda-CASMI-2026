# Roman Rozen: From Peaks to Structures

Source: https://www.kaggle.com/code/romanrozen/0-468-casmi-from-peaks-to-structures

Fetched 2026-11-04. **Useful as a source of incremental experiments; largely the same pipeline we already reproduced.** Only small source/metadata files were fetched. No model assets were downloaded, no environment installed, and no downloaded notebook/module was executed.

## Exact snapshot and score limits

- Kaggle pull metadata reports **V8**, kernel ID `140764933`; the public page's oEmbed URL identifies script version `365039563`.
- `original_v8.ipynb`: 695,770 bytes; SHA-256 `98008df2e1fbabf66acbdab8a5beff9550ccc4f1ed1447352672a9710628362b`.
- `pull_v8.json` explicitly requests `versionLabel=v8` and contains the same source bytes as `pull_latest.json`.
- `[0.468]` remains in the title. The current source describes a **0.480 neural ensemble** and adds a default **TAX experiment**. The 0.480 board result is an author claim in Markdown, not an independently verified score for the current V8 TAX code. All code-cell outputs/execution counts in this source are cleared.
- The browser tool could not render the page; direct HTTP acquired only its HTML shell, including title, date and oEmbed version link. It contains no rendered score or notebook-license field. The anonymous kernel-list API required authentication. The linked second-model trainer pull returned HTTP403.

## What differs from our Flex V56

Static AST extraction verifies that the frozen 0.465 baseline, **all eight helper-module hashes**, and **all four Saner model pins** are identical to our Flex V56 snapshot. The common frozen SHA is `d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88`.

| Item | New value |
| --- | --- |
| Neural ensemble | `0.5*z(public)+0.5*z(second model)`, standardized within each molecule; supplies a potentially independent ranking signal. |
| Taxonomic prior | Default `PRESET='TAX'`; LOTUS genus support from confident library-hit leaders gives a small leave-one-out bonus on ranks 2–25. `NE480` is its off control. |
| Evidence gates | TAX requires at least 6 specific anchors and genus co-occurrence above a random-set p95 and 0.25 floor. Missing data/errors disable the bonus. |
| Experimental record | Documents negative experiments: better standalone fingerprint similarity did not necessarily improve candidate-ranking MRR/board score. These are the authors' reports. |

The final merge/dedup code also differs from Flex's separate final layer, so identical baseline/helper hashes do not establish identical final answers. This code has a last raw-SMILES fill path; metric-identity uniqueness needs an explicit audit before adopting it.

## Reproduction dependency that matters

The second scorer is found by searching for `final_model.pt` plus `config_used.json` (or an accepted ours directory). Its weight SHA is not pinned. Pull metadata attaches **`deleted/142141665`** as a kernel data source; the notebook metadata lists kernelVersion `364605128`. No second-model payload was acquired in this review.

If the second model is absent, `_swap_to_ours()` prints a message and returns the public bundle. Both ensemble arms can then use the same model, providing no additional independent signal while the pipeline still runs. A completed run alone would not prove reproduction of the advertised two-model experiment.

The TAX files `lotus_structure_genus.parquet` and `natural_products.parquet` are already present in our D: knowledge-table snapshot. TAX assumes useful shared organism information across the query set; its gates and any gain need evaluation on an appropriate held-out query set. The visible 12 training examples cannot establish that gain.

## Inputs and licenses

The API attaches the Saner public model, fold-safe FPNet, knowledge table, natural-product panel, popularity prior, attributed v4g assets, catalogue experiment, official RDKit wheel, competition data, and the deleted kernel reference. See `metadata_v8.json` / `review.json` for exact names and source IDs.

Whole-notebook licensing was not exposed by the acquired page/API. Existing component metadata includes Apache 2.0 for Saner's dataset, CC BY-NC-SA 4.0 for attributed assets, and component-specific terms for other collections. The source's prose contains additional license claims; it does not resolve all component terms or medal eligibility.

## Recommended next step

Keep this snapshot and use its two additions as **separate A/B experiments**. First locate/verify the second-model training source and checkpoint. Reuse the already generated Flex frozen candidate evidence and query spectra for later reranking instead of rebuilding the common library/E2 pipeline. Compare the ensemble alone, then TAX on/off, on an identity-disjoint validation set. No fourth full run or large asset download is justified by the title alone.

`review.json` records the evidence boundaries. `extraction_receipt.json` binds the safely extracted helper/frozen/taxonomy source hashes. `cells/` and `embedded/` contain source for inspection only.
