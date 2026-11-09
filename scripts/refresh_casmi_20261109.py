"""Read only live CASMI result, allowance and previous batch snapshot."""
from contextlib import redirect_stdout, redirect_stderr
import io,json,logging,os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
for k,v in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
    os.environ[k]=str(ROOT/v)
from kaggle_first_submission import make_api,now,safe_error
import kaggle_batch as batch
from watch_kaggle_batch_20261107 import snapshot

def main():
    api=make_api()
    limits=api.competition_get_submission_limits(batch.COMPETITION)
    manifest=batch.load_manifest(ROOT/'submission/optimization_20261108/manifest.json')
    result=snapshot(manifest,poller=lambda m,b:batch.poll_submission(m,b,api=api))
    result.update(allowance={k:getattr(limits,k,None) for k in ('num_today','num_total','num_allowed_now')})
    out=ROOT/'reports/optimization_20261109';out.mkdir(exist_ok=True)
    batch.save(out/'initial_live_status.json',result)
    batch.save(ROOT/'reports/optimization_20261108/latest_status.json',dict(status='refreshed_read_only',**result))
    return result

if __name__=='__main__':
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):result=main()
        print(json.dumps(result,indent=2))
    except Exception as error:
        print(json.dumps(dict(status='read_failed',**safe_error(error))));raise SystemExit(1)
