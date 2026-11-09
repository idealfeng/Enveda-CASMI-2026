# ── Configuration ─────────────────────────────────────────────────────────────────────────────
VARIANT = 'CUSTOM'
#   V0  baseline 0.465 answers, no neural term
#   V1  public 0.466 recipe: neural reciprocal-rank fusion, weight 0.25 everywhere
#   V2  leader-safe consensus: rank 1 as V1, ranks 2-25 at neural weight 0.50   (upstream default)
#   V3  V2 + tail rescue: outside candidates may take the last 3 places by neural score
#   V4  bold consensus: rank 1 as V1, ranks 2-25 at neural weight 1.00
#   'CUSTOM' uses the weights below (w_top=0 keeps the pipeline's own rank 1)
CUSTOM = dict(w_top=0.25, w_mid=0.75, rescue=0)

RRF_OFFSET = 3.0              # k in 1/(k + rank), as in the public recipe
COMMIT_MODE = 'smoke'         # 'smoke': the commit run ranks 12 visible molecules and draws every figure
                              # 'fast' : the commit run skips the pipeline (saves ~30 GPU minutes);
                              #          the scoring rerun on the hidden test always runs in full
OUTSIDERS_PER_MOLECULE = 20   # candidate pool for the tail rescue (V3, or CUSTOM with rescue > 0)
TIME_GUARD_HOURS = 7.5        # optional stages are skipped once the session has run this long
QUIET_LOGS = True             # one line per pipeline stage here; full logs stay in /kaggle/working/*.log
ENABLE_TAIL_SLOT = True
PHYSICAL_POST_SECONDS = 1500

# This notebook: CUSTOM, rank 1 at neural weight 0.25, ranks 2-25 at 0.75. PHYSICAL switches the fragment check,
# PROVENANCE the provenance reranker; neural model: Saner Turhaner v1.
PHYSICAL = True
PROVENANCE = False
# variant M: the fragment check reads variants/submission_V2.csv (cell 5 as upstream, the input of Spectral Parallax V17);
# the merge cell after the provenance cell keeps only its rank-1 moves, on the CUSTOM order
FRAG_ON_V2 = True   # False leaves submission.csv as the fragment check wrote it (V2 order)

# ── Final layer (this notebook) ───────────────────────────────────────────────────────────────
# Runs after the m1 merge. Rank 1 is never touched. If the leader differs from the CUSTOM leader, the CUSTOM leader
# is pinned at rank 2 (as m1 does). Ranks 2-25 are re-sorted by the CUSTOM consensus score plus a small
# documentation prior (MIDX weights), then metric-identity duplicates are dropped and freed slots are filled with
# scored outside candidates that carry a new metric identity. No raw-SMILES fallback that could re-add duplicates.
FINAL_LAYER = True
POP_W, SPEC_W, NP_W = 0.10, 0.05, 0.02
LIB_HIT_GATE = 0.87
OUTSIDER_FILL = True
NEURAL_ENSEMBLE = True        # ranks 2-25: average of z-scored v1 and long-model neural scores
ENSEMBLE_W = 0.5             # weight of the long model in that average
DISAGREEMENT_RESCUE = False   # Roman Tamrazov's ion + neutral-loss rescue of leader moves m1 rejected
