"""Offline regressions for the fixed receiver, immutable inputs and rollback."""
import copy
import io
import json
from pathlib import Path
import runpy
import struct
import sys
import unittest
from unittest.mock import patch
import urllib.parse
import zlib

m = runpy.run_path(str(Path(__file__).with_name("irq_screen.py")))
r = m["runtime"]()
restore = r.load("irq_screen_test_restore", Path(__file__).with_name("baud_restore.py"))
tune = r.load("irq_screen_test_tune", Path(__file__).with_name("baud_tune.py"))
old = restore.load("irq_screen_test_arbiter", m["ROOT"] / ".cache/p34-restore-20260922/restore_device.py")


class Inputs(unittest.TestCase):
    def test_bootstrap_was_verified_and_closed(self):
        self.assertEqual(len(m["prior_complete"](r)), 4)

    def test_exact_unchanged_receiver_body_and_map(self):
        group = r.m.verified_assets()["groups"]["screen"]
        m["validate_group"](group)
        baseline = Path(group["baseline"]["path"]).read_bytes()
        target = Path(group["target"]["path"]).read_bytes()
        self.assertEqual(baseline[:0x400], target[:0x400])
        self.assertEqual(baseline[0x460:], target[0x460:])
        self.assertNotEqual(baseline[0x400:0x460], target[0x400:0x460])
        maps = r.m.load_bindings()["profiles"]
        self.assertEqual(set(maps), {"30210", "30211"})
        self.assertEqual(maps["30210"]["map"], maps["30211"]["map"])
        self.assertEqual(maps["30210"]["symbols"], maps["30211"]["symbols"])

    def test_wrong_identity_size_or_decoder_is_rejected(self):
        group = r.m.verified_assets()["groups"]["screen"]
        for section, key, value in (("baseline_identity", "version_code", 30208),
                ("target_identity", "version_code", 30210), ("target", "bytes", 613280),
                ("baseline", "sha256", "0" * 64), ("decoder", "byte_identical", False)):
            changed = copy.deepcopy(group)
            changed[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(RuntimeError):
                m["validate_group"](changed)

    def test_all_bauds_share_one_input_and_sender(self):
        group = r.m.verified_assets()["groups"]["screen"]
        values = [r.experiment_config(name, group, baud, "https://unit-fixture.trycloudflare.com")
                  for name, baud in m["CELLS"]]
        self.assertEqual({x["requestedBaud"] for x in values}, {115200, 460800, 921600})
        for x in values:
            del x["requestedBaud"], x["runId"]
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[1], values[2])
        self.assertTrue(values[0]["reuseGatt"] and values[0]["withoutResponse"])

    def test_runtime_binds_exact_app_and_recovery(self):
        self.assertEqual(r.PKG, "com.wen.gaia.gaia.p34retry")
        self.assertEqual(r.PHONE, m["AREA"] / "runtime/phone-r1")
        self.assertEqual(restore.OUT, m["AREA"] / "recovery")
        self.assertIs(restore.m, r.m)
        self.assertIs(tune.m, r.m)
        self.assertEqual(restore.expectation()["from_version"], 30211)
        self.assertEqual(restore.expectation()["to_version"], 30210)
        self.assertEqual(restore.expectation()["backup_sha256"], m["BASE_SHA"])

    def test_original_adapters_remain_unchanged_and_transform_is_bound(self):
        for name in m["ADAPTER_INPUTS"]:
            source = Path(__file__).with_name(name).read_text(encoding="utf-8")
            expected = m["transform_adapter"](name, source)
            self.assertEqual((m["AREA"] / "adapters" / name).read_text(encoding="utf-8"), expected)
            with self.assertRaises(RuntimeError):
                m["transform_adapter"](name, source + "\n")

    def test_old_tuning_identity_fails_before_hardware(self):
        with patch.object(r.m, "native_authority", side_effect=AssertionError("hardware reached")):
            with self.assertRaisesRegex(RuntimeError, "admission identity"):
                tune.tune("wrong-version", 460800, 30208)

    def test_busy_unknown_and_unplanned_rate_rejected(self):
        status = dict(busy=0, probe=0, state=1, known=115200, baud=115200, epoch=7)
        for baud in (115200, 460800, 921600):
            self.assertEqual(tune.command_for("probe", baud, status), "probe 7 " + str(baud))
        for changed in (dict(busy=1), dict(probe=1), dict(state=0), dict(state=2), dict(known=460800)):
            with self.assertRaises(RuntimeError):
                tune.command_for("set", 921600, dict(status, **changed))
        with self.assertRaises(RuntimeError):
            tune.command_for("set", 230400, status)

    def test_unplanned_or_existing_cell_cannot_start(self):
        with self.assertRaises(RuntimeError):
            m["admit_next"](r, "extra-460800")
        with patch.object(r, "cell", return_value=m["PRIOR"]):
            with self.assertRaisesRegex(RuntimeError, "may already have executed"):
                m["admit_next"](r, "irq-460800")


class Routing(unittest.TestCase):
    def setUp(self):
        self.group = r.m.verified_assets()["groups"]["screen"]
        self.state = r.RoutingState(r.m.verified_assets(), "https://unit-fixture.trycloudflare.com")

    def latest(self):
        status, _, data = self.state.handle_latest(list(r.query_for(self.group).items()))
        self.assertEqual(status, 200)
        body = json.loads(data)
        r.verify_latest(body, self.group)
        return body

    def test_unique_name_and_exact_download(self):
        body = self.latest()
        self.assertEqual(body["asset"]["fileName"], m["FILE_NAME"])
        pairs = urllib.parse.parse_qsl(urllib.parse.urlsplit(body["asset"]["downloadUrl"]).query)
        status, _, data = self.state.handle_download(pairs, None, None)
        self.assertEqual(status, 200)
        self.assertEqual(data, Path(self.group["package"]["path"]).read_bytes())
        status, _, suffix = self.state.handle_download(pairs, "bytes=16-", None)
        self.assertEqual(status, 206)
        self.assertEqual(suffix, data[16:])

    def test_installed_target_is_not_offered_itself(self):
        query = r.query_for(self.group)
        query.update(currentVersionCode="30211", currentImageSha=self.group["target"]["sha256"])
        status, _, data = self.state.handle_latest(list(query.items()))
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(data)["updateAvailable"])

    def test_duplicate_and_tampered_download_inputs_fail(self):
        body = self.latest()
        pairs = urllib.parse.parse_qsl(urllib.parse.urlsplit(body["asset"]["downloadUrl"]).query)
        for changed in (pairs + [("releaseId", "p34-baud-screen")],
                        [(k, "p34-baud-bootstrap" if k == "releaseId" else v) for k, v in pairs]):
            with self.assertRaises(r.service.ServiceError):
                self.state.handle_download(changed, None, None)


class Recovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = restore.expectation()
        cls.baseline = Path(cls.expected["group"]["baseline"]["path"]).read_bytes()

    def ready(self, seq=17):
        words = [restore.MAGIC, 1, 1, 0, 1000, 0, 0, 1, 30211, 30210,
                 self.expected["backup_length"], self.expected["backup_crc32"], 0, 0, 0, 0]
        record = bytearray(64)
        record[:8] = b"ETBC\x01\x04\x00\x00"
        struct.pack_into("<H", record, 8, seq)
        struct.pack_into("<IIII", record, 28, 30211, self.expected["backup_length"], self.expected["backup_crc32"], 30210)
        struct.pack_into("<I", record, 60, zlib.crc32(record[:60]) & 0xFFFFFFFF)
        storage = bytearray(b"\xff" * 128 + b"\xa5" * 128)
        storage[:64], storage[255] = record, 0x55
        return struct.pack("<16I", *words) + bytes(storage) + bytes(256) + bytes.fromhex(
            self.expected["boot_sha256"]) + bytes.fromhex(self.expected["backup_sha256"])

    def committed(self, ready):
        value, record = bytearray(ready), bytearray(ready[64:128])
        record[5:8] = bytes((5, 0, 2))
        struct.pack_into("<H", record, 8, (struct.unpack_from("<H", record, 8)[0] + 1) & 65535)
        struct.pack_into("<I", record, 60, zlib.crc32(record[:60]) & 0xFFFFFFFF)
        value[320:576], value[384:448] = ready[64:320], record
        struct.pack_into("<I", value, 8, 3)
        struct.pack_into("<III", value, 48, 1, 0, 1)
        return bytes(value)

    def test_exact_inactive_bcb_and_sequence_wrap(self):
        for seq in (17, 65535):
            ready = self.ready(seq)
            result = restore.validate_committed(ready, self.committed(ready), self.expected, old.arbitrate)
            self.assertTrue(result["settings_unchanged"])
            self.assertEqual(result["after_seq"], (seq + 1) & 65535)

    def test_settings_changes_rejected(self):
        ready = self.ready()
        value = bytearray(self.committed(ready))
        value[520] ^= 1
        with self.assertRaises(RuntimeError):
            restore.validate_committed(ready, value, self.expected, old.arbitrate)

    def test_wrong_helper_state_identity_or_hash_rejected(self):
        for offset in (0, 8, 32, 36, 40, 44, 576, 608):
            value = bytearray(self.ready())
            value[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                restore.validate_ready(value, self.expected, old.arbitrate)

    def test_backup_slot_checks_full_identity_and_marker(self):
        value = b"ETSL\x02\xff\xff\xff" + struct.pack("<III", len(self.baseline), self.expected["backup_crc32"], 30210)
        value += self.baseline[0x428:0x430] + struct.pack("<I", 0x434F4D54)
        restore.validate_slot(value, self.baseline, self.expected)
        for offset in (0, 4, 8, 12, 16, 20, 28):
            changed = bytearray(value)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                restore.validate_slot(changed, self.baseline, self.expected)


if __name__ == "__main__":
    m["require"](Path.cwd() == m["ROOT"] and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                 "isolated explicit root required")
    out = m["checked"](m["AREA"] / "host-tests")
    m["require"](not out.exists(), "preserve existing host-test evidence")
    m["checked"](out / "result.json")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    r.save(out / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), output=stream.getvalue(),
        source=r.b.record(m["SELF"]), test_source=r.b.record(Path(__file__)), hardware=False))
    print(stream.getvalue(), flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
