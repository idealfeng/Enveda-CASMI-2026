"""Fetch only public notebook source and metadata; never execute notebook code."""
from pathlib import Path
import datetime
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parent
URL = "https://www.kaggle.com/api/v1/kernels/pull?userName=romanrozen&kernelSlug=0-468-casmi-from-peaks-to-structures"
request = urllib.request.Request(URL, headers={"User-Agent": "KaggleApi/1.7", "Accept": "application/json"})
with urllib.request.urlopen(request, timeout=60) as response:
    raw = response.read(20 * 1024 * 1024 + 1)
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("Source response exceeds 20 MiB limit")
    # Retain provenance without persisting anonymous session cookies or tokens.
    safe_header_names = {"content-type", "content-length", "date", "etag", "last-modified", "cache-control"}
    headers = {key: value for key, value in response.headers.items() if key.lower() in safe_header_names}
    status = response.status
data = json.loads(raw)
(ROOT / "pull_latest.json").write_bytes(raw)
receipt = dict(source_url=URL, fetched_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               status=status, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), headers=headers)
(ROOT / "download_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(metadata=data.get("metadata"), blob_keys=list(data.get("blob", {}))), ensure_ascii=True))
