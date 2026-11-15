# ── Configuration ─────────────────────────────────────────────────────────────────────────
VARIANT = 'CUSTOM'
#   V0  baseline 0.465 answers, no neural term
#   V1  public 0.466 recipe: neural reciprocal-rank fusion, weight 0.25 everywhere
#   V2  leader-safe consensus: rank 1 as V1, ranks 2-25 at neural weight 0.50   (upstream default)
#   V3  V2 + tail rescue: outside candidates may take the last 3 places by neural score
#   V4  bold consensus: rank 1 as V1, ranks 2-25 at neural weight 1.00
#   'CUSTOM' uses the verified 0.477 optimal weights (w_top=0.25, w_mid=0.75, rescue=0)
CUSTOM = dict(w_top=0.25, w_mid=0.75, rescue=0)
RRF_OFFSET = 3.0              # k in 1/(k + rank), as in the public recipe
COMMIT_MODE = 'fast'         # 'smoke': commit run validates 12 visible molecules and asserts all stages;
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
# ── Calibrated Documentation & Natural Product Prior (Guhongbin / Alex Chilton SOTA 0.487) ──
POP_W, SPEC_W, NP_W = 0.12, 0.12, 0.12
LIB_HIT_GATE = 0.78
NP_PROMO_MARGIN = 0.040
PIN_OLD_LEADER = True
OUTSIDER_FILL = True
# ── v8 (romanrozen) ──
V8 = 'BOTH'                   # 'BOTH': timsTOF mass prior ON + Leader-Immune learned RR8 isomer reranker ON
assert V8 in ('MASS', 'RR', 'BOTH', 'BASE'), V8
MASS_ON = V8 in ('MASS', 'BOTH')
RR8 = V8 in ('RR', 'BOTH')
MASS_CENTER, MASS_FREE, MASS_FULL, MASS_W = -1.5, 3.0, 8.0, 0.15   # ppm of (exact - neutral)/neutral; above NP_W
MASS_LEAD_OFF, MASS_LIB_TAU = 5.0, 0.9                              # rank-1 rule: leader beyond 5 ppm, library < 0.9
RR8_ALPHA = 0.20               # optimal conservative isomer reranker weight against list's own order
RR8_LIB_TAU = 0.9
RR8_BUDGET_SECONDS = 1800
RR8_LIMIT_SECONDS = 9 * 3600 - 1800   # never start a step past 8.5 h of session time
RR8_MIN_SECONDS = 600
MASS_PEN, MASS_PPM = {}, {}   # filled by the v8 mass cell: {molecule_id: {smiles: penalty <= 0}}, {..: {smiles: ppm}}
