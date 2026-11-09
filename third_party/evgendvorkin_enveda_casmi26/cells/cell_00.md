# 🔬 Forensics Lab — Enveda CASMI 2026

> *Welcome to the Forensics Lab. 400 molecules — 400 unsolved cases.*
>
> *We have fingerprints, but no suspects. Can we uncover their identities?*

---

## 🕵️ The Case — The Mystery of Unknown Molecules

Modern mass spectrometry can detect **thousands of different molecules** in nature. But detecting a molecule is not the same as knowing what it is.

Imagine investigating a crime with nothing but a **partial fingerprint**.

When a molecule undergoes collision-induced fragmentation, it breaks into smaller pieces. The result is an **MS/MS spectrum** — a collection of peaks representing the fragment ions produced.

Our mission is to reconstruct the original molecular structure from these indirect clues.

Sometimes the suspect is already in the database. Sometimes their identity is known, but no fingerprints are available. And sometimes the suspect has never been registered anywhere.

That's when we must **reconstruct the suspect's portrait from scratch**.

---

## 🧩 Mapping the Investigation — A Detective's Guide

| Chemistry | Forensics Analogy |
|---|---|
| **MS/MS spectrum** | 🖐️ Fingerprint left at the crime scene |
| Fragment peaks (`m/z`) | Individual ridges and patterns of the fingerprint |
| Peak intensities | How clearly each trace was imprinted |
| Precursor `m/z` | The suspect's approximate height and build |
| Adduct (`[M+H]+`, `[M+Na]+`) | The conditions under which the fingerprint was left |
| Collision energy | How strongly we disturbed the evidence to reveal its fragments |
| Molecular formula | The suspect's known chemical composition |
| **SMILES** | 🎨 The complete wanted poster |
| InChIKey14 | A way to recognize equivalent molecular structures |
| **Top-25 candidates** | A lineup of 25 suspects |
| **MRR@25** | How high the real culprit appears in the lineup |

Of course, this is only an analogy. In reality, every peak depends on chemical bonds, ion stability, fragmentation conditions, and many other factors.

---

## 🚨 Three Levels of Difficulty — Three Types of Cases

| Class | Forensics Analogy | Main Approach |
|---|---|---|
| 🟢 **Class 1** | The suspect is already in the police database, fingerprints included | Spectral library search |
| 🟡 **Class 2** | Interpol knows the suspect, but has no fingerprints | Molecular database retrieval |
| 🔴 **Class 3** | A ghost — the structure is missing from available databases | De novo structure generation |

**The fundamental challenge:** these classes require different sources of evidence.

For Class 1, direct spectral matching is especially useful. For Class 2, we need to predict structural properties and retrieve plausible candidates. For Class 3, we may need to reconstruct the molecular structure itself.

---

## ⚖️ The Rules of the Game

- 🎯 **400 molecules** in our original description of the challenge; each molecule may have multiple MS/MS spectra.
- 📇 **One prediction per `molecule_id`** — all spectra belonging to the same molecule contribute to the final decision.
- 🏆 **MRR@25** — a correct answer at rank 1 earns 1.0; at rank 25, it earns 0.04.
- 🎭 **Metric-aware identity** — evaluation uses official canonicalization, including stereochemistry and tautomer handling.
- ⏱️ **Limited runtime** — inference must finish within the Kaggle notebook submission constraints.
- 🔒 **Internet Off** — required models, data, and dependencies must be available through attached datasets.

The goal is not merely to include the correct molecule among our predictions.

We must **rank it as high as possible among the 25 suspects**.

---

## 💡 The Detective's Insight

> Most investigations begin by searching for the right suspects.
>
> But the hardest cases are solved when we understand **why a particular molecule leaves exactly that spectral fingerprint**.

In an earlier version of our story, we described roughly two-thirds of the challenge as retrieval and the remaining part as genuine structural investigation. This is a useful intuition, not a result established by our own independent validation.

**Our goal is to distinguish missing-candidate failures from ranking failures — and understand which physicochemical signals can solve each type of problem.**

---

## About the Works This Solution Is Based On

The current solution builds upon the progressive development of ideas from **13 public works**. Each contributed a distinct component to the overall architecture.

**1. Analog Propagation (V10)** — [prvsiyan](https://www.kaggle.com/code/prvsiyan/analog-propagation-casmi-2026-baseline).

One of the first strong retrieval systems: spectral libraries, analog propagation, MetFrag-lite, and FPNet. 25 features, two priors, and four random seeds. **Public LB 0.335.**

**2. 4-Channel Retrieval & Neural Fingerprint Ranker (V17)** — [haideptry](https://www.kaggle.com/code/haideptry/enveda-casmi-2026-fast-spectral-cosine-baseline/notebook).

Four retrieval channels, 31 features, and neural fingerprint scoring through `f·z`. **Public LB 0.339.**

**3. Two Rankers, One Engine** — [megayak](https://www.kaggle.com/code/megayak/casmi26-two-rankers-one-engine).

Adduct-shifted spectral search and a blend of two independent rankers. **Public LB 0.337.**

**4. CASMI26 Next Direct W088** — [Jiachen Li](https://www.kaggle.com/code/llccqq624/casmi26-next-direct-w088/notebook).

Tuned `w_pv = 0.88` and addressed important candidate-ranking issues. **Public LB 0.341.**

**5. CASMI 26: From Spectra to Structures** — [Dmitrii Gluzdov](https://www.kaggle.com/code/dmitriigluzdov/casmi-26-from-spectra-to-structures).

Retrieval + Class-3 generation, 160 features, four LightGBM boosters, an isolated PubChem channel, ICEBERG, and GLACIER. **Public LB 0.373.**

**6. casmi26-v4m-inference** — [Ahmed Berat Özer](https://www.kaggle.com/code/ahmedberatozer/casmi26-v4m-inference).

Introduced **`fpnet_full1`**, trained on the full training set, strengthening the spectrum-to-fingerprint representation. **Reported improvement: +0.013 LB.**

**7. casmi26 e5c union gl a06** — [Seyit Kaan Gunes](https://www.kaggle.com/code/seyitkaangunes/casmi26-e5c-union-gl-a06/notebook).

Added Engine 2 with **BIO (ChEBI + LIPID MAPS)** and **AFIX (formula-derived mass)**, expanding candidate coverage and combining independent retrieval systems. **Public LB 0.386.**

**8. casmi26 v4n engine fusion union** — [Seyit Kaan Gunes](https://www.kaggle.com/code/seyitkaangunes/casmi26-v4n-engine-fusion-union-lb-0-399/notebook).

Combined `fpnet_full1`, ICEBERG/GLACIER coefficients, and a stronger two-engine fusion strategy. **Public LB 0.399.**

**9. V10 Apex Fusion SOTA** — [BobtheBot369](https://www.kaggle.com/code/bobthebot369/enveda-casmi-2026-v10-apex-fusion-sota/notebook).

Introduced a PubChem popularity prior with `μ = 0.15`, using external frequency-based evidence to improve candidate ranking. **Public LB 0.401.**

**10. CASMI26 V44 PairTail Locked Top1** — [Imran Arif](https://www.kaggle.com/code/imranarif536/casmi26-v44-pairtail-locked-top1/notebook).

Added LambdaRank for tail candidates, rank-1 protection, and scorer-aware candidate cleanup. **Public LB 0.417.**

**11. CASMI26 V1.1 — Metric Audit and Safe Tail** — [OBSTACLE DEVELOPER](https://www.kaggle.com/code/obstacledeveloper/casmi26-v1-1-metric-audit-and-safe-tail/notebook).

Introduced a smoke/full-rerun switch, official metric-aware canonicalization, equivalent-candidate removal, overflow recovery across multiple engines, and safe filling of vacant top-25 positions without worsening the ranks of existing structures. **Public LB 0.433.**

**12. CASMI26 v7c E006 FragGap** — [Ahmed Berat Özer](https://www.kaggle.com/code/ahmedberatozer/casmi26-v7c-e006-fraggap/notebook).

Introduced an **adaptive forward cascade**: GLACIER when coverage is available, ICEBERG where GLACIER is blind, and MetFrag-lite `FRAG_GAP` (`λ = 0.5`) when neither forward model provides useful evidence. **Public LB 0.441.**

**13. CASMI 26: The Data Behind Spectra to Structures** — [Dmitrii Gluzdov](https://www.kaggle.com/code/dmitriigluzdov/casmi-26-the-data-behind-spectra-to-structures?scriptVersionId=361008383).

A new stage in the evolution of the pipeline:

- Five-fold FPNet ensemble;
- Natural-product, LOTUS, and PubChem synonym priors;
- PubChemLite and standardized BIO candidates;
- Additional reference spectra;
- Deterministic adduct selection;
- GLACIER proxy and joint ICEBERG–GLACIER scoring;
- Engine-2 rank-2 insertion;
- An additional PubChem candidate at rank 24.

**Public LB 0.464 — our reproduction target.**

This is the direct source of the current Version 18. Ownership and attribution of models, datasets, and individual components remain with their respective authors.

---

## Growth Pattern — The Evolution of the Investigation

| Version | Main Improvement | ΔLB | Public LB |
|---|---|---:|---:|
| v4i | Baseline, `PC_N1=5000` | — | 0.373 |
| v4l | `ICE_LAM = GL_LAM = 1.0` | +0.007 | 0.380 |
| v4n-e5c | Two-engine fusion + BIO/AFIX | +0.006 | 0.386 |
| v4n-engine-fusion | `fpnet_full1` + forward fusion | +0.013 | 0.399 |
| V10 Apex | Popularity prior | +0.002 | 0.401 |
| V44 PairTail | LambdaRank + top-1 protection | +0.016 | 0.417 |
| V1 | PubChem promotion + GLACIER rerank | +0.008 | 0.425 |
| V1.1 | Metric-safe tail | +0.008 | 0.433 |
| E004 / v80 | Metric-identity voting | +0.003* | 0.436 |
| ICE fallback | ICEBERG where GLACIER is blind | +0.002* | 0.438 |
| E006 | Window-40 fusion + fallback | +0.002* | 0.440 |
| v7c FragGap | MetFrag where forward models are blind | +0.001* | 0.441 |
| **Data Behind — v20** | **Fold FPNet + chemical priors + proxy rescoring + candidate insertion** | **+0.023*** | **0.464** |

\* These are sequential differences between reported public scores, **not experimentally isolated causal effects**. Some versions modify multiple components simultaneously.

**Research insight:** over time, the strongest solutions have evolved from improving individual models toward integrating increasingly diverse and partially independent sources of evidence.

---

## Main Signals — The Evidence Behind Our System

**1. Spectrum-to-Fingerprint Prediction**

`fpnet_full1` and additional fold-safe FPNet checkpoints predict molecular structural properties from observed spectra.

**2. Library and Analog Retrieval**

Experimental spectra are compared with reference measurements and structurally related molecules, including cases involving different adducts.

**3. BIO, AFIX, and PubChemLite**

These channels expand the pool of suspects the ranking system can consider in the first place.

**4. PubChem and Natural-Product Priors**

Popularity, depositor evidence, synonyms, LOTUS literature, and natural-product membership provide additional evidence about molecular plausibility.

**5. Two-Engine Metric-Identity Fusion**

Independent rankings are combined without allowing multiple representations of the same structure to receive duplicate votes within an engine.

**6. ICEBERG and GLACIER**

These forward models predict candidate fragmentation and compare the simulated evidence with observed MS/MS spectra. Additional GLACIER proxies extend the applicability of forward scoring.

**7. MetFrag-lite FragGap**

Uses interpretable fragment-mass evidence when more sophisticated forward models cannot provide useful scores.

**8. Engine-2 Rank-2 Insertion**

Gives a strong candidate from the second engine a prominent position in the final ranking.

**9. Metric-Safe Tail**

Fills the top-25 list with unique structures while preventing the loss of already discovered correct metric identities.

---

## What Changed Conceptually — From More Models to Better Decisions

In the early stages, the development process looked roughly like this:

**New model → new score → better ranking.**

Then came additional retrieval engines, PubChem popularity, and forward-spectrum simulators.

But the latest strong solutions reveal a more interesting pattern.

The system is now trying to answer several different questions:

- **Is the correct molecule present among our candidates?**
- **Which data source is most likely to retrieve it?**
- **How much can we trust the available spectral evidence?**
- **Where do our forward simulators actually provide useful coverage?**
- **When do external chemical priors help, and when do they introduce bias?**
- **How can we combine all signals without losing a correct candidate?**

Our current architecture can be summarized as:

**Candidate Retrieval → FPNet Evidence → Chemical Priors → Forward / Proxy Scoring → Metric-Aware Fusion → Top-25 Construction**

This is the central pattern worth looking for when studying future top-performing solutions.

---

## Reproduction Protocol — Version 18

**Current objective: reproduce the public 0.464 score.**

Original work: [Dmitrii Gluzdov — pinned notebook, scriptVersionId 361008383](https://www.kaggle.com/code/dmitriigluzdov/casmi-26-the-data-behind-spectra-to-structures?scriptVersionId=361008383).

In this version:

- All **24 executable blocks** of the original inference pipeline are preserved.
- Each block is preceded by Markdown with an English heading and a Russian technical explanation.
- Algorithms, coefficients, checkpoints, candidate slots, and scoring logic remain unchanged.
- Exploratory EDA cells, visualizations, and demonstrations have been excluded.
- The original author's datasets and models are used.
- The configuration includes the additional PubChem candidate at rank 24.
- The visible smoke run is treated strictly as an operational check.

**Public 0.464 is the source notebook's reported result, which our own Kaggle submission must still independently confirm.**

At this stage, we are not claiming a new algorithm or an original model improvement.

---

## Research Roadmap — Beyond Public Reproduction

Once reproduction is confirmed, our objective changes: instead of continually copying stronger public solutions, we will focus on developing an original, robust improvement.

**Candidate Recall**

Investigate which molecular classes are missing the correct structure from the candidate pool, and why existing databases fail to provide sufficient coverage.

**Spectrum Representation**

Understand which properties of MS/MS spectra truly distinguish structural isomers and which information is lost in current fingerprint representations.

**Validation**

Build independent validation splits that account for structural similarity, molecular families, spectral data sources, and potential information leakage.

**Model Complementarity**

Identify which models correct each other's errors and determine whether these complementary effects survive beyond the public leaderboard.

**Own Training**

Use local infrastructure and collected datasets for original feature engineering, model training, and systematic evaluation.

**Private Generalization**

Prioritize improvements supported by our own validation rather than public leaderboard movement alone.

Our long-term objective is not to reproduce yet another high-scoring notebook, but to understand **why it works**, identify its weaknesses, and build a more robust system of our own.

---

## Credits, Datasets & Provenance

The direct source of Version 18 is [Dmitrii Gluzdov](https://www.kaggle.com/dmitriigluzdov).

Important additional contributors and sources:

[canqiang — E006](https://www.kaggle.com/code/canqiang/casmi26-e006-window-40-ice-fallback-true) · [Ahmed Berat Özer — v7c](https://www.kaggle.com/code/ahmedberatozer/casmi26-v7c-e006-fraggap) · [flexonafft](https://www.kaggle.com/code/flexonafft/casmi26-public-baseline-adaptation-experiments) · [samanyu1808](https://www.kaggle.com/code/samanyu1808/casmi26-iceberg-where-glacier-is-blind-lb-0-438) · [antriksharya — Rank-2 Insertion](https://www.kaggle.com/code/antriksharya/casmi26-lb-0-443-v7c-engine-2-rank-2-insert) · [prvsiyan](https://www.kaggle.com/code/prvsiyan/analog-propagation-casmi-2026-baseline) · [megayak](https://www.kaggle.com/code/megayak/casmi26-two-rankers-one-engine) · [ms-pred](https://github.com/coleygroup/ms-pred).

Author-provided Kaggle datasets:

[Attributed v4g Assets](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets) · [PubChem Popularity](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-pubchem-popularity-prior) · [Natural-Product Panel](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-natural-product-panel-benchmark) · [Fold-Safe FPNet](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-fold-safe-fpnet) · [Natural-Product Knowledge](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-natural-product-knowledge-table).

Original credits, attribution, and third-party licensing conditions are preserved.

**Our contribution to Version 27:** reproducible notebook organization, selection of essential executable cells, research-oriented presentation, and transparent documentation of the solution's lineage.

---

## 🔍 The Next Case

> We have learned how to discover strong public solutions and reproduce them reliably.
>
> The next step is to uncover patterns that other competitors have not yet recognized.
>
> **We have the fingerprints. We have the tools. Now we must learn to think like molecular detectives.**

**The investigation continues.** 🕵️