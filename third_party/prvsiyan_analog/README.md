# prvsiyan Analog Propagation V43: downloaded source

This folder contains an unmodified source snapshot downloaded anonymously from Kaggle on 2026-11-04. It has **not been executed**.

- Original notebook: https://www.kaggle.com/code/prvsiyan/analog-propagation-casmi-2026-baseline
- Version: **43**, scriptVersionId **360497306**.
- Source: `prvsiyan_v43.ipynb`; SHA-256 `a1da86c791cdbcb553254a12cef8bca8b527b991f40953d9dcb2a9c819d3c852`.
- `kaggle_pull_latest.json` is the complete raw API response. `metadata_v43.json` retains the source Docker-image digest and input slugs.
- `prvsiyan_v43_source.txt` is a convenience concatenation of code cells; it is not a standalone Python runner.
- `embedded_sources/` contains selected literal Python payloads extracted statically, without evaluating notebook code.
- `manifest.json` records source identity and checks. All 32 code cells parse as Python AST; this is not a runtime check.

## Input inventory

`dependency_sources.json` and `dataset_metadata/` retain official public API metadata and the complete paginated file inventory. These are the datasets' **currently observed versions**, not proven notebook-bound historical versions. `kernels/pull` supplies dataset slugs but no per-input version IDs.

`minimum_inputs.json` selects a practical 13.0 GB input set (uncompressed), before local train data, Python packages, runtime caches and output. Files are not downloaded merely because they are listed here.

The 80.4 GB popularity dataset does not need a wholesale download. This source references only:

| File | Bytes |
| --- | ---: |
| `pc_lsid.npy` | 211,751,106 |
| `pc_lpmid.npy` | 211,751,106 |
| `pool_lsid.npy` | 1,421,530 |
| `pool_lpmid.npy` | 1,421,530 |

The source chooses the popularity directory via `pc_lsid.npy`, and the extracted `cell14_V17_PATCH.txt` also loads `pc_lpmid.npy`. Both pool arrays are read directly by the notebook. Total: 426,345,272 bytes.

Other selection details:

- From `megayak/casmi26-simulated-ranker-rows`, only `sim_rank_rows_nofp.npz` is referenced. Its two FPNet checkpoints and other ranker rows are unnecessary here.
- Both checkpoints in `ahmedberatozer/casmi26-v3-models` are loaded by `glob('fpnet_*.pt')` in the PubChem runner. Removing one changes the ensemble.
- The V4 setup verifies **every file in its MANIFEST**. Keep the full V4 bundle unless explicitly implementing and validating a different setup path.
- The official RDKit dataset contains four interpreter wheels; source Python 3.12 needs only its cp312 wheel. These bundled wheels are Linux builds.

Anonymous per-file download was tested successfully for V4 `MANIFEST.json`:

`https://www.kaggle.com/api/v1/datasets/download/ahmedberatozer/casmi26-v4b-models/MANIFEST.json?datasetVersionNumber=4`

## Runtime constraints

The notebook uses absolute `/kaggle/input` and `/kaggle/working` paths, symlinks, subprocesses and Linux offline wheels. It is not an unchanged Windows script. Its main RDKit is 2026.03.3, whereas ICEBERG/GLACIER require an isolated 2025.03.6 environment. A compatible Linux runtime is the closest reproduction target.

`run_local_linux.py` is a local adapter. It leaves the original notebook unchanged, translates Kaggle paths, replaces the T4-only observer with actual GPU reporting, and checks the explicitly supplied local competition directory. Ranking, models, smoke selection and stage-health assertions remain in the original source. A WSL Ubuntu `--prepare-only` check parsed all 32 adapted code cells and verified that hash-bound N1 embedded scripts remain unchanged; model execution is still pending.

Example (after preparing a compatible Linux environment and all required inputs):

```bash
.venv-linux/bin/python third_party/prvsiyan_analog/run_local_linux.py \
  --input-root /mnt/d/Paper/casmi/assets/kaggle \
  --work-root /mnt/d/Paper/casmi/artifacts/prvsiyan_v43/smoke \
  --competition-root /mnt/d/Paper/casmi/enveda-CASMI26-molecule-id-mass-spectra
```

Add `--prepare-only` to write adapted cell files and a patch receipt without running model code. A run records every cell's completion/failure, source and adapted hashes, and output hashes in `local_run_receipt.json`. The source's own `e004_verification.json` contains historical ancestor-source IDs; use the adapter receipt for the downloaded V43 source identity.

For this machine's memory budget, first build the equivalent cleaned spectrum cache with `scripts/build_shared_spec_cache.py`, then add `--shared-spec-cache /mnt/d/Paper/casmi/runs/shared_spec_cache --mmap-pool`. The shared `scripts/reproduction_io.py` helper checks source/structure identity and input rows/size before linking four cache files. It applies module-local copy-on-write mmap (`mmap_mode='c'`) to the Library CSR arrays and optional Pool fingerprint/fragment arrays. The runner maps the outer training-fingerprint load the same way. Global NumPy is unchanged; the downloaded source is unchanged.

The streaming builder was compared with the original on row group 20: **1184 spectra, 152902 cleaned peaks**, identical CSR dtypes/values and exact pandas metadata. Copy-on-write Library search and representative selection also matched the original exactly on that fixture, with writeable-array semantics preserved. Reports are in `cache_equivalence_rg20/`. These checks verify cache/IO equivalence on a fixture, not competition accuracy.

## Recover after a later stage fails

The first local V43 run completed Engine2 and saved `runs/prvsiyan_smoke_20261104a/eng_lists.json`, then failed in a later stage. To recover in a **new** work directory, append:

```bash
--reuse-engine-lists /mnt/d/Paper/casmi/runs/prvsiyan_smoke_20261104a/eng_lists.json
```

This optional mode validates the old run receipt, exact Notebook source hash, successful Engine2 cell, saved adapted cell hash, and four generated Engine2 sources. It fingerprints the full active query table, including peaks, metadata, row order and pandas index, and requires exact target IDs. It binds the complete attached-input payload file metadata and all three competition files. Any input payload modified after the old Engine2 result was written is rejected. The original run did not snapshot all inputs at Engine2 completion, so this is explicitly a **retrospective metadata binding**; download hashes are recorded from their receipts and large inputs are not rehashed by this option.

Only the Engine2 subprocess call in cell12 is replaced by validated JSON copying. `ENG_FILES` generation remains, all subsequent stages execute, and their normal failure checks still apply. The recovery receipt marks Engine2 reuse and excludes any cold-start claim. `engine2_reuse_binding.json` retains the full binding. `--prepare-only` performs these checks and prepares the adapted cells without starting models.

The source's Notebook `display` global is supplied through `IPython.display.display`, with a text-only fallback if IPython is unavailable. This is an output compatibility adapter and does not change candidates.

On the visible dummy test, cell 10 deliberately selects only the first 12 molecules and reduces some simulator budgets. Full hidden scoring is a different execution path. **Even this 12-molecule smoke builds the complete training spectral cache and candidate banks**, so most input data remains necessary. The notebook page's runtime must not be described as a measured full hidden-test runtime.

## License and attribution

Credit: prvsiyan and all upstream authors credited by the original notebook; the downloaded source preserves those credits. The notebook page declares Apache-2.0, but several attached artifacts (`casmi26-fp-models-v2`, `casmi26-ranker-features`, `coconut-casmi26-candidates`) explicitly declare CC BY-NC-SA 4.0. Other datasets have source-specific terms. Local research availability does not establish eligibility for a medal/prize submission. See the original metadata and the hosts' clarification: https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/748882 .
