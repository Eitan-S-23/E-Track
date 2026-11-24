"""Host regressions for routing, immutable App configuration and recovery gates."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
import urllib.parse
import zlib


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


r = load("baud_runtime_tested", Path(__file__).with_name("baud_runtime.py"))
t = load("baud_tune_tested", Path(__file__).with_name("baud_tune.py"))
restore = load("baud_restore_tested", Path(__file__).with_name("baud_restore.py"))
old = load("baud_restore_original_arbiter", r.b.ROOT / ".cache/p34-restore-20260922/restore_device.py")
OUT = r.b.checked(r.b.OUT / "host-tests-runtime-002")


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = r.m.verified_assets()
        cls.state = r.RoutingState(cls.assets, "https://unit-fixture.trycloudflare.com")

    def latest(self, tag):
        group = self.assets["groups"][tag]
        status, _, raw = self.state.handle_latest(list(r.query_for(group).items()))
        self.assertEqual(status, 200)
        body = json.loads(raw)
        r.verify_latest(body, group)
        return body, urllib.parse.parse_qsl(urllib.parse.urlsplit(body["asset"]["downloadUrl"]).query)

    def test_both_latest_and_download_groups_use_matching_release(self):
        for tag, group in self.assets["groups"].items():
            with self.subTest(tag=tag):
                _, pairs = self.latest(tag)
                status, _, data = self.state.handle_download(pairs, None, None)
                self.assertEqual(status, 200)
                self.assertEqual(data, Path(group["package"]["path"]).read_bytes())

    def test_tampered_token_still_rejected(self):
        _, pairs = self.latest("bootstrap")
        pairs = [(key, "p34-baud-screen" if key == "releaseId" else value) for key, value in pairs]
        with self.assertRaises(r.service.ServiceError) as error:
            self.state.handle_download(pairs, None, None)
        self.assertEqual(error.exception.http_status, 401)

    def test_duplicate_parameter_rejected(self):
        _, pairs = self.latest("bootstrap")
        pairs.append(("releaseId", "p34-baud-screen"))
        with self.assertRaises(r.service.ServiceError):
            self.state.handle_download(pairs, None, None)

    def test_only_frozen_open_ranges(self):
        _, pairs = self.latest("screen")
        status, _, data = self.state.handle_download(pairs, "bytes=16-", None)
        self.assertEqual(status, 206)
        self.assertEqual(len(data), self.assets["groups"]["screen"]["package"]["bytes"] - 16)
        with self.assertRaises(r.service.ServiceError):
            self.state.handle_download(pairs, "bytes=16-63", None)

    def test_no_upgrade_loop_at_final_target(self):
        query = r.query_for(self.assets["groups"]["screen"])
        query["currentVersionCode"] = "30209"
        query["currentImageSha"] = self.assets["groups"]["screen"]["target"]["sha256"]
        status, _, raw = self.state.handle_latest(list(query.items()))
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)["updateAvailable"])

    def test_unknown_model_rejected(self):
        query = r.query_for(self.assets["groups"]["screen"])
        query["deviceModel"] = "unknown"
        with self.assertRaises(r.service.ServiceError) as error:
            self.state.handle_latest(list(query.items()))
        self.assertEqual(error.exception.http_status, 400)


class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        group = r.m.verified_assets()["groups"]["screen"]
        cls.value = r.experiment_config("baud-921600", group, 921600, "https://unit-fixture.trycloudflare.com")
        data = (json.dumps(cls.value) + "\n").encode()
        cls.file = r.raw(OUT / "p34-experiment.json", data)
        cls.config = dict(id="baud-921600", baud=921600, runtime_config=cls.file)

    def line(self, **changed):
        value = dict(self.value)
        value.pop("target")
        value.pop("firmwareLatestUrl")
        value.update(configSha256=self.file["sha256"], deviceAddress=r.TARGET, endpointHost="unit-fixture.trycloudflare.com")
        value.update(changed)
        return "OTA_EXPERIMENT " + json.dumps(value)

    def test_original_bytes_and_both_identities_are_bound(self):
        value = r.experiment_line(self.line(), self.config)
        self.assertEqual(value["requestedBaud"], 921600)

    def test_wrong_hash_baud_run_endpoint_and_package_rejected(self):
        for key, value in (("configSha256", "0" * 64), ("runId", "other"), ("requestedBaud", 115200),
                           ("endpointHost", "wrong.invalid"), ("packageBytes", 1), ("deviceAddress", "other")):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                r.experiment_line(self.line(**{key: value}), self.config)

    def test_all_three_rates_share_one_package(self):
        group = r.m.verified_assets()["groups"]["screen"]
        values = [r.experiment_config("baud-" + str(rate), group, rate, "https://unit-fixture.trycloudflare.com")
                  for rate in (115200, 460800, 921600)]
        self.assertEqual(len({item["packageSha256"] for item in values}), 1)
        self.assertEqual(len({item["packageBytes"] for item in values}), 1)

    def test_real_query_parser_accepts_config_but_not_an_upgrade(self):
        p = r.phone("host-fixture")
        capture_id, sentinel, pid = "1790090000000-" + "a" * 24, "OTAOBS" + "b" * 24, 1234
        header = dict(seq=1, kind="open", schema=1, captureId=capture_id, pid=pid, sentinel=sentinel,
                      target=r.TARGET, platform="android")
        summary = dict(label="query", device=r.TARGET, getInfo=dict(calls=1, failures=0), bind=dict(found=True, subscribeOk=True))
        lines = [header, dict(seq=2, kind="line", message=self.line()),
                 dict(seq=3, kind="line", message="OTA_LINK_STATS " + json.dumps(summary))]
        data = b"".join((json.dumps(row) + "\n").encode() for row in lines)
        health = dict(schema=1, captureId=capture_id, healthy=True, error=None, lost=0, records=3, bytes=len(data),
                      producerLines=2, upgradeStarts=0, upgradeEnds=0, outcome=None)
        raw = json.dumps(health).encode()
        result, _, messages = p.query.validate(data, raw, raw, pid=pid, sentinel=sentinel, target=r.TARGET)
        self.assertEqual(result["successfulQueries"], 1)
        r.experiment_line(messages, self.config)
        health["upgradeStarts"] = 1
        with self.assertRaises(RuntimeError):
            p.query.validate(data, json.dumps(health).encode(), raw, pid=pid, sentinel=sentinel, target=r.TARGET)


class RateTests(unittest.TestCase):
    def setUp(self):
        self.status = dict(busy=0, probe=0, state=1, known=115200, baud=115200, epoch=4)

    def test_all_requested_rates_in_first_batch(self):
        for rate in (115200, 460800, 921600):
            self.assertEqual(t.command_for("probe", rate, self.status), "probe 4 " + str(rate))
        self.assertEqual(t.command_for("set", 921600, self.status), "rate set 4 921600")

    def test_no_set_from_unknown_pending_busy_or_unmatched_baud(self):
        for patch in (dict(state=0), dict(state=2), dict(busy=1), dict(probe=1), dict(known=460800)):
            with self.subTest(patch=patch), self.assertRaises(RuntimeError):
                t.command_for("set", 921600, dict(self.status, **patch))

    def test_no_unnecessary_set_or_unplanned_230400(self):
        for rate in (115200, 230400):
            with self.assertRaises(RuntimeError):
                t.command_for("set", rate, self.status)


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = restore.expectation()
        cls.baseline = Path(cls.expected["group"]["baseline"]["path"]).read_bytes()

    def ready(self, seq=17):
        words = [restore.MAGIC, 1, 1, 0, 1000, 0, 0, 1, 30209, 30208,
                 self.expected["backup_length"], self.expected["backup_crc32"], 0, 0, 0, 0]
        record = bytearray(64)
        record[:8] = b"ETBC\x01\x04\x00\x00"
        struct.pack_into("<H", record, 8, seq)
        struct.pack_into("<IIII", record, 28, 30209, self.expected["backup_length"], self.expected["backup_crc32"], 30208)
        struct.pack_into("<I", record, 60, zlib.crc32(record[:60]) & 0xFFFFFFFF)
        storage = bytearray(b"\xff" * 128 + b"\xa5" * 128)
        storage[:64] = record
        storage[255] = 0x55
        return struct.pack("<16I", *words) + bytes(storage) + bytes(256) + bytes.fromhex(self.expected["boot_sha256"]) + bytes.fromhex(self.expected["backup_sha256"])

    def committed(self, ready):
        value = bytearray(ready)
        record = bytearray(ready[64:128])
        record[5:8] = bytes((5, 0, 2))
        struct.pack_into("<H", record, 8, (struct.unpack_from("<H", record, 8)[0] + 1) & 65535)
        struct.pack_into("<I", record, 60, zlib.crc32(record[:60]) & 0xFFFFFFFF)
        value[320:576] = ready[64:320]
        value[384:448] = record
        struct.pack_into("<I", value, 8, 3)
        struct.pack_into("<III", value, 48, 1, 0, 1)
        return bytes(value)

    def test_exact_inactive_transaction_and_sequence_wrap(self):
        for seq in (17, 65535):
            ready = self.ready(seq)
            restore.validate_ready(ready, self.expected, old.arbitrate)
            result = restore.validate_committed(ready, self.committed(ready), self.expected, old.arbitrate)
            self.assertTrue(result["settings_unchanged"])
            self.assertEqual(result["after_seq"], (seq + 1) & 65535)

    def test_settings_write_is_rejected(self):
        ready = self.ready()
        data = bytearray(self.committed(ready))
        data[320 + 200] ^= 1
        with self.assertRaises(RuntimeError):
            restore.validate_committed(ready, data, self.expected, old.arbitrate)

    def test_wrong_helper_identity_or_digest_is_rejected(self):
        for offset in (0, 8 * 4, 10 * 4, 576, 608):
            data = bytearray(self.ready())
            data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                restore.validate_ready(data, self.expected, old.arbitrate)

    def test_slot_full_identity_gate(self):
        data = b"ETSL\x02\xff\xff\xff" + struct.pack("<III", len(self.baseline), self.expected["backup_crc32"], 30208) + self.baseline[0x428:0x430] + struct.pack("<I", 0x434F4D54)
        restore.validate_slot(data, self.baseline, self.expected)
        for offset in (0, 4, 8, 12, 16, 20, 28):
            changed = bytearray(data)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                restore.validate_slot(changed, self.baseline, self.expected)


if __name__ == "__main__":
    r.b.require(Path.cwd().resolve() == r.b.ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit root required")
    r.b.require(not OUT.exists(), "preserve previous test evidence")
    for name in ("p34-experiment.json", "result.json"):
        r.b.checked(OUT / name)
    OUT.mkdir(parents=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    r.save(OUT / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), sources=r.sources(), test_source=r.b.record(Path(__file__)), hardware=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
