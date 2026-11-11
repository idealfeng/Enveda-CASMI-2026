## 6. Run it yourself

Join the competition, then Copy & Edit this notebook (the competition data and the datasets in the credits stay
attached). Keep the accelerator on GPU T4 and internet off. Run All in the editor is a smoke test: it ranks 12
visible molecules and gives no score. For a score, Save Version (our commit runs took 21-30 minutes on a T4), then
submit that version; the scoring rerun on the hidden test takes hours.

| switch | this notebook | what it does |
|---|---|---|
| `VARIANT`, `CUSTOM` | `CUSTOM`, w_top 0.25, w_mid 0.75 | the leader-safe weights; `V2` is the 0.25 / 0.50 recipe |
| `PHYSICAL` | `True` | Roman Tamrazov's fragment check |
| `PROVENANCE` | `False` | his provenance-aware reranker |
| `FRAG_ON_V2` | `True` | keep the fragment check's leader moves from the V2 order on top of the 0.75 order; False leaves the check's own V2 output |
| `COMMIT_MODE` | `'smoke'` | the commit run ranks 12 visible molecules; the scoring rerun ranks all |

Our string patches to his code, each asserted by our builder to apply exactly once:

1. Configuration cell: `VARIANT = 'CUSTOM'`, the CUSTOM weights, and the `PHYSICAL`, `PROVENANCE` and `FRAG_ON_V2`
   switches.
2. Fragment-check source (hidden): unchanged. It reads the V2 file, as upstream does.
3. Run cell (`BUNDLE = materialise_sources()`): it accepts the configured variant instead of only V2, and in a fast
   commit it writes the sample file and stops.
4. Fragment-check cell and provenance cell: an `if not PHYSICAL` and an `if not PROVENANCE` gate.
5. Our merge cell, after the provenance cell: per molecule, if the fragment check moved the V2 leader, the answer is
   [its new leader, the V2 leader] followed by the 0.75 order; otherwise the 0.75 order unchanged. It applies only
   when V2 and the 0.75 order share the leader and the fragment check's output holds the same candidates as the 0.75
   order; a list where the check also put an outside candidate at rank 25 keeps the 0.75 order without its leader
   move. Any error restores the 0.75 order.