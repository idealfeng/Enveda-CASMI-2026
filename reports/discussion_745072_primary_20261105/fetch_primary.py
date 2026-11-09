"""Bounded read-only public discussion requests; no login or external messages."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REQUESTS = [
    ('public_page', 'https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/745072', None),
    ('public_comments_api', 'https://www.kaggle.com/api/v1/discussions/745072/comments', None),
    ('internal_read_rpc', 'https://www.kaggle.com/api/i/discussions.DiscussionsService/GetForumTopicById', {'forumTopicId': 745072, 'includeComments': True}),
]


def fetch(item):
    name, url, body = item
    request_body = json.dumps(body).encode() if body else None
    request = Request(url, data=request_body, headers={'User-Agent': 'Mozilla/5.0',
                      'Accept': 'application/json,text/html;q=0.9', 'Content-Type': 'application/json'})
    receipt = {'url': url, 'method': request.get_method(), 'read_only_operation': True,
               'utc': datetime.now(timezone.utc).isoformat(), 'request_body': body}
    try:
        try:
            response = urlopen(request, timeout=25)
        except HTTPError as error:
            response = error
        with response:
            data = response.read(3_000_001)
            if len(data) > 3_000_000:
                raise ValueError('Small-source limit exceeded')
            receipt.update(status=response.status, bytes=len(data), content_type=response.headers.get('Content-Type'),
                           sha256=hashlib.sha256(data).hexdigest())
        (ROOT / (name + '.response')).write_bytes(data)
    except Exception as error:
        receipt['error'] = repr(error)
    (ROOT / (name + '.receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        print(json.dumps(list(pool.map(fetch, REQUESTS)), indent=2))
