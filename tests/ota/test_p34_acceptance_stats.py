"""Full v1/v2 accounting fixtures, not physical OTA performance evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/p3-4-link-stats"))
sys.path.insert(0, str(ROOT / "tests/ota"))
import acceptance_stats as m
from test_p3_4_observation_capture import rows, encoded, SENTINEL, TARGET


def fixture(*, total=384, protocol=2, initial=0, failed=False, missing=False, early=False):
    source = dict(packageSha256="a" * 64, packageBytes=total, currentVersionCode=30286,
                  currentImageSha256="b" * 64, targetVersionCode=30287, targetImageSha256="c" * 64,
                  deviceAddress=TARGET, appLifecycle="resumed")
    stamp = dict(schema=10, runId="fixture", configSha256="e" * 64, requestedBaud=921600,
        reuseGatt=True, withoutResponse=False, endpointHost="fixture.invalid", senderWindowSegments=24,
        transferMode="full", prefixBytes=None, dataBatchFrames=12, androidPhyPolicy="off",
        rebootInfoMaxAttempts=8, ackTimeoutMs=2000, **{k: v for k, v in source.items() if k != "appLifecycle"})
    messages = ["OTA_EXPERIMENT " + json.dumps(stamp)]
    def sample(kind, at, **fields):
        messages.append("OTA_LINK_SAMPLE label=upgrade kind=" + kind + " us=" + str(at) +
                        "".join(" " + key + "=" + str(value) for key, value in fields.items()))
    writes = []
    def gatt(size):
        sample("gatt_write", 10, bytes=size)
        writes.append(size)
    def control(cmd, at, seq):
        f = dict(cmd=cmd, session=0 if cmd in (0x10, 1, 0x11) else 7, seq=seq, bytes=m.CONTROL_BYTES[cmd])
        sample("control_start", at, **f)
        gatt(f["bytes"])
        sample("control_end", at + 20, **f)
    if protocol == 2: control(0x10, 10, 50)
    control(0x11 if protocol == 2 else 1, 100, 0)
    begin = dict(protocol=protocol, session=7, seq=0, epoch=123 if protocol == 2 else 0,
                 off=initial, bitmap=0, ackTimeoutMs=2000, maxRetries=5, windowSegments=24)
    sample("begin_ack", 115, **begin)
    sample("durable", 115, off=initial)
    sent, latencies, durable = {}, [], [(115, initial)]
    data_wire = 0
    limit = min(4096, total - 128) if failed else total
    pending = []
    for off in range(initial, limit, 128):
        length = min(128, total - off)
        at = 1000 + (off - initial) * 10
        wire = length + (18 if protocol == 2 else 14)
        data_wire += wire
        gatt(wire)
        sample("batch_chunk", at, bytes=wire, frames=1)
        sample("segment_first_send", at + 1, off=off, len=length)
        sent[off] = at + 1
        pending.append(off)
        if off + length == total or (off + length) % 4096 == 0:
            confirm = at + 100
            for offset in pending:
                if missing and offset == off: continue
                if early and offset == off:
                    # Original observer records the early arrival and marks it
                    # invalid on completion; there is no zero-valued ACK sample.
                    messages = [line.replace("us=" + str(sent[off]) + " off=" + str(off),
                                "us=" + str(confirm + 1) + " off=" + str(off))
                                if "kind=segment_first_send " in line else line for line in messages]
                    sent[off] = confirm + 1
                    sample("ack_early", confirm, off=off)
                    sample("ack_early_invalid", confirm, off=off)
                    continue
                latency = confirm - sent[offset]
                latencies.append(latency)
                sample("ack_latency", latency, off=offset)
            pending.clear()
            sample("durable", confirm, off=off + length)
            durable.append((confirm, off + length))
    end = None
    if not failed:
        end = max(sent.values()) + 500
        control(0x13 if protocol == 2 else 3, end - 10, len(sent) + 1)
    missing_count = len(sent) - len(latencies)
    early_count = 1 if early else 0
    parts = []
    if missing_count: parts.append("missing=" + str(missing_count))
    if early_count: parts.append("early=" + str(early_count))
    gatt_summary = m.distribution([10] * len(writes))
    gatt_summary.pop("count"); gatt_summary.pop("p99Us")
    summary = dict(schema=1, label="upgrade", clock="stopwatch-mono-us",
        bind=dict(mtuChunkBytes=244, writeMode="writeWithResponse"),
        failure=dict(stage="transfer" if failed else None, reason="DISCONNECTED" if failed else None),
        gattWrites=dict(calls=len(writes), bytes=sum(writes), errors=0, **gatt_summary),
        transfer=dict(startUs=100, endAckUs=end, elapsedUs=end - 100 if end else None,
            outcome="fail" if failed else "ok", begin=dict(first=dict(us=115, **begin), count=1),
            segmentsUnique=len(sent), segmentSendTotal=len(sent), retransmitFrames=0,
            acks=dict(ok=len(sent), duplicate=0, error=0, malformed=0, noProgress=0, abort=0,
                      ignoredErrors=dict(schema=1, counts={}, saturated=False)),
            ackSamples="partial:" + ",".join(parts) if parts else "complete",
            ackEarlyInvalid=early_count, ackEarlyUnsent=0, ackLatency=m.distribution(latencies),
            durable=dict(events=len(durable), finalOff=durable[-1][1]),
            dataBatch=dict(schema=1, maxFrames=12, chunks=len(sent), bytes=data_wire)))
    messages.append("OTA_LINK_STATS " + json.dumps(summary))
    messages.append("OTA_MONO MONO_BUDGET_START monoUs=1000 wallUs=5000")
    messages.append("OTA_IDENTITY " + json.dumps(dict(phase="pre-transfer", versionCode=30286,
                                                    imageSha256="b" * 64, deviceAddress=TARGET)))
    if not failed:
        messages.append(f"OTA_MONO MONO_END_ACK_OK monoUs={end + 1000} wallUs=6000")
        messages.append(f"OTA_MONO MONO_REBOOT_VERIFIED monoUs={end + 2000} wallUs=7000")
        messages.append("OTA_IDENTITY " + json.dumps(dict(phase="post-reboot", versionCode=30287,
                                                        imageSha256="c" * 64, deviceAddress=TARGET)))
    return source, messages


def snapshot(source, messages):
    items = [rows()[0], dict(kind="upgrade-start", input=source)]
    items.extend(dict(kind="line", message=line) for line in messages)
    failed = json.loads(next(s[len("OTA_LINK_STATS "):] for s in messages if s.startswith("OTA_LINK_STATS ")))["transfer"]["outcome"] != "ok"
    items.append(dict(kind="upgrade-end", outcome="not-completed" if failed else "completed"))
    for i, item in enumerate(items, 1): item["seq"] = i
    return encoded(items)


def observed(**kwargs):
    return m.inspect(snapshot(*fixture(**kwargs)), SENTINEL, TARGET)


class Tests(unittest.TestCase):
    def test_v1_and_complete_v2_schema10_and_same_stamp(self):
        for protocol in (1, 2):
            source, messages = fixture(protocol=protocol)
            messages.insert(1, messages[0])
            value = m.inspect(snapshot(source, messages), SENTINEL, TARGET)
            self.assertTrue(value["fullZeroStart"])
            self.assertTrue(value["ackEligible"])
            self.assertEqual(value["parameters"]["protocol"], protocol)
            self.assertEqual(value["observedAckP99Us"], 2659)

    def test_resume_does_not_become_full_reference(self):
        value = observed(total=8192, initial=4096)
        self.assertEqual(value["initialDurable"], 4096)
        self.assertFalse(value["fullZeroStart"])
        self.assertFalse(value["ackEligible"])
        self.assertIsNone(value["throughputKiBs"])

    def test_failed_and_missing_early_samples_remain_visible(self):
        fail = observed(total=8192, failed=True)
        self.assertFalse(fail["success"])
        self.assertIsNone(fail["transferUs"])
        for key in ("missing", "early"):
            value = observed(**{key: True})
            self.assertEqual(value["missingAckSamples"], 1)
            self.assertFalse(value["ackEligible"])
            self.assertNotIn(0, value["ackSamplesUs"])

    def test_wrong_wire_summary_config_end_clock_and_originals_fail(self):
        source, good = fixture()
        cases = [[s.replace("bytes=146", "bytes=145") for s in good],
                 [s for s in good if "kind=control_end" not in s or "cmd=19" not in s],
                 [s for s in good if "MONO_END_ACK_OK" not in s],
                 [s.replace('"clock": "stopwatch-mono-us"', '"clock": "wall-us"') for s in good],
                 [s.replace('"p99Us": 2659', '"p99Us": 0') for s in good],
                 [s.replace("kind=ack_latency us=2659", "kind=ack_latency us=99999999") for s in good],
                 good + [good[0].replace('"ackTimeoutMs": 2000', '"ackTimeoutMs": 500')],
                 [s for s in good if "kind=segment_first_send us=1001" not in s],
                 good + [next(s for s in good if "kind=segment_first_send " in s)]]
        for i, bad in enumerate(cases):
            with self.subTest(case=i), self.assertRaises(ValueError):
                m.inspect(snapshot(source, bad), SENTINEL, TARGET)

    def test_full_reference_group_30_and_nearest_rank_no_success_selection(self):
        template = observed(total=1048576)
        runs = []
        for i in range(30):
            value = copy.deepcopy(template)
            value["captureId"] = str(i)
            value["rawSha256"] = hashlib.sha256(str(i).encode()).hexdigest()
            runs.append(dict(id=str(i), observation=value))
        result = m.aggregate(runs, expected_count=30)
        self.assertTrue(result["groups"][0]["stability30MeetsObservedGates"])
        self.assertEqual(result["groups"][0]["successes"], 30)
        runs[-1]["observation"]["success"] = False
        result = m.aggregate(runs, expected_count=30)
        self.assertEqual(result["groups"][0]["failures"], 1)
        self.assertFalse(result["groups"][0]["stability30MeetsObservedGates"])
        self.assertIsNone(result["groups"][0]["recommendedAckTimeoutMs"])
        with self.assertRaises(ValueError): m.aggregate(runs[:-1], expected_count=30)
        with self.assertRaises(ValueError): m.aggregate(runs + [runs[-1]], expected_count=31)

    def test_baud_timeout_retry_never_mix_and_missing_file_is_not_zero(self):
        for key, changed in (("requestedBaud", 460800), ("ackTimeoutMs", 500), ("maxRetries", 4)):
            a, b = observed(), observed()
            b["captureId"], b["rawSha256"] = "different", "different"
            b["parameters"][key] = changed
            result = m.aggregate([dict(id="a", observation=a), dict(id="b", observation=b),
                                  dict(id="c", gap="original not captured")], expected_count=3)
            self.assertEqual(len(result["groups"]), 2)
            self.assertEqual(len(result["evidenceGaps"]), 1)
            self.assertTrue(all(not g["ackP99Eligible"] for g in result["groups"]))

    def test_ten_recoveries_require_disconnect_and_durable_resume_not_abort(self):
        a, b = observed(total=8192, failed=True), observed(total=8192, initial=4096)
        runs = []
        for i in range(10):
            for role, original in (("disconnect", a), ("resume", b)):
                value = copy.deepcopy(original)
                value["captureId"] = value["rawSha256"] = f"{i}-{role}"
                runs.append(dict(id=f"{i}-{role}", role=role, recoveryCase=str(i), observation=value))
        result = m.aggregate(runs, expected_count=20)
        self.assertEqual(result["successfulRecoveries"], 10)
        self.assertTrue(result["recovery10MeetsObservedGates"])
        runs[0]["observation"]["failure"]["reason"] = "CANCELLED"
        result = m.aggregate(runs, expected_count=20)
        self.assertEqual(result["successfulRecoveries"], 9)
        self.assertFalse(result["recovery10MeetsObservedGates"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
