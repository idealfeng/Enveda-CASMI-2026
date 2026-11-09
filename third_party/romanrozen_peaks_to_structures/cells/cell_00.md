# CASMI26 · v4 · Neural Ensemble + Taxonomic Consistency

**romanrozen · From Peaks to Structures, v4.** This notebook is the public *CASMI26 LB 0.480 | Neural Ensemble*
(alex chilton, running bgunshui's notebook verbatim) with one new, independent signal on ranks 2–25: the producing
organisms of the candidates. Every other cell is theirs; the changes are listed in the next cell's description.

| `PRESET` | Rank 1 | Ranks 2–25 |
|---|---|---|
| **`'TAX'`** · default | as the public 0.480 notebook | its final layer + taxonomic consistency bonus |
| `'NE480'` | as the public 0.480 notebook | its final layer, unchanged: the A/B control |

What v4 changes, each asserted by its builder to apply exactly once: a v4 block at the end of the configuration cell;
a new cell before the final layer that builds the bonus table from LOTUS genera (section *v4 · Taxonomic consistency*);
one added term in the final layer's ranks 2–25 score, which adds exactly 0.0 when the bonus is off. Outputs were
cleared and text garbled by a cp1251 round trip was repaired in comments and messages (never in the pinned sources).

Credits for v4's signal: LOTUS (natural products and their organisms, CC0) and NPAtlas via Dmitrii Gluzdov's
*casmi26-natural-product-knowledge-table*; the idea of taxonomically informed metabolite annotation is
Rutz, Dounoue-Kubo, Ollivier et al., *Front. Plant Sci.* 2019 (TIMA). Everything else: the authors credited below.