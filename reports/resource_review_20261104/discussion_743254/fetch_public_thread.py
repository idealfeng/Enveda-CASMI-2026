"""Fetch small public Kaggle discussion evidence only; no model/data downloads."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
URLS = {
    "page_lower": "https://www.kaggle.com/competitions/enveda-casmi26-molecule-id-mass-spectra/discussion/743254",
    "api_comments": "https://www.kaggle.com/api/v1/discussions/743254/comments",
    "api_internal_no_www": "https://kaggle.com/api/i/discussions.DiscussionsService/GetForumTopicById?forumTopicId=743254&includeComments=true",
}

def fetch(item):
    name, url = item
    record = {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/html;q=0.9"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(3_000_001)
            if len(payload) > 3_000_000:
                raise ValueError("Response exceeds small-text evidence limit")
            record.update(status=response.status, content_type=response.headers.get("Content-Type"), bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            (ROOT / (name + ".response")).write_bytes(payload)
    except Exception as error:
        record.update(error=repr(error))
    (ROOT / (name + ".receipt.json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(fetch, URLS.items()):
            print(json.dumps(result))
