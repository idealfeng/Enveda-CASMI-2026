"""Read current fixed submission results and redacted failure text; no cloud writes."""
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import logging
import re
import os

import kaggle_batch as batch
from kagglesdk.competitions.types.competition_api_service import ApiGetSubmissionRequest


def main():
    manifest = batch.load_manifest('submission/optimization_20261112/manifest_recovered.json')
    root = batch.ROOT / manifest['state_root']
    api = batch.make_api()
    rows = []
    for branch in manifest['branches']:
        try:
            score = batch.poll_submission(manifest, branch, api=api)
            if score['error_description_present']:
                req = ApiGetSubmissionRequest()
                req.ref = score['submission_ref']
                with api.build_kaggle_client() as client:
                    item = client.competitions.competition_api_client.get_submission(req)
                failure = dict(ref=item.ref, status=item.status.name, public_score=item.public_score,
                    error_description=re.sub(r'https?://\S+', '[URL omitted]', str(item.error_description)),
                    checked_at_utc=batch.now(), read_only=True)
                batch.save(root / 'generation_hidden_failure_details.json', failure)
                score['error_description'] = failure['error_description']
            rows.append(dict(branch=branch['name'], **score))
        except Exception as error:
            rows.append(dict(branch=branch['name'], status='read_failed', **batch.safe_error(error)))
    try:
        limits = api.competition_get_submission_limits(batch.COMPETITION)
        allowance = dict(num_today=limits.num_today, num_total=limits.num_total, num_allowed_now=limits.num_allowed_now)
    except Exception as error:
        allowance = dict(status='read_failed', **batch.safe_error(error))
    result = dict(checked_at_utc=batch.now(), read_only=True, new_submission_performed=False,
                  branches=rows, limits=allowance)
    batch.save(root / 'review_live_results.json', result)
    return result


if __name__ == '__main__':
    for key, rel in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'), ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        os.environ[key] = str(batch.ROOT / rel)
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = main()
        print(json.dumps(result, indent=2))
    except Exception as error:
        print(json.dumps(dict(status='read_failed', **batch.safe_error(error))))
        raise SystemExit(1)
