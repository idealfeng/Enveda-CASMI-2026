This dataset gathers, with credit, the public models and candidate sets behind the pipeline that most public CASMI 2026 notebooks share, so that it runs offline in one notebook: FPNet fingerprint models, LightGBM rankers, the ICEBERG and GLACIER spectrum simulators, DreaMS, candidate structures from the training set, COCONUT, PubChem, ChEBI, LIPID MAPS and PubChemLite, and RDKit installers. Apart from one spectrum–structure model of our own, every file is an unchanged copy of a public Kaggle resource, kept with its author, licence and checksum. The [data notebook](https://www.kaggle.com/code/dmitriigluzdov/casmi-26-the-data-behind-spectra-to-structures) runs the whole pipeline from it.

![The shared public pipeline in five steps: spectrum, candidates within 10 ppm, FPNet fingerprint match, LightGBM ranking, ICEBERG and GLACIER spectrum check, answer of up to 25 structures.](https://raw.githubusercontent.com/Gluzdov-Dmitrii/Enveda-CASMI-2026/main/kaggle-datasets/casmi26-attributed-v4g-reproduction-assets/architecture.png)

## How the pipeline works

1. **Candidates.** All known structures within 10 ppm of the molecule's neutral mass become candidates.
2. **Fingerprint match.** FPNet reads the spectrum and predicts which structural features the molecule has; candidates whose fingerprints match better score higher.
3. **Ranking.** LightGBM rankers combine the fingerprint match with the similarity to library spectra and other evidence into one score.
4. **Spectrum check.** ICEBERG and GLACIER simulate the spectra of the best candidates; candidates whose simulated spectrum looks more like the measured one move up.
5. **Answer.** Up to 25 structures, best first.

Two such engines run side by side with different candidate sets and models, and a PubChem search adds proposals from outside the main pool; their lists are merged before the spectrum check.

## Models

| Model | What it does | Folder | Authors | Licence |
|---|---|---|---|---|
| FPNet | Predicts a molecular fingerprint [a list of yes/no structural features] from a spectrum. Three checkpoints: one trained on all training data for the main engine and a pair for the PubChem search. | `casmi26-fpnet-full1/`, `casmi26-v3-models/`, `casmi26-v4b-models/` | [Ahmed Berat Özer](https://www.kaggle.com/code/ahmedberatozer/casmi26-v4g-inference) | Other; competition data terms |
| Second-engine fingerprint models | Single and merged models predicting 6,930 fingerprint bits for the second engine. | `casmi26-fp-models-v2/` | [prvsiyan](https://www.kaggle.com/code/prvsiyan/analog-propagation-casmi-2026-baseline) | CC BY-NC-SA 4.0 |
| LightGBM rankers | Combine all candidate evidence into one ranking score ([LightGBM](https://github.com/microsoft/LightGBM)). | `casmi26-v4b-models/`, `casmi26-v3-models/` | Ahmed Berat Özer | Other |
| Feature models | Networks that give the main-engine ranker learned features of each spectrum–candidate pair. | `casmi26-v4b-models/` | Ahmed Berat Özer | Other |
| ICEBERG | Simulates the MS/MS spectrum of a candidate by predicting how it breaks into fragments ([Goldman et al., 2024](https://doi.org/10.1021/acs.analchem.3c04654)). | `casmi26-iceberg/` | Coley group, [ms-pred](https://github.com/coleygroup/ms-pred); runner by Ahmed Berat Özer | Other; ms-pred notices |
| GLACIER | A second spectrum simulator from the same code base; the pipeline uses it first and ICEBERG where GLACIER has no score. | `casmi26-glacier/` | Coley group, [ms-pred](https://github.com/coleygroup/ms-pred); runner by Ahmed Berat Özer | Other; ms-pred notices |
| DreaMS | A transformer that turns a spectrum into an embedding ([Bushuiev et al., 2025](https://www.nature.com/articles/s41587-025-02663-3)), with precomputed embeddings; the current pipeline uses only its structure lists, to fill empty answer places. | `hengck23-dreams-enveda-casmi26/` | Bushuiev et al.; files by [hengck23](https://www.kaggle.com/hengck23) | MIT label; source notices |
| Spectrum–structure model | Scores how well a spectrum matches each candidate: a transformer reads the spectrum, a small network reads the candidate's fingerprint, and the two are compared. Trained by us on the competition training data, after the idea of [Saner Turhaner's neural re-ordering](https://www.kaggle.com/code/sanpier/pubchem-neural025-lb-0-466); the data notebook uses it to re-order its final lists. | `casmi26-spec2mol/` | Dmitrii Gluzdov | CC BY-NC-SA 4.0; competition data terms |
| FPNet pair for simulated rows | Fingerprint models released with simulated ranker training rows. | `casmi26-simulated-ranker-rows/` | [megayak](https://www.kaggle.com/code/megayak/casmi26-two-rankers-one-engine) | CC0 label; source notices |

## Candidate sets

| Set | Contents | Folder or files |
|---|---|---|
| Main pool | 710,701 structures: the training molecules and COCONUT natural products, with fingerprints and fragment masses. | `casmi26-v2-pool/` |
| COCONUT candidates | COCONUT structures with fingerprints for the second engine. | `coconut-casmi26-candidates/` |
| PubChem tier | 105.9 million PubChem structures sorted by mass, searched outside the pool. | `pubchem_tier__pc_*.npy` |
| ChEBI and LIPID MAPS | Standardised structures from ChEBI and LIPID MAPS, plus the earlier bank kept for older notebooks. | `casmi-chebi-lmsd-structures/`, `chebi-lipidmaps-casmi26/` |
| PubChemLite | PubChemLite candidates with fingerprints. | `casmi26-pubchemlite-cc0-candidate-fingerprints/` |

`casmi26-ranker-features/` holds ranker training features, and `rdkit-2026-3-3-wheel/` and `rdkit-wheels/` install RDKit offline: 2026.03.3, the scorer's version, and 2025.03.6 for the spectrum simulators. Folder names repeat the names of the source Kaggle datasets so that every file can be traced to its author.

## Quick start

The example finds the dataset in either supported Kaggle mount location and lists its folders with their sizes.

```python
from pathlib import Path
slug = 'casmi26-attributed-v4g-reproduction-assets'
D = next(p for p in (Path('/kaggle/input/datasets/dmitriigluzdov') / slug, Path('/kaggle/input') / slug) if p.is_dir())
for f in sorted(p for p in D.iterdir() if p.is_dir()):
    files = [q for q in f.rglob('*') if q.is_file()]
    print(f'{f.name:48s} {len(files):4d} files {sum(q.stat().st_size for q in files) / 1e9:6.2f} GB')
```

## How it was made

Every source file was copied unchanged; the spectrum–structure model was trained from the competition training file. `MANIFEST.json` gives the source dataset, size, SHA-256 checksum and current location of the first 134 files and of the model's three files, and `ATTRIBUTION.md` and `SOURCE-LICENSES.md` the authors and terms of every folder. Running the pipeline from these files reproduces its inputs; the score also depends on the exact notebook that runs them.

## Updates

- **2026-10-27:** Added our spectrum–structure model.
- **2026-10-20:** Renamed from “CASMI26 Attributed v4g Reproduction Assets”; removed 131 top-level files (3.8 GB) that duplicated the source folders byte for byte, with `MANIFEST.json` now pointing to their folder copies.
- **2026-10-18:** Added the PubChemLite candidates and fingerprints.
- **2026-10-16:** Added the standardised ChEBI and LIPID MAPS structures.
- **2026-10-13:** Added copies of fourteen public datasets for the two-engine pipeline.

## Licence and credits

The collection follows **CC BY-NC-SA 4.0**, with component-specific terms retained. Non-commercial use, attribution and share-alike apply to the relevant files; competition-derived and COCONUT-derived assets also retain their source restrictions. Ahmed Berat Özer's upstream dataset fields are **Other**, with terms in their cards. His linked notebook code is Apache-2.0; this does not relicense all models and data as Apache-2.0 or CC0.

Credit [Ahmed Berat Özer](https://www.kaggle.com/code/ahmedberatozer/casmi26-v4g-inference) for the original inference code, candidate collections, FPNet models, LightGBM rankers and model runners. [prvsiyan](https://www.kaggle.com/code/prvsiyan/analog-propagation-casmi-2026-baseline) supplied fingerprint models, ranker features and candidate banks under CC BY-NC-SA 4.0. [megayak](https://www.kaggle.com/code/megayak/casmi26-two-rankers-one-engine) supplied simulated ranking rows under CC0. sergiomalv supplied the later ChEBI/LIPID MAPS set under CC BY 4.0; franciscoangulo supplied PubChemLite candidates under CC0, derived from cosmicbe and [Schymanski et al., 2021](https://doi.org/10.1186/s13321-021-00489-0).

ICEBERG and GLACIER are by the Coley group ([ms-pred](https://github.com/coleygroup/ms-pred); [Goldman et al., 2024](https://doi.org/10.1021/acs.analchem.3c04654)). hengck23 supplied the MIT-labelled DreaMS resource; DreaMS is by [Bushuiev et al., 2025](https://www.nature.com/articles/s41587-025-02663-3). The RDKit developers supplied the chemistry toolkit; metric and eveliaveldrine supplied the wheels, whose recorded labels are unknown and Apache-2.0 respectively, with original notices retained. Primary data come from Enveda, [COCONUT](https://coconut.naturalproducts.net/), [ChEBI](https://www.ebi.ac.uk/chebi/), [LIPID MAPS](https://www.lipidmaps.org/) and [PubChem](https://pubchem.ncbi.nlm.nih.gov/). Copying and documenting these resources does not claim authorship of them.
