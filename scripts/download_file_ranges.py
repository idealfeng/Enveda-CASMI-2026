"""Resume a public file using independently verified parallel HTTP byte ranges.

Stop any other downloader writing OUTPUT/OUTPUT.part before starting this program.
Cancellation retains the contiguous .part prefix and completed range fragments.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class RangeError(RuntimeError):
    pass


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            result.update(block)
    return result.hexdigest()


def save_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextlib.contextmanager
def output_lock(path):
    """Kernel-held lock survives neither cancellation nor process death."""
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def download_range(url, total, start, end, folder, cancelled):
    segment = folder / f"{start:016d}-{end:016d}.part"
    length = end - start + 1
    if segment.exists() and segment.stat().st_size > length:
        raise RangeError(f"Oversized saved fragment for bytes {start}-{end}")

    # A cancellation while assembling can leave a prefix ending inside a completed
    # fragment. Reuse its remaining tail instead of downloading that tail again.
    if not segment.exists():
        for candidate in folder.glob("*.part"):
            match = re.fullmatch(r"(\d+)-(\d+)\.part", candidate.name)
            if match:
                old_start, old_end = map(int, match.groups())
                if old_start < start <= old_end == end and candidate.stat().st_size == old_end - old_start + 1:
                    with candidate.open("rb") as source, segment.open("wb") as target:
                        source.seek(start - old_start)
                        shutil.copyfileobj(source, target, 4 << 20)
                    break

    attempts = 0
    while not segment.exists() or segment.stat().st_size < length:
        if cancelled.is_set():
            raise concurrent.futures.CancelledError()
        saved = segment.stat().st_size if segment.exists() else 0
        request_start = start + saved
        request = urllib.request.Request(url, headers={
            "Range": f"bytes={request_start}-{end}",
            "Accept-Encoding": "identity",
            "User-Agent": "CASMI26-local-range-reproduction/1.0",
        })
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                # Never log response.geturl(): redirects can contain signed URLs.
                if response.status != 206:
                    raise RangeError(f"Expected HTTP 206 for bytes {request_start}-{end}; got {response.status}")
                header = response.headers.get("Content-Range", "")
                parsed = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", header.strip())
                if not parsed:
                    raise RangeError("Missing or invalid Content-Range")
                first, last, actual_total = map(int, parsed.groups())
                if first != request_start or not (first <= last <= end) or actual_total != total:
                    raise RangeError(f"Content-Range mismatch for requested bytes {request_start}-{end}")
                body_size = last - first + 1
                advertised = response.headers.get("Content-Length")
                if advertised is not None and int(advertised) != body_size:
                    raise RangeError("Content-Length differs from Content-Range")
                received = 0
                with segment.open("ab") as target:
                    while received < body_size:
                        if cancelled.is_set():
                            raise concurrent.futures.CancelledError()
                        try:
                            block = response.read(min(4 << 20, body_size - received))
                        except http.client.IncompleteRead as error:
                            block = error.partial
                            if len(block) > body_size - received:
                                raise RangeError("Partial response exceeds its declared byte range") from None
                            target.write(block)
                            received += len(block)
                            raise OSError("Incomplete HTTP response; saved received bytes") from None
                        if not block:
                            raise OSError("Early EOF; saved received bytes")
                        if len(block) > body_size - received:
                            raise RangeError("Response exceeds its declared byte range")
                        target.write(block)
                        received += len(block)
                if received != body_size:
                    raise RangeError("Received size differs from Content-Range")
        except urllib.error.HTTPError as error:
            if error.code in (400, 401, 403, 404, 405, 410, 416):
                raise RangeError(f"HTTP {error.code}; this status is not retried") from None
            attempts += 1
            if attempts >= 6:
                raise RangeError(f"HTTP {error.code}; retry limit reached") from None
            cancelled.wait(min(20, 2 ** attempts))
        except RangeError:
            raise
        except concurrent.futures.CancelledError:
            raise
        except (OSError, urllib.error.URLError, http.client.HTTPException, TimeoutError) as error:
            attempts += 1
            if attempts >= 6:
                raise RangeError(f"Range {start}-{end} failed after retries: {type(error).__name__}") from None
            cancelled.wait(min(20, 2 ** attempts))
    if segment.stat().st_size != length:
        raise RangeError(f"Fragment size mismatch for bytes {start}-{end}")
    return {"start": start, "end": end, "bytes": length, "path": str(segment),
            "sha256": digest(segment), "retry_count": attempts}


def run(args):
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    receipt_path = output.with_name(output.name + ".receipt.json")
    folder = output.with_name(output.name + ".ranges")
    folder.mkdir(exist_ok=True)
    # Preserve encoded file-name slashes (%2F); encode spaces/Unicode safely.
    parsed = urllib.parse.urlsplit(args.url)
    encoded_path = urllib.parse.quote(parsed.path, safe="/%:@-._~!$&'()*+,;=")
    url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, parsed.query, ""))
    if parsed.scheme not in ("https", "http"):
        raise RangeError("URL must use HTTP or HTTPS")
    started = time.monotonic()
    cancelled = threading.Event()
    receipt = {"method": "parallel_http_ranges", "url": url, "path": str(output),
               "expected_bytes": args.expected_bytes, "expected_sha256": args.sha256,
               "workers": args.workers, "chunk_mib": args.chunk_mib, "ranges": [], "state": "starting"}

    with output_lock(output.with_name(output.name + ".range.lock")):
        identity_path = folder / "source.json"
        identity = {"url": url, "bytes": args.expected_bytes}
        if identity_path.exists():
            if json.loads(identity_path.read_text(encoding="utf-8")) != identity:
                raise RangeError("Saved range fragments belong to another URL or file size")
        else:
            save_json(identity_path, identity)
        if output.is_file():
            if output.stat().st_size != args.expected_bytes:
                raise RangeError("Existing final output has the wrong size; refusing to overwrite")
            checksum = digest(output)
            if args.sha256 and checksum != args.sha256:
                raise RangeError("Existing final output SHA-256 differs from expected")
            receipt.update(state="present", bytes=args.expected_bytes, sha256=checksum)
            save_json(receipt_path, receipt)
            print(json.dumps({"state": "present", "bytes": args.expected_bytes, "sha256": checksum}), flush=True)
            return 0
        prefix = partial.stat().st_size if partial.exists() else 0
        if prefix > args.expected_bytes:
            raise RangeError("Existing contiguous .part prefix is larger than expected")
        receipt.update(state="downloading", initial_prefix_bytes=prefix, contiguous_bytes=prefix,
                       prefix_note="Existing contiguous prefix is trusted; final expected SHA-256 is checked when supplied")
        save_json(receipt_path, receipt)
        chunk_size = args.chunk_mib << 20
        ranges = []
        position = prefix
        while position < args.expected_bytes:
            end = min(((position // chunk_size) + 1) * chunk_size, args.expected_bytes) - 1
            ranges.append((position, end))
            position = end + 1
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.workers)
        futures = {executor.submit(download_range, url, args.expected_bytes, a, b, folder, cancelled): i
                   for i, (a, b) in enumerate(ranges)}
        ready = {}
        next_index = 0
        try:
            with partial.open("ab") as target:
                for future in concurrent.futures.as_completed(futures):
                    record = future.result()
                    ready[futures[future]] = record
                    receipt["ranges"].append(record)
                    while next_index in ready:
                        item = ready.pop(next_index)
                        if target.tell() != item["start"]:
                            raise RangeError("Contiguous prefix changed while assembling; another writer may be active")
                        with Path(item["path"]).open("rb") as source:
                            shutil.copyfileobj(source, target, 4 << 20)
                        target.flush()
                        receipt["contiguous_bytes"] = target.tell()
                        next_index += 1
                    receipt["elapsed_seconds"] = round(time.monotonic() - started, 2)
                    save_json(receipt_path, receipt)
                    print(json.dumps({"state": "downloading", "completed_ranges": len(receipt["ranges"]),
                                      "total_ranges": len(ranges), "contiguous_bytes": receipt["contiguous_bytes"],
                                      "expected_bytes": args.expected_bytes,
                                      "elapsed_seconds": receipt["elapsed_seconds"]}), flush=True)
            if partial.stat().st_size != args.expected_bytes:
                raise RangeError("Assembled file size differs from expected")
            checksum = digest(partial)
            if args.sha256 and checksum != args.sha256:
                raise RangeError("Assembled SHA-256 differs from expected; retained .part and fragments")
            partial.replace(output)
            receipt.update(state="complete", bytes=args.expected_bytes, sha256=checksum,
                           checksum_checked_against_expected=bool(args.sha256),
                           elapsed_seconds=round(time.monotonic() - started, 2))
            save_json(receipt_path, receipt)
            for path in folder.glob("*.part"):
                if re.fullmatch(r"\d+-\d+\.part", path.name):
                    path.unlink()
            print(json.dumps({"state": "complete", "bytes": args.expected_bytes, "sha256": checksum,
                              "elapsed_seconds": receipt["elapsed_seconds"]}), flush=True)
            return 0
        except BaseException as error:
            cancelled.set()
            receipt.update(state="cancelled" if isinstance(error, KeyboardInterrupt) else "failed",
                           contiguous_bytes=partial.stat().st_size if partial.exists() else 0,
                           error_type=type(error).__name__, error=str(error),
                           elapsed_seconds=round(time.monotonic() - started, 2))
            save_json(receipt_path, receipt)
            raise
        finally:
            cancelled.set()
            executor.shutdown(wait=True, cancel_futures=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bytes", required=True, type=int, dest="expected_bytes")
    parser.add_argument("--sha256", default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--chunk-mib", type=int, default=128)
    args = parser.parse_args()
    if min(args.expected_bytes, args.workers, args.chunk_mib) <= 0:
        parser.error("bytes, workers and chunk-mib must be positive")
    if args.sha256:
        args.sha256 = args.sha256.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", args.sha256):
            parser.error("sha256 must be 64 hexadecimal characters")
    try:
        return run(args)
    except KeyboardInterrupt:
        print(json.dumps({"state": "cancelled", "message": "Contiguous prefix and fragments retained"}), flush=True)
        return 130
    except Exception as error:
        print(json.dumps({"state": "failed", "error_type": type(error).__name__, "error": str(error)}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
