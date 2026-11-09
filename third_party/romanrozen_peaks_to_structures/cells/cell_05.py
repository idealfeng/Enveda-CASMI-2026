# ── Configuration ─────────────────────────────────────────────────────────────────────────────
VARIANT = 'CUSTOM'
#   V0  baseline 0.465 answers, no neural term
#   V1  public 0.466 recipe: neural reciprocal-rank fusion, weight 0.25 everywhere
#   V2  leader-safe consensus: rank 1 as V1, ranks 2-25 at neural weight 0.50   (upstream default)
#   V3  V2 + tail rescue: outside candidates may take the last 3 places by neural score
#   V4  bold consensus: rank 1 as V1, ranks 2-25 at neural weight 1.00
#   'CUSTOM' uses the verified 0.477 optimal weights (w_top=0.25, w_mid=0.75, rescue=0)
CUSTOM = dict(w_top=0.25, w_mid=0.75, rescue=0)

RRF_OFFSET = 3.0              # k in 1/(k + rank), as in the public recipe
COMMIT_MODE = 'smoke'         # 'smoke': commit run validates 12 visible molecules and asserts all stages;
                              #          the scoring rerun on hidden test executes in full
OUTSIDERS_PER_MOLECULE = 20   # candidate pool for the tail rescue (V3, or CUSTOM with rescue > 0)
TIME_GUARD_HOURS = 7.5        # optional stages are skipped once the session has run this long
QUIET_LOGS = True             # one line per pipeline stage here; full logs stay in /kaggle/working/*.log
ENABLE_TAIL_SLOT = True
PHYSICAL_POST_SECONDS = 1500

# Physical switches the fragment check; PROVENANCE the provenance reranker; neural model: Saner Turhaner v1
PHYSICAL = True
PROVENANCE = False
# Variant M: fragment check reads variants/submission_V2.csv;
# merge cell keeps its rank-1 moves unblocked on the CUSTOM order
FRAG_ON_V2 = True
# InChIKey-14 deduplication: removes redundant stereoisomers within candidate pool
ENABLE_K14_DEDUP = True

# ── Final layer (baidalinadilzhan) ──────────────────────────────────────────────────────────────
# Documentation-prior weights on ranks 2-25 (MID: 0.10 / 0.05 / 0.02), spectral-library bonus only for molecules whose
# best library match reaches LIB_HIT_GATE, the pipeline's leader pinned at rank 2 after a fragment-check leader move,
# metric-exact deduplication (the scorer's own key) and empty slots filled with scored outside candidates.
POP_W, SPEC_W, NP_W = 0.10, 0.05, 0.02
LIB_HIT_GATE = 0.87
PIN_OLD_LEADER = True
OUTSIDER_FILL = True

# ── v4 (romanrozen): taxonomic consistency on ranks 2-25 ─────────────────────────────────────────────────────────
PRESET = 'TAX'
#   TAX    the public 0.480 answer rule + taxonomic consistency bonus on ranks 2-25 (rank 1 is never moved by it)
#   NE480  the public 0.480 answer rule exactly (the A/B control)
TAX_W = 0.05              # bonus weight, on the scale of the documentation prior (SPEC_W 0.05, NP_W 0.02)
TAX_ANCHOR_LIB = 0.87     # anchors: molecules whose best library match reaches this (as LIB_HIT_GATE)
TAX_SPECIFIC_MAX = 25     # anchors whose leader LOTUS reports from more genera carry no taxonomic information
TAX_MIN_SPECIFIC = 6      # gate: at least this many taxonomically specific anchors ...
TAX_MIN_COOCCUR = 0.25    # ... sharing genera above chance (random-set p95, computed at run time) and above this floor
TAX_SCALE = 0.5           # bonus = TAX_W * (1 - exp(-S / TAX_SCALE)), S = strongest genus mass of the candidate
assert PRESET in ('TAX', 'NE480'), PRESET
if PRESET == 'NE480':
    TAX_W = 0.0