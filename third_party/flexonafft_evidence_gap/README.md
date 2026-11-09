# Flexonafft: Closing the Evidence Gap

Public source: https://www.kaggle.com/code/flexonafft/casmi26-closing-the-evidence-gap

Fetched on 2026-11-04. Original Kaggle pull responses and source notebooks are retained separately for **V56** and **V61**. The pull API confirms the requested version number. The public page search index reports best public MRR@25 **0.479 at V56**, while V61 reports 0.473. These are upstream records, not scores reproduced here.

## Files

- `v56/original.ipynb`, `v61/original.ipynb`: exact source strings returned by Kaggle.
- `pull_v56.json`, `pull_latest_v61.json`: complete original API pull responses.
- `v56/embedded/`: safely extracted source literals, including the base64-embedded frozen baseline, eight verified helper modules, engine 2 sources, fragmentation and PubChem wrappers.
- `v56/extraction_receipt.json`: original SHA-256 bindings and neural-model pins. V61 has a corresponding receipt.
- `dataset_metadata/`: fetched dataset metadata and complete paginated file lists.
- `minimum_download_plan.json`: conservative inference-file selection; original API file sizes, version snapshots, per-file download URLs and verified shared-tier reuse information.
- `dependency_sources.json`: source/dependency status and evidence limits.
- `run_local.py`: creates and runs an adapted copy; original sources remain intact.

No fetched notebook code was executed during source acquisition or static extraction. `extract_sources.py` uses AST literal extraction; the eight helper-module hashes and frozen-notebook hash match the pins in the original source. The local runner's prepare-only path was checked on Windows, including syntax compilation of adapted top-level code cells. A later Linux stage-0 run passed model-bundle discovery, all four exact model-file pins and official RDKit 2026.03.3 bootstrap in 12.626 seconds; see `bootstrap_probe_20261104b/local_reproduction_status.json`. A complete V56 inference run is still pending.

## Download scope

The file plan totals **14,676,761,014 bytes** across 447 files. Of this, **7,214,128,278 bytes** are the shared PubChem mass/offset/SMILES arrays, so an existing verified copy can be hard-linked rather than downloaded again. Per-file original-source SHA-256 values are included for those three arrays. The additional physical download is approximately 7.46 GB before further reuse with other public schemes.

The metadata advertises eight datasets; static V56 inference needs six. The long-schedule second neural model and catalogue replay dataset are not referenced by V56 inference. The 80 GB popularity dataset contains large precomputed fingerprint shards that this V56 source does not use; those shards are excluded. The plan also excludes the large DreaMS embeddings and incompatible Python-version wheels.

Current dataset snapshots are pinned in the file plan. The notebook pull metadata does **not** identify the original mounted dataset-version IDs. Source-declared model/manifests must still validate at runtime; fetching a current snapshot is not itself proof of exact original inputs.

## Local execution

Use Linux Python 3.12, for example WSL. The original simulator package includes a Linux/cp312 RDKit 2025.3.6 wheel, while the main scoring environment requires RDKit 2026.03.3. They remain isolated in the source's simulator site. CUDA-enabled PyTorch, NumPy, pandas, PyArrow, scikit-learn, LightGBM, Numba, IPython and Matplotlib are required by the main path. The source performs its own offline wheel bootstrapping.

Store downloads at:

```text
assets/kaggle/<owner>/<dataset-slug>/v<version>/<file>
```

Then prepare without inference:

```bash
.venv-linux/bin/python third_party/flexonafft_evidence_gap/run_local.py \
  --input-root assets/kaggle \
  --work-root outputs/flexonafft_v56_smoke \
  --prepare-only
```

Remove `--prepare-only` to execute. The default is the original 12-molecule visible-test smoke path. Use a fresh work directory for each run. `--full` enables all visible molecules and can take substantially longer. The full local visible test is still a placeholder and provides no hidden-test generalization score.

Use `--materialise-only` to run the stage-0 source, exact model-pin and RDKit checks, then stop before inference. Before each WSL command, source `/mnt/d/Paper/casmi/scripts/linux_env.sh` so all caches and temporary files remain on D:.

For the completed shared spectrum cache, add:

```bash
  --shared-spec-cache runs/shared_spec_cache
```

This uses `scripts/reproduction_io.py` after the upstream manifest checks. The helper verifies a completed full-input cache receipt, cleaning-source hashes, numeric file sizes, runtime training-file path/size/row count and training-structure identity/order. It links the four clean-CSR files instead of rebuilding them. Only the Library/Pool modules' targeted numeric loaders and the single `train_fp_sel.npy` load use copy-on-write memory mapping (`mmap_mode='c'`). The global NumPy module, original cached files, model weights and ranking calculations are unchanged. The runner records the helper/cache-receipt hashes and writes a runtime IO receipt. The optional shared-cache path was syntax/hash checked without executing a model.

The second engine's original raw-peak CSR is a separate representation; it is not replaced by the cleaned shared cache.

The runner creates an input view using directory symlinks to pinned dataset directories and the existing competition data. The Saner model bundle instead uses real parent directories and five leaf-file symlinks: Python 3.12 `Path.rglob()` does not descend directory symlinks, and the original bundle finder uses `Path.rglob()`. This preserves the original finder and its four model-file SHA checks. The runner rewrites `/kaggle/input` and `/kaggle/working` to workspace paths in a generated notebook, regenerates embedded-source hashes after those edits, and records both original and adapted hashes. The observer's allowed competition paths are compared after resolving the symlinks. Model pins and ranking parameters are unchanged. This adaptation has not yet been proved numerically equivalent by a completed inference run.

## Limits that affect reproduction

- The pipeline builds/searches the full training spectral library even in a small query smoke. A 15 GB host may need memory-aware cache work before the original pipeline fits reliably.
- Linux paths, symlinks and Linux simulator wheels are used throughout. A direct native-Windows run is not equivalent; the runner requires Linux for actual inference.
- The upstream smoke fills unprocessed public IDs with placeholders. Those rows must not be described as model predictions or submitted as a fully processed local result.
- Dataset `dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets` is currently labelled **CC BY-NC-SA 4.0**. This conflicts with assuming that the entire public high-score stack is commercially redistributable. Research reproduction is distinct from proving eligibility for competition awards; component provenance and replacements remain necessary before adopting the stack as our award-targeted solution.

Original API endpoint used for V56:

```text
https://www.kaggle.com/api/v1/kernels/pull?userName=flexonafft&kernelSlug=casmi26-closing-the-evidence-gap&versionLabel=v56
```

The `v` prefix in `versionLabel` is required. The response confirms `metadata.currentVersionNumber == 56`.
