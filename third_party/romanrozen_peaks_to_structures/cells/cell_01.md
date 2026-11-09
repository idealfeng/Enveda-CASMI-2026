# CASMI26 LB 0.480 | Neural Ensemble

**This version runs [bgunshui's *CASMI26 480 neural ensemble*](https://www.kaggle.com/code/bgunshui/casmi26-480-neural-ensemble) verbatim.**
It scored **0.480** on our account (2026-11-01), against 0.479 for our previous version (Baidalin Adilzhan's midx exact dedup fill).

What it adds on top of the 0.479 midx notebook:
- a second spectrum-to-structure model, trained by bgunshui's public kernel [`casmi26-scorer-train-public`](https://www.kaggle.com/code/bgunshui/casmi26-scorer-train-public) and attached here as a kernel source;
- ranks 2-25 are ordered by `0.5*z(public neural) + 0.5*z(retrained neural)`, z-scored per molecule; rank 1 keeps the leader-safe decision.

That work is bgunshui's, built on Baidalin Adilzhan's midx notebook, Kunal Desale's MID notebook, busyaprime's merge and the authors credited further down.
Everything from the next section down is their notebook, unchanged, so "we" and "our" below mean its authors.
Every dataset and kernel it reads is public. The commit run takes its own smoke path (about 26 GPU minutes); the scoring rerun on the hidden test runs in full.

**Board results on our account, one notebook per row:**

| notebook | public LB |
|---|---|
| romanrozen V2, verbatim | 0.468 |
| our 0.472 version: `w_mid` 0.75 | 0.472 |
| Spectral Parallax (romantamrazov), verbatim | 0.472 |
| heliosli *Happy to make the dataset public*, verbatim (page 0.478) | 0.468 |
| busyaprime merge | 0.477 |
| Kunal Desale *Enveda CASMI 2026 - MID*, verbatim (page 0.478) | 0.476 |
| Baidalin Adilzhan midx exact dedup fill (our previous version) | 0.479 |
| **bgunshui 480 neural ensemble (this version)** | **0.480** |

The same code can score about 0.002 apart from one run to the next: the pipeline skips optional stages when its time guards trip, so the score depends on the speed of the machine that reruns it.
