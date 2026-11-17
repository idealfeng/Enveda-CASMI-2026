*Figure 1. Public scores as the Code tab shows them (the best over each notebook's versions), 0.40 and above. Dark:
notebooks that attach Dmitrii Gluzdov's v4g assets.*

## 2. One lineage, two branches

| step | notebook | what it changed | public LB shown |
|---|---|---|---:|
| 1 | Dmitrii Gluzdov, [The Data Behind Spectra to Structures](https://www.kaggle.com/code/dmitriigluzdov/casmi-26-the-data-behind-spectra-to-structures) | assembles and documents the shared pipeline: library search, a PubChem channel, GLACIER and ICEBERG forward models, two-engine fusion (its own credits name canqiang's E006 and Ahmed Berat Özer's engines as the base) | 0.465 |
| 2 | Saner Turhaner, [PubChem + Neural025](https://www.kaggle.com/code/sanpier/pubchem-neural025-lb-0-466) | a neural spectrum-to-structure scorer, fused by reciprocal rank at weight 0.25 | 0.466 |
| 3 | Roman Rozen, [From Peaks to Structures](https://www.kaggle.com/code/romanrozen/0-468-casmi-from-peaks-to-structures) | leader-safe consensus V2: rank 1 as in step 2, ranks 2-25 at neural weight 0.50 (Kozykorpesh's [Balanced Acquisition Evidence](https://www.kaggle.com/code/kozykappa/lb-0-468-balanced-acquisition-evidence) ran this V2 in its versions 6-7, the pipeline Spectral Parallax thanks) | 0.468 |
| 4a | alex chilton, [Leader-Safe, Ranks 2-25 at 0.75](https://www.kaggle.com/code/alexchilton/casmi26-lb-0-472-leader-safe-ranks-2-25-at-0-75) | ranks 2-25 at neural weight 0.75 | 0.472 on [a fork that changes only the commit mode](https://www.kaggle.com/code/cngnguynhuuz/casmi26-fork-lb472); his own page shows 0.467 |
| 4b | Roman Tamrazov, [Spectral Parallax](https://www.kaggle.com/code/romantamrazov/casmi-2026-spectral-parallax) | an untrained fragment check on the V2 lists | 0.472 (best of its versions; version 22, whose code runs here, shows no score of its own) |
| 5 | this notebook | 4b's leader moves from the V2 order, ranks 2-25 from 4a's 0.75 order | **0.477** |

Scores are what the Code tab displayed on 2026-10-27, Kaggle's best public score over each notebook's versions. The
current versions of some linked notebooks run something else: Roman Rozen's now stacks a private isomer reranker
(skipped when its dataset is absent), the fragment check and a tail recovery on ranks 2-25 at 1.00, and since
2026-10-28 his page shows 0.472.

The fusion rule in one line: a candidate at pipeline rank b and neural rank n scores 1/(3 + b) + w/(3 + n). Rank 1
uses w = 0.25, so the neural model can take the lead from the pipeline's leader only when that leader sits at neural
rank 18 or worse and the runner-up is the neural favourite. Ranks 2-25 use w_mid; at 0.75 the neural model sorts them
much harder than at 0.50.

**What the fragment check does.** 4b has three parts:

- **Rank 1.** When the leader's match to the reference library is below 0.87 and the molecule has at least three
  usable spectra, a candidate from ranks 2-6 with the leader's formula (an isomer the precursor mass cannot tell
  apart) can take rank 1. It must explain clearly more fragment intensity than the leader and score higher with the
  neural model, and it needs support from the engines' own top-5 lists or from the GLACIER and ICEBERG forward
  models.
- **Swaps.** Up to two adjacent swaps of same-formula candidates in ranks 2-11, with no library gate.
- **Last place.** One same-formula outside candidate may take rank 25.

**Why stacking 4a and 4b scored 0.472, and what scored 0.477.** 4a never touches rank 1, so the two changes looked
independent. Run together (our e1) they scored 0.472, the same as each alone. The rank-1 rule takes its contenders
from ranks 2-6 of the order it is handed. On the 0.75 order that window holds different candidates: on Saner
Turhaner's labelled panel, the same-formula candidates in ranks 2-6 that pass the rule's neural gates change in 17 of
86 eligible lists, each change adds a wrong structure and no right one drops out (the fragment gates need the
spectra and were not replayed). Our reading, which no single submission isolates: on the 0.75 order the rule keeps
its good leader moves and adds wrong ones. The whole fragment check (rank-1 rule, swaps and last place) on the
long-trained neural model's 0.75 order cost 0.008 (e3 0.453 against e4 0.461); that pair does not separate the rank-1
rule from the other two parts. This
notebook runs the rule on the V2 order, keeps only the leader it picks there, and places the old leader second and
the 0.75 order below them: 0.477.

The field already swept the knobs around 4a (displayed scores, knobs read from each notebook's configuration cell):
w_mid 0.70, 0.75 and 0.80 all show 0.472 ([v1220](https://www.kaggle.com/code/rajrajak99/casmi26-apex-v1220-golden-ratio-070), [fork-lb472](https://www.kaggle.com/code/cngnguynhuuz/casmi26-fork-lb472),
[v1210](https://www.kaggle.com/code/rajrajak99/casmi26-apex-v1210-sweet-spot-080)); rank-1 weight 0 shows 0.472 ([v1230](https://www.kaggle.com/code/rajrajak99/casmi26-apex-v1230-pure-shield-075)), 0.50 shows 0.448 and 1.00 shows
0.359 ([fork-wt05](https://www.kaggle.com/code/cngnguynhuuz/casmi26-fork-wt05), [fork-wt10](https://www.kaggle.com/code/cngnguynhuuz/casmi26-fork-wt10)). On the step-3 line (w_mid 0.50), offset 1 instead
of 3 shows 0.466 ([v520](https://www.kaggle.com/code/guhongbin/casmi26-v520-p2s-wmid050off1)). Moving rank 1 with the neural model is where scores are lost.