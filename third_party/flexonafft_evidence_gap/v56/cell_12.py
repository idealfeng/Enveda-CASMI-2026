import sys, traceback
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(CODE))
from parallax_physical import apply
try:
    _remaining = max(0, int(8.55 * 3600 - (time.time() - NB_T0)))
    if not PHYSICAL:
        PARALLAX_DIAGNOSTICS = {'status': 'disabled in this experiment'}
    elif _remaining < 180:
        PARALLAX_DIAGNOSTICS = {'status':'skipped_due_to_runtime_budget','remaining_seconds':_remaining,'control_retained':True}
    else:
        PARALLAX_DIAGNOSTICS = apply(ROOT, COMP, max_seconds=min(PHYSICAL_POST_SECONDS, _remaining - 120), allow_tail=True, allow_top=True)
except Exception:
    traceback.print_exc()
    shutil.copy2(ROOT/'submission_control_V2.csv',ROOT/'submission.csv')
    PARALLAX_DIAGNOSTICS = {'error':'physical_overlay_failed', 'control_restored':True}
    (ROOT/'spectral_parallax_report.json').write_text(json.dumps(PARALLAX_DIAGNOSTICS,indent=2))
assert (ROOT/'submission.csv').is_file()
final = pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
assert final.molecule_id.tolist() == SAMPLE_IDS and final.molecule_id.is_unique
assert final.smiles.notna().all() and final.smiles.str.split(';').map(len).between(1,25).all()
assert final.smiles.str.split(';').map(lambda a: all(x.strip() for x in a)).all()
print('SUBMISSION READY:',ROOT/'submission.csv','rows',len(final),'control',SUBMITTED)
print('EXPERIMENT:', json.dumps(PARALLAX_DIAGNOSTICS))
