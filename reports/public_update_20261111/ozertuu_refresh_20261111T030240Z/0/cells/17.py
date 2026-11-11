import traceback
try:
    import importlib.util
    spec=importlib.util.spec_from_file_location('parallax_public_provenance',PROVENANCE_CODE)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _left=max(0,int(8.65*3600-(time.time()-NB_T0)))
    if not PROVENANCE:
        PROVENANCE_REPORT={'status':'disabled in this experiment'}
    elif _left<240:
        PROVENANCE_REPORT={'status':'skipped_because_of_kaggle_runtime','seconds_remaining':_left}
    else:
        PROVENANCE_REPORT=module.run(ROOT,COMP,time_budget=min(960,_left-180))
except Exception as exc:
    traceback.print_exc()
    shutil.copy2(ROOT/'submission_physical0472_control.csv' if (ROOT/'submission_physical0472_control.csv').is_file() else ROOT/'submission_control_V2.csv',ROOT/'submission.csv')
    PROVENANCE_REPORT={'status':'restored_control_after_error','exception':repr(exc)}

final=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
assert list(final.columns)==['molecule_id','smiles']
assert final.molecule_id.tolist()==SAMPLE_IDS and final.molecule_id.is_unique
assert final.smiles.str.split(';').map(len).between(1,25).all()
assert final.smiles.str.split(';').map(lambda a: all(bool(s) for s in a) and len(set(a))==len(a)).all()
print('SUBMISSION READY:',ROOT/'submission.csv','molecules',len(final),'provenance',PROVENANCE_REPORT)
