"""Bounded public metadata/source requests; no assets or source execution."""
from pathlib import Path
import datetime
import hashlib
import json
import urllib.request

root = Path(__file__).resolve().parent
base = "https://www.kaggle.com"
requests = {
    "pull_v8.json": base + "/api/v1/kernels/pull?userName=romanrozen&kernelSlug=0-468-casmi-from-peaks-to-structures&versionLabel=v8",
    "kernel_list.json": base + "/api/v1/kernels/list?user=romanrozen&search=0-468-casmi-from-peaks-to-structures&pageSize=20",
    "page.html": base + "/code/romanrozen/0-468-casmi-from-peaks-to-structures",
    "trainer_pull.json": base + "/api/v1/kernels/pull?userName=bgunshui&kernelSlug=casmi26-scorer-train-public",
}
receipts = []
for name, url in requests.items():
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "KaggleApi/1.7", "Accept": "application/json" if name.endswith("json") else "text/html"})
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read(20 * 1024 * 1024 + 1)
            if len(raw) > 20 * 1024 * 1024:
                raise ValueError("Response exceeds small-source size limit")
            status = response.status
            content_type = response.headers.get("Content-Type")
        (root / name).write_bytes(raw)
        receipts.append(dict(name=name, url=url, status=status, bytes=len(raw), content_type=content_type,
                             sha256=hashlib.sha256(raw).hexdigest()))
    except Exception as exc:
        receipts.append(dict(name=name, url=url, error=repr(exc)))
(root / "metadata_request_receipts.json").write_text(json.dumps(dict(
    fetched_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), requests=receipts), indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipts, indent=2))
