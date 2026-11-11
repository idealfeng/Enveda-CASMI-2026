## 3. The pipeline

The configuration and session cells at the top of this notebook and the cells below are Spectral Parallax's, in his
order. Hidden: the pinned sources (Saner Turhaner's six helper modules from the 0.466 notebooks, Roman Rozen's
`consensus.py` and `outsiders.py`, and the 0.465 pipeline embedded as base64, each checked by SHA-256), the stage
runner, and the fragment check's source. Shown: the run cell (pipeline in one process, the neural scorer on the final
lists and on up to 20 outside candidates per molecule, the leader-safe consensus), the fragment-check cell and the
provenance cell. A failing overlay restores the previous answer file; the scoring rerun refuses to submit without a
real pipeline run and a neural score.