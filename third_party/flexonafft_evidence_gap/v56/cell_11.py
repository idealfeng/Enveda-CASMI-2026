BUNDLE = materialise_sources()
PIPELINE_DONE = run_public_pipeline()
if not PIPELINE_DONE and not IS_RERUN and COMMIT_MODE == 'fast':
    shutil.copyfile(COMP / 'sample_submission.csv', ROOT / 'submission.csv')
    raise SystemExit('fast commit: sample file written, the scoring rerun runs every stage')
if not PIPELINE_DONE:
    raise RuntimeError('A real baseline run is required; no placeholder-only submission')
NEURAL_OK = score_final_lists()
if not NEURAL_OK:
    raise RuntimeError('The 0.468 V2 neural checkpoint is required; refusing silent 0.465 fallback')
OUTSIDERS_OK = score_outside_candidates(needed=True)
CONSENSUS_OK, REPORT, MOVES = build_consensus()
if not CONSENSUS_OK:
    raise RuntimeError('Unable to reproduce the V2 control')
SUBMITTED = choose_and_submit()
if SUBMITTED != VARIANT:
    raise RuntimeError(f'Expected {VARIANT}, got {SUBMITTED}')
shutil.copy2(ROOT/'submission.csv', ROOT/'submission_control_V2.csv')
print('Exact V2 control:', hashlib.sha256((ROOT/'submission_control_V2.csv').read_bytes()).hexdigest()[:16])
