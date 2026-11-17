# ===== heliosli: time guard for the FREEZE cell on the 0.477 base =====
# This base stops its own optional stages at 8.55-8.65 h after NB_T0 (its cell 1). The FREEZE cell checks budget_s
# before each list and leaves the remaining lists in the base's order once it runs out; here budget_s = what is left
# until 8.75 h after NB_T0, at most the package's 2,400 s.
import time as _rr3_t

_rr3_left = 8.75 * 3600 - (_rr3_t.time() - globals().get('NB_T0', _rr3_t.time()))
RR3_OVERRIDE = dict(budget_s=float(max(0.0, min(2400.0, _rr3_left))))
print('[guard] FREEZE budget_s %.0f (session %.2f h)' % (RR3_OVERRIDE['budget_s'], (8.75 * 3600 - _rr3_left) / 3600))
