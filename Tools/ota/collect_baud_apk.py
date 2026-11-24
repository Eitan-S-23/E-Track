"""Resume immutable development artifacts without another CI dispatch."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b = load("baud_collect_common", Path(__file__).with_name("baud_sweep.py"))
d = load("baud_collect_ranges", b.ROOT / ".cache/p3-4-screening-20260922/download.py")
SHA = "4f206cfa9f619b336fe1ecda95df19bcec52e664"
RUN = 35734099702
CHUNK = 256 * 1024
MAX_SECONDS = 1200


class ArtifactLocation:
    def __init__(self, artifact_id, token):
        self.artifact_id, self.token = artifact_id, token
        self.lock, self.location, self.expiry = threading.Lock(), None, 0

    def get(self, force=False):
        with self.lock:
            if force or time.monotonic() >= self.expiry:
                # A cached redirect can outlive its signed blob URL.
                url = "https://api.github.com/repos/" + b.REPO + "/actions/artifacts/%d/zip?resume=%d" % (self.artifact_id, time.time_ns())
                request = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token,
                    "User-Agent": "E-Track-P34-artifact", "Cache-Control": "no-cache"})
                try:
                    with d.r.opener("proxy", redirects=False).open(request, timeout=40):
                        raise RuntimeError("artifact API must redirect")
                except urllib.error.HTTPError as error:
                    b.require(error.code == 302, "artifact API HTTP %d" % error.code)
                    location = error.headers["Location"]
                parsed = urllib.parse.urlsplit(location)
                b.require(parsed.scheme == "https" and not parsed.username and not parsed.password and
                          (parsed.hostname or "").endswith((".blob.core.windows.net", ".githubusercontent.com")),
                          "unexpected artifact download host")
                self.location, self.expiry = location, time.monotonic() + 120
            return self.location


def curl_segment(base, provider, first, last, size, deadline, route):
    env = dict(os.environ)
    for attempt in (1, 2):
        path = b.checked(base / "chunks" / ("%09d-attempt-%d.bin" % (first, attempt)))
        header = b.checked(path.with_suffix(".headers"))
        receipt = b.checked(path.with_suffix(".json"))
        b.require(not any(item.exists() for item in (path, header, receipt)), "preserve native range attempts")
        path.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        if started >= deadline:
            raise TimeoutError("artifact deadline")
        location = provider.get(force=attempt == 2)
        args = [r"C:\Windows\System32\curl.exe", "--disable", "--config", "-", "--silent", "--show-error",
            "--connect-timeout", "15", "--max-time", str(max(1, min(110, int(deadline - started)))),
            "--retry", "0", "--range", "%d-%d" % (first, last), "--output", str(path),
            "--dump-header", str(header), "--write-out", "%{http_code} %{size_download}"]
        args += ["--proxy", "http://127.0.0.1:7897"] if route == "proxy" else ["--noproxy", "*"]
        process = subprocess.run(args, input=('url = "' + location + '"\n').encode(), cwd=b.ROOT,
            env=env, capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        fields = process.stdout.decode("ascii", "replace").strip().split()
        body = b.record(path) if path.exists() else None
        import re
        raw_header = header.read_text(encoding="ascii", errors="replace") if header.exists() else ""
        ranges = re.findall(r"(?im)^Content-Range:\s*bytes (\d+)-(\d+)/(\d+)\s*$", raw_header)
        lengths = re.findall(r"(?im)^Content-Length:\s*(\d+)\s*$", raw_header)
        encodings = re.findall(r"(?im)^Content-Encoding:\s*(\S+)\s*$", raw_header)
        valid = process.returncode == 0 and fields == ["206", str(last - first + 1)] and body is not None and \
            body["bytes"] == last - first + 1 and ranges == [(str(first), str(last), str(size))] and \
            lengths[-1:] == [str(last - first + 1)] and all(value.lower() == "identity" for value in encodings)
        value = dict(start=first, end=last, total=size, attempt=attempt, seconds=time.monotonic() - started,
            result="RANGE_VERIFIED" if valid else "RANGE_FAILED", file=body, exit=process.returncode,
            http_status=fields[0] if fields else None, native_headers=b.record(header) if header.exists() else None)
        b.io.write_json(b.ROOT, receipt, value)
        if valid:
            return value
        if attempt == 2 or time.monotonic() >= deadline:
            raise RuntimeError("native range incomplete; original response retained")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_receipt(artifact, value):
    b.require(value["id"] == artifact["id"] and value["name"] == artifact["name"],
              "artifact receipt identity changed")
    archive = b.record(value["archive"]["path"])
    b.require(archive == value["archive"] and archive["bytes"] == artifact["size_in_bytes"] and
              artifact["digest"] == "sha256:" + archive["sha256"], "archive changed")
    b.require(all(b.record(item["path"]) == item for item in value["files"]), "extracted artifact changed")
    return value


def verified_parts(directories, size):
    found = {}
    for directory in directories:
        for path in sorted((directory / "chunks").glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("result") != "RANGE_VERIFIED":
                continue
            first, last = value["start"], value["end"]
            b.require(type(first) is int and type(last) is int and 0 <= first <= last < size and
                      value["total"] == size, "verified range identity changed")
            item = value["file"]
            b.require(b.record(item["path"]) == item and item["bytes"] == last - first + 1,
                      "verified range bytes changed")
            previous = found.get((first, last))
            b.require(previous is None or previous["file"]["sha256"] == item["sha256"],
                      "conflicting verified ranges")
            found[first, last] = value
    return sorted(found.values(), key=lambda item: item["start"])


def missing_ranges(size, parts, chunk=CHUNK):
    b.require(type(size) is int and 0 < size <= 300 * 1024 * 1024 and
              type(chunk) is int and 0 < chunk <= 2 * 1024 * 1024, "range bounds")
    missing, position = [], 0
    for item in [*parts, dict(start=size, end=size)]:
        first, last = item["start"], item["end"]
        b.require(type(first) is int and type(last) is int and position <= first <= last <= size,
                  "overlapping or unsorted verified ranges")
        missing.extend((start, min(start + chunk, first) - 1) for start in range(position, first, chunk))
        position = last + 1
    return missing


def segment(base, location, first, last, size, deadline, route):
    for attempt in (1, 2):
        path = b.checked(base / "chunks" / ("%09d-attempt-%d.bin" % (first, attempt)))
        receipt = b.checked(path.with_suffix(".json"))
        b.require(not path.exists() and not receipt.exists(), "preserve existing range attempts")
        path.parent.mkdir(parents=True, exist_ok=True)
        started, count = time.monotonic(), 0
        try:
            b.require(started < deadline, "artifact deadline exhausted")
            request = urllib.request.Request(location, headers={"User-Agent": "E-Track-P34-resumable",
                "Range": "bytes=%d-%d" % (first, last), "Accept-Encoding": "identity"})
            with d.r.opener(route).open(request, timeout=30) as response, path.open("xb") as stream:
                d.validate_range(response, first, last, size)
                while count <= last - first:
                    if time.monotonic() >= min(deadline, started + 100):
                        raise TimeoutError("bounded range deadline")
                    data = response.read1(min(65536, last - first + 1 - count))
                    if not data:
                        break
                    stream.write(data)
                    count += len(data)
                stream.flush()
                os.fsync(stream.fileno())
            b.require(count == last - first + 1, "short range body")
            value = dict(start=first, end=last, total=size, attempt=attempt,
                         seconds=time.monotonic() - started, result="RANGE_VERIFIED", file=b.record(path))
            b.io.write_json(b.ROOT, receipt, value)
            return value
        except Exception as error:
            b.io.write_json(b.ROOT, receipt, dict(start=first, end=last, total=size, attempt=attempt,
                bytes=count, seconds=time.monotonic() - started, result="RANGE_FAILED", **d.r.error_summary(error)))
            if attempt == 2 or not d.retryable(error) or time.monotonic() >= deadline:
                raise
            time.sleep(1)


def fetch(artifact, credential, recovery, requested_route="auto", transport="urllib"):
    size = artifact["size_in_bytes"]
    roots = [b.OUT / "downloads", *sorted(b.OUT.glob("download-recovery-*"))]
    previous = [root / "artifacts" / str(artifact["id"]) for root in roots if root != recovery]
    for directory in previous:
        path = directory / "receipt.json"
        if path.is_file():
            return validate_receipt(artifact, json.loads(path.read_text(encoding="utf-8")))
    parts = verified_parts(previous, size)
    missing = missing_ranges(size, parts)
    base = b.checked(recovery / "artifacts" / str(artifact["id"]))
    b.require(not base.exists(), "this attempt already exists; reconcile instead of overwriting")
    for name in ("started.json", "failure.json", "receipt.json", "artifact.zip", "contents", "chunks"):
        b.checked(base / name)
    for first, _ in missing:
        for attempt in (1, 2):
            for suffix in (".bin", ".json", ".headers"):
                b.checked(base / "chunks" / ("%09d-attempt-%d" % (first, attempt) + suffix))
    provider = ArtifactLocation(artifact["id"], credential)
    location = provider.get()
    route, probes = "proxy", []
    for candidate in (("direct", "proxy") if requested_route == "auto" else (requested_route,)):
        started = time.monotonic()
        try:
            end = min(16384, size) - 1
            request = urllib.request.Request(location, headers={"Range": "bytes=0-%d" % end,
                "Accept-Encoding": "identity", "User-Agent": "E-Track-P34-route"})
            with d.r.opener(candidate).open(request, timeout=8) as response:
                d.validate_range(response, 0, end, size)
                prefix = response.read(end + 1)
                b.require(len(prefix) == end + 1, "short route probe")
            probes.append(dict(route=candidate, seconds=time.monotonic() - started, bytes=len(prefix)))
            route = candidate
            break
        except Exception as error:
            probes.append(dict(route=candidate, seconds=time.monotonic() - started, **d.r.error_summary(error)))
    started = time.monotonic()
    b.io.write_json(b.ROOT, base / "started.json", dict(time=b.now(), artifact_id=artifact["id"],
        size=size, reused=[item["file"] for item in parts], missing_chunks=len(missing), chunk_bytes=CHUNK,
        workers=8, max_seconds=MAX_SECONDS, route=route, transport=transport, probes=probes, source=b.record(Path(__file__))))
    print("DOWNLOAD_RESUME", artifact["id"], "reused", len(parts), "missing", len(missing), route, flush=True)
    pool = ThreadPoolExecutor(max_workers=8)
    futures, failures = [], []
    try:
        worker = curl_segment if transport == "curl" else segment
        endpoint = provider if transport == "curl" else location
        futures = [pool.submit(worker, base, endpoint, first, last, size, started + MAX_SECONDS, route)
                   for first, last in missing]
        for index, future in enumerate(as_completed(futures), 1):
            try:
                parts.append(future.result())
            except Exception as error:
                failures.append(d.r.error_summary(error))
            if index % 8 == 0 or index == len(missing):
                print("DOWNLOAD_PROGRESS", artifact["id"], index, "/", len(missing),
                      "failed", len(failures), flush=True)
        pool.shutdown(wait=True)
        b.require(not failures, "some ranges failed; completed verified ranges remain reusable")
        parts.sort(key=lambda item: item["start"])
        b.require(not missing_ranges(size, parts), "assembled coverage incomplete")
        archive = b.checked(base / "artifact.zip")
        with archive.open("xb") as writer:
            for part in parts:
                b.require(b.record(part["file"]["path"]) == part["file"], "range changed during download")
                with Path(part["file"]["path"]).open("rb") as reader:
                    shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fsync(writer.fileno())
        actual = b.record(archive)
        b.require(actual["bytes"] == size and artifact["digest"] == "sha256:" + actual["sha256"],
                  "complete artifact digest mismatch")
        files = d.extract(archive, base)
        value = dict(id=artifact["id"], name=artifact["name"], archive=actual, files=files,
                     seconds=time.monotonic() - started, download_route=route + "-resumed-ranges", chunks=parts)
        b.io.write_json(b.ROOT, base / "receipt.json", value)
        print("ARTIFACT_VERIFIED", artifact["id"], actual["sha256"], flush=True)
        return value
    except Exception as error:
        for future in futures:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
        b.io.write_json(b.ROOT, base / "failure.json", dict(time=b.now(), **d.r.error_summary(error),
            completed_chunks=len(parts), partial_preserved=True))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--route", choices=("auto", "direct", "proxy"), default="auto")
    parser.add_argument("--transport", choices=("urllib", "curl"), default="urllib")
    args = parser.parse_args()
    b.require(Path.cwd().resolve() == b.ROOT and sys.flags.isolated and sys.flags.no_site and
              sys.dont_write_bytecode, "isolated explicit root execution required")
    recovery = b.checked(b.OUT / ("download-recovery-%03d" % args.attempt))
    b.require(not recovery.exists() and not (b.OUT / "apk.json").exists(), "preserve completed/failed collection")
    for path in (b.OUT / "apk.json", recovery / "result.json"):
        b.checked(path)
    os.environ.update(b.environment())
    token = b.credential()
    run = b.api("/repos/" + b.REPO + "/actions/runs/" + str(RUN), token)[1]
    b.require(run["head_sha"] == SHA and run["conclusion"] == "success" and
              run["event"] == "workflow_dispatch" and run["head_branch"] == b.BRANCH,
              "development CI binding changed")
    expected = b.read("ci-artifacts.json")
    listing = b.api("/repos/" + b.REPO + "/actions/runs/%d/artifacts?per_page=100" % RUN, token)[1]["artifacts"]
    selected = []
    for old in expected["artifacts"]:
        matches = [item for item in listing if item["id"] == old["id"]]
        b.require(len(matches) == 1 and not matches[0]["expired"] and
                  all(matches[0][key] == old[key] for key in ("id", "name", "size_in_bytes", "digest", "workflow_run")),
                  "artifact unavailable or identity changed")
        selected.append(matches[0])
    files = [Path(item["path"]) for artifact in sorted(selected, key=lambda item: item["size_in_bytes"])
             for item in fetch(artifact, token, recovery, args.route, args.transport)["files"]]
    reports = [path for path in files if path.name == "result.json"]
    b.require(len(reports) == 2, "both original host reports required")
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        b.require(report["development_result"] == "PASS" and report["scope"] == "all" and
                  report["source_before"]["head"] == SHA and report["source_before"]["clean"],
                  "host result binding failed")
        print("HOST_REPORT", report["host"], json.dumps(report.get("console_summary", {})), flush=True)
    apks = [path for path in files if path.name == "trace-dev-debug.apk"]
    b.require(len(apks) == 1, "one debug APK required")
    apk = apks[0]
    meta = json.loads(apk.with_suffix(".json").read_text(encoding="utf-8"))
    b.require(meta["commit"] == SHA and meta["application_id"] == "com.wen.gaia.gaia.p34baud" and
              meta["release_signing"] is False and meta["sha256"] == b.record(apk)["sha256"] and
              meta["requested_ota_link_candidate"] == dict(name="runtime", runtime_config=True),
              "APK metadata/hash binding failed")
    value = dict(time=b.now(), sha=SHA, run=RUN, url=run["html_url"], apk=b.record(apk), metadata=meta,
                 host_reports=[b.record(path) for path in reports], installed=False, independent_acceptance=False)
    b.save("apk.json", value)
    b.io.write_json(b.ROOT, recovery / "result.json", dict(result="APK_VERIFIED", apk=value["apk"],
        original_failed_download_preserved=True, device_commands=0, ci_dispatches=0))
    print("APK_VERIFIED", value["apk"]["sha256"], apk, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("COLLECTION_FAILED", json.dumps(d.r.error_summary(error)),
              str(error) if isinstance(error, RuntimeError) else "see immutable attempt receipts", flush=True)
        raise SystemExit(1)
