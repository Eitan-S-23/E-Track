"""Controlled PATCH service regressions; loopback HTTP, no phone or OTA."""
import copy
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import urlopen
import zlib

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


svc = load("p34_patch_service", ROOT / "Tools/ota/p3-3-service/service.py")
io = load("p34_patch_io", ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
BASE = "9b3a4a21409c59b916976385ec877b7d90bd7e4c90b3553f0b8df2b02fd787dc"
TARGET = "58eebd962ba1b39369f85954a167516ec5f5e519c5d894c3db5eb0edccea76a1"


def container(kind):
    payload = b"bounded host fixture\x00" * 128
    header = bytearray(64)
    header[:4] = b"ETU1"
    struct.pack_into("<HHII", header, 4, 64, 7 if kind == "patch" else 11, 1, 1)
    struct.pack_into("<IIIIHBB", header, 32, len(payload), zlib.crc32(payload),
                     30287, 30286 if kind == "patch" else 0, 1, 1, 1)
    header[52:60] = bytes.fromhex(BASE)[:8] if kind == "patch" else bytes(8)
    struct.pack_into("<I", header, 60, zlib.crc32(header[:60]))
    return bytes(header) + payload


class PatchServiceTests(unittest.TestCase):
    def setUp(self):
        parent = io.checked_output(ROOT, ROOT / ".cache/p34-service-tests")
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def config(self, kind="patch", data=None):
        data = container(kind) if data is None else data
        path = io.checked_output(ROOT, self.out / (kind + ".etu"))
        path.write_bytes(data)
        name = "e-track-at32f435-v3.2.86-to-v3.2.87-patch.etu" if kind == "patch" else "e-track-at32f435-v3.2.87-full.etu"
        return dict(publicBaseUrl="https://fixture.invalid", token=dict(keyVersion=1,
            keyHex="11" * 32, ttlSeconds=300), channels=dict(stable="reference"),
            releases=dict(reference=dict(releaseId="p34-reference", versionName="3.2.87",
                versionCode=30287, releaseTag="mcu-e-track-at32f435-v3.2.87",
                releaseNotes="host fixture", targetImageSha256=TARGET, targetHardware="e-track-at32f435",
                minAppVersionCode=0, hardwareRevision=1, layoutId=1, minBootVersion=1,
                minProtocolVersion=1, asset=dict(assetId="reference-" + kind, kind=kind,
                    fileName=name, path=str(path), sizeBytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                    baseVersionCode=30286 if kind == "patch" else 0,
                    baseImageSha256=BASE if kind == "patch" else None))))

    def state(self, config=None):
        return svc.V2ServiceState(config or self.config(), str(ROOT), now_fn=lambda: 1800000000)

    def query(self, **changes):
        values = dict(appId="trace", deviceModel="e-track-at32f435", channel="stable",
            currentVersionCode="30286", currentImageSha=BASE, hardwareRevision="1", layoutId="1",
            bootVersion="1", protocolVersion="1", appVersionCode="86")
        values.update(changes)
        return list(values.items())

    def test_patch_exact_raw_base_and_metadata(self):
        state = self.state()
        status, _, raw = state.handle_latest(self.query())
        body = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertTrue(body["updateAvailable"])
        asset = body["asset"]
        self.assertEqual((asset["kind"], asset["baseVersionCode"], asset["baseImageSha256"]),
                         ("patch", 30286, BASE))
        token = parse_qsl(urlsplit(asset["downloadUrl"]).query)
        code, headers, downloaded = state.handle_download(token, None, None)
        self.assertEqual((code, downloaded), (200, container("patch")))
        self.assertEqual(dict(headers)["Content-Length"], str(len(downloaded)))
        self.assertIn("Content-Digest", dict(headers))

    def test_wrong_base_full_sha_or_version_fails_without_url(self):
        state = self.state()
        for change in [dict(currentVersionCode="30285"), dict(currentImageSha=BASE[:-1] + "0")]:
            with self.subTest(change=change), self.assertRaises(svc.ServiceError) as failure:
                state.handle_latest(self.query(**change))
            self.assertEqual((failure.exception.http_status, failure.exception.error_code),
                             (503, "BACKEND_UNAVAILABLE"))
            self.assertNotIn("asset", failure.exception.extra_fields)
        _, _, raw = state.handle_latest(self.query(currentVersionCode="30287", currentImageSha=TARGET))
        self.assertEqual(json.loads(raw)["errorCode"], "NO_UPDATE")

    def test_config_kind_filename_base_size_and_sha_rejected(self):
        config = self.config()
        changes = [dict(kind="recovery"), dict(kind="full"), dict(fileName="bad-full.etu"),
            dict(fileName="../reference-patch.etu"), dict(fileName="e-track-at32f435-v3.2.85-to-v3.2.87-patch.etu"),
            dict(baseVersionCode=0), dict(baseVersionCode=30287), dict(baseImageSha256=None),
            dict(baseImageSha256=BASE.upper()), dict(sizeBytes=1), dict(sha256="0" * 64)]
        for change in changes:
            bad = copy.deepcopy(config)
            bad["releases"]["reference"]["asset"].update(change)
            with self.subTest(change=change), self.assertRaises(svc.ServiceConfigError):
                self.state(bad)

    def test_outer_header_cannot_lie_about_kind_base_target_or_size(self):
        good = container("patch")
        for offset in (6, 8, 12, 32, 36, 40, 44, 48, 50, 51, 52, 60, 64):
            bad = bytearray(good)
            bad[offset] ^= 1
            if offset < 60:
                struct.pack_into("<I", bad, 60, zlib.crc32(bad[:60]))
            with self.subTest(offset=offset), self.assertRaises(svc.ServiceConfigError):
                self.state(self.config(data=bytes(bad)))
        with self.assertRaises(svc.ServiceConfigError):
            self.state(self.config(data=good + b"x"))
        disguised = self.config("full", good)
        with self.assertRaises(svc.ServiceConfigError):
            self.state(disguised)

    def test_full_and_compatibility_behavior_is_retained(self):
        state = self.state(self.config("full"))
        status, _, raw = state.handle_latest(self.query(currentImageSha="0" * 64))
        asset = json.loads(raw)["asset"]
        self.assertEqual((status, asset["kind"], asset["baseVersionCode"], asset["baseImageSha256"]),
                         (200, "full", 0, None))
        for changed, code in [(dict(hardwareRevision="2"), "HARDWARE_INCOMPATIBLE"),
                (dict(layoutId="2"), "LAYOUT_INCOMPATIBLE"), (dict(bootVersion="0"), "BOOT_TOO_OLD"),
                (dict(protocolVersion="2"), "PROTOCOL_UNSUPPORTED")]:
            with self.assertRaises(svc.ServiceError) as failure:
                self.state().handle_latest(self.query(currentImageSha="0" * 64, **changed))
            self.assertEqual(failure.exception.error_code, code)

    def test_real_http_patch_download_range_and_invalid_tokens(self):
        supplied = os.environ.get("P34_REFERENCE_ETU")
        data = Path(supplied).read_bytes() if supplied else container("patch")
        if supplied:
            self.assertEqual(len(data), 1048576)
            self.assertEqual(hashlib.sha256(data).hexdigest(),
                "8373305b6817081106ad35c840ef87bf2d4210ffa2e8b9e881e0799ad1ff9e47")
        print("PATCH_HTTP_INPUT " + json.dumps(dict(path=str(Path(supplied).resolve()) if supplied else None,
            bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
            source="retained-1MiB-reference" if supplied else "synthetic-host-container")), flush=True)
        state = self.state(self.config(data=data))
        handler = type("BoundPatchHandler", (svc.P33RequestHandler,),
                       dict(state=state, log=logging.getLogger("p34-http-test")))
        server = svc.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            origin = "http://127.0.0.1:%d" % server.server_address[1]
            state.public_base_url = origin
            with urlopen(origin + svc.LATEST_PATH + "?" + urlencode(self.query()), timeout=5) as response:
                body = json.load(response)
            url = body["asset"]["downloadUrl"]
            with urlopen(url, timeout=5) as response:
                self.assertEqual(response.read(), data)
                etag = response.headers["ETag"]
            from urllib.request import Request
            with urlopen(Request(url, headers={"Range": "bytes=64-", "If-Range": etag}), timeout=5) as response:
                self.assertEqual((response.status, response.read()), (206, data[64:]))
            for token in [dict(parse_qsl(urlsplit(url).query), signature="bad"),
                          dict(parse_qsl(urlsplit(url).query), kind="full")]:
                with self.assertRaises(HTTPError) as failure:
                    urlopen(origin + svc.DOWNLOAD_PATH + "?" + urlencode(token), timeout=5)
                self.assertEqual(failure.exception.code, 401)
                failure.exception.close()
            with self.assertRaises(HTTPError) as failure:
                urlopen(origin + svc.LATEST_PATH + "?" + urlencode(self.query(currentImageSha="0" * 64)), timeout=5)
            self.assertEqual(failure.exception.code, 503)
            failure.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main(verbosity=2)
