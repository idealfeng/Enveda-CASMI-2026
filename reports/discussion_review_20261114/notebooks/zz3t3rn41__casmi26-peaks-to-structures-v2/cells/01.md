## What we tried that did not work

Every row below is a single knob changed against one scored base.
Board scores come straight from `kaggle competitions submissions` on this competition.
Rows marked offline come from a labelled offline panel or paired-ranking metric, because no board submission answered them.
An offline number is not a board number; read it only as a hint.

| Change | Base board score | Result (board, or offline as labelled) |
|---|---|---|
| Rerun romanrozen V2 verbatim (`w_mid` 0.50), commit-mode only | 0.468 | 0.468 |
| `w_mid` 0.50 -> 0.75 on ranks 2-25 only (this notebook's own change) | 0.468 | 0.472 |
| `w_mid` 0.50 -> 1.00 on ranks 2-25 only (VARIANT V4) | 0.468 | 0.470 |
| `w_mid` 0.50 plus a 3-slot tail rescue (VARIANT V3) | 0.468 | 0.468, no change |
| `RRF_OFFSET` 3 -> 1 on rank 1 | 0.468 | 0.466 |
| Heliosli 'Happy to make the dataset public' run verbatim on our account (page 0.478) | 0.478 (page) | 0.468 on our board |
| `GL_LAM` 1.0 -> 1.5 in the frozen baseline | 0.467 | 0.447 |
| Retrain our own FPNet / fe_D on our own trainer, 7 separate swaps (offline: +26.5% better Tanimoto than the public net) | 0.456 | 0.418-0.443 on the board, every one of the 7 swaps lost; offline paired-ranking MRR also lost, -0.09 to -0.10 (offline) |
| Kunal Desale 'Enveda CASMI 2026 - MID' run verbatim on our account (page 0.478) | 0.478 (page) | 0.476 on our board |
| busyaprime m1: `w_top` 0.25 -> 0.15 (CUSTOM, rank 1) | 0.477 | 0.477, no change |
| busyaprime m1: `w_mid` 0.75 -> 0.875 (CUSTOM, ranks 2-25) | 0.477 | 0.473 |
| busyaprime m1: CUSTOM rescue 0 -> 3 (the merge skips molecules where rescue changes the set) | 0.477 | 0.471 |
| Spectral Parallax: control V2 -> CUSTOM `w_mid` 0.75 | 0.472 | 0.472, no change |
| Test-set molecular-network propagation rerank, neighbour weight 0.25 | 0.9706 (offline, panel MRR) | 0.9674 (offline, panel MRR, -0.0033) |
| FIORA-OS negative-mode forward-model blend, weight 0.25 | 0.9583 (offline, panel MRR) | 0.9444 (offline, panel MRR, -0.0139) |

Offline intrinsic metrics often mispredicted the board.
Our own retrained FPNet scored 26.5% better than the public net on raw Tanimoto similarity, offline, and still lost on every one of the 7 board swaps above.
Only the `w_mid` weight on ranks 2-25 moved the board up; the tail-rescue, RRF-offset and GL_LAM knobs either did nothing or cost score.
On the 0.477 base (busyaprime m1, 2026-10-30) the same knobs are flat or worse: `w_mid` 0.75 is already the best of 0.50, 0.75, 0.875 and 1.00, a lower rank-1 weight changes nothing at three decimals, and a 3-slot rescue costs 0.006.