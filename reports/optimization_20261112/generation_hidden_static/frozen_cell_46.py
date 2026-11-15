'''## Final metric audit

The final pass cannot demote any existing metric-equivalent answer: it retains the first
occurrence of every valid identity in order, then appends new identities up to 25 candidates.
Runtime assertions check this for every active molecule. This guarantee applies to the
same predictions and current metric; it does not predict the score of a fresh inference run.

Outputs: `submission.csv`, `baseline_submission.csv`, `candidate_audit.csv`,
`candidate_audit.json`, and stage health in `run_manifest.json`.
'''
