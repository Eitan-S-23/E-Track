"""Offline P3-4 run/group accounting over original, strictly verified App snapshots.

No collection, device commands or acceptance authority. A plan lists every attempt,
including missing/failed ones; its IDs/counts are frozen by the independent owner.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from observation_capture import decode, digest, require, uint, verify, MAX_BYTES, INPUT_FIELDS
from batch_timing import verify_batch_stamp

SAMPLE = re.compile(r"OTA_LINK_SAMPLE label=upgrade kind=(\w+) us=(-?\d+)(?: (.*))?")
CONTROL_BYTES = {1: 111, 3: 42, 4: 10, 5: 10, 0x10: 14, 0x11: 115, 0x13: 46, 0x14: 14}
GROUP_FIELDS = ("requestedBaud reuseGatt withoutResponse senderWindowSegments dataBatchFrames "
                "pauseScanDuringOta androidHighPriority androidPhyPolicy reuseRebootInfoLink "
                "rebootInfoTimeoutMs rebootProbeIntervalMs rebootInfoMaxAttempts").split()


def rank(values, percent):
    return sorted(values)[max(1, (len(values) * percent + 99) // 100) - 1] if values else None


def samples(messages):
    for index, line in enumerate(messages):
        match = SAMPLE.fullmatch(line)
        if not match:
            require(not line.startswith("OTA_LINK_SAMPLE label=upgrade "), "malformed upgrade sample")
            continue
        fields = {}
        for part in (match[3] or "").split():
            kv = part.split("=")
            require(len(kv) == 2 and kv[0] not in fields and re.fullmatch(r"-?\d+", kv[1]),
                    "unknown/duplicate sample field")
            fields[kv[0]] = int(kv[1])
        yield index, match[1], int(match[2]), fields


def experiment(messages, envelope):
    values = [decode(line[len("OTA_EXPERIMENT "):]) for line in messages if line.startswith("OTA_EXPERIMENT ")]
    require(values and all(value == values[0] for value in values), "missing/conflicting runtime configuration")
    stamp = values[0]
    require(uint(stamp.get("schema")) and 1 <= stamp["schema"] <= 10, "unknown experiment schema")
    for key in INPUT_FIELDS - {"appLifecycle"}:
        expected, actual = envelope["input"][key], stamp.get(key)
        require(type(actual) is type(expected) and
                (actual.lower() == expected.lower() if key == "deviceAddress" else actual == expected),
                "runtime/input identity mismatch: " + key)
    require(stamp.get("requestedBaud") in (115200, 230400, 460800, 921600) and
            type(stamp.get("reuseGatt")) is bool and type(stamp.get("withoutResponse")) is bool and
            digest(stamp.get("configSha256")), "runtime parameter identity")
    if stamp["schema"] >= 5:
        verify_batch_stamp(stamp, stamp.get("dataBatchFrames"))
    return stamp


def distribution(values):
    return dict(count=len(values), minUs=min(values) if values else None,
                p50Us=rank(values, 50), p95Us=rank(values, 95), p99Us=rank(values, 99),
                maxUs=max(values) if values else None)


def analyze(envelope, messages, *, historical=False):
    total = envelope["input"]["packageBytes"]
    require(64 <= total <= 1048576, "bounded input package required")
    stamp = experiment(messages, envelope)
    summaries = [decode(line[len("OTA_LINK_STATS "):]) for line in messages if line.startswith("OTA_LINK_STATS ")]
    summaries = [s for s in summaries if s.get("label") == "upgrade"]
    require(len(summaries) == 1, "one original upgrade summary required")
    summary = summaries[0]
    require(type(summary.get("schema")) is int and summary["schema"] == 1 and
            summary.get("clock") == "stopwatch-mono-us", "mixed/unknown App clock")
    t = summary["transfer"]
    if not historical:
        ignored_summary = t["acks"].get("ignoredErrors")
        require(isinstance(ignored_summary, dict) and set(ignored_summary) == {"schema", "counts", "saturated"} and
                ignored_summary["schema"] == 1 and isinstance(ignored_summary["counts"], dict) and
                type(ignored_summary["saturated"]) is bool, "filtered-error observation capability missing")
    require(t.get("outcome") in ("ok", "fail"), "missing transfer outcome")
    success = envelope["outcome"] == "completed"
    require(not success or t["outcome"] == "ok", "business/transfer outcome conflict")
    start, end = t["startUs"], t["endAckUs"]
    require(start is None or uint(start, (1 << 63)-1), "invalid transfer origin")
    require(end is None or (uint(end, (1 << 63)-1) and start is not None and end > start), "invalid END clock")
    require(t["elapsedUs"] == (end - start if end is not None else None), "transfer duration summary mismatch")
    require(t["outcome"] != "ok" or end is not None, "successful transfer without END")
    sends, retries, latencies, early, early_invalid = {}, [], {}, {}, {}
    begins, durable, writes, chunks, control_starts, control_ends = [], [], [], [], [], []
    pending_controls = []
    awaiting = 0
    for index, kind, at, fields in samples(messages):
        require(at >= 0, "negative timing sample; never clamp to zero")
        if kind.startswith("segment_"):
            require(set(fields) == {"off", "len"} and start is not None and at >= start, "DATA sample fields/clock")
            off, length = fields["off"], fields["len"]
            require(off % 128 == 0 and 0 <= off < total and length == min(128, total - off), "DATA bounds")
            if kind == "segment_first_send":
                require(off not in sends, "duplicate first DATA sample")
                sends[off] = (at, length)
            else:
                require(kind == "segment_retransmit" and off in sends and at >= sends[off][0], "invalid retransmission")
                retries.append(off)
            if "dataBatch" in t:
                require(awaiting > 0 and chunks[-1]["at"] <= at, "missing/reordered DATA completion group")
                awaiting -= 1
            require(end is None or at <= end, "DATA sample from another clock/binding")
        elif kind in ("ack_latency", "ack_early", "ack_early_invalid"):
            require(set(fields) == {"off"}, "ACK timing fields")
            target = {"ack_latency": latencies, "ack_early": early, "ack_early_invalid": early_invalid}[kind]
            off = fields["off"]
            require(off not in target and off % 128 == 0 and 0 <= off < total, "duplicate/out-of-bounds ACK sample")
            target[off] = at
        elif kind == "durable":
            require(set(fields) == {"off"} and uint(fields["off"], total) and
                    (fields["off"] == total or fields["off"] % 4096 == 0), "durable sample fields")
            require(not durable or (fields["off"] > durable[-1][1] and at >= durable[-1][0]), "nonmonotonic durable samples")
            durable.append((at, fields["off"]))
        elif kind == "begin_ack":
            require(set(fields) == {"protocol", "session", "seq", "epoch", "off", "bitmap", "ackTimeoutMs", "maxRetries", "windowSegments"},
                    "BEGIN observation fields")
            require(fields["protocol"] in (1, 2) and 1 <= fields["session"] <= 255 and uint(fields["seq"], 65535) and
                    uint(fields["epoch"]) and (fields["protocol"] != 2 or fields["epoch"] > 0) and
                    uint(fields["off"], total) and (fields["off"] == total or fields["off"] % 4096 == 0) and
                    uint(fields["bitmap"]) and 500 <= fields["ackTimeoutMs"] <= 2000 and uint(fields["maxRetries"], 5) and
                    1 <= fields["windowSegments"] <= (24 if fields["protocol"] == 2 else 32), "BEGIN observation domain")
            begins.append(dict(us=at, **fields))
        elif kind in ("control_start", "control_end"):
            require(set(fields) == {"cmd", "session", "seq", "bytes"} and
                    CONTROL_BYTES.get(fields["cmd"]) == fields["bytes"] and
                    uint(fields["session"], 255) and uint(fields["seq"], 65535), "control wire geometry")
            if kind == "control_start":
                pending_controls.append((fields, at))
                control_starts.append((fields, at))
            else:
                require(pending_controls and pending_controls[0][0] == fields and at >= pending_controls[0][1],
                        "missing/duplicate control write")
                pending_controls.pop(0)
                control_ends.append((fields, at))
        elif kind == "gatt_write":
            require(not awaiting and set(fields) <= {"bytes", "error"} and uint(fields.get("bytes"), 65535) and
                    fields.get("error", 0) in (0, 1), "GATT sample fields/completion group")
            writes.append(dict(us=at, bytes=fields["bytes"], error=fields.get("error", 0), assigned=False))
        elif kind == "batch_chunk":
            require(set(fields) == {"bytes", "frames"} and not awaiting and writes and not writes[-1]["assigned"] and
                    fields["bytes"] == writes[-1]["bytes"] and 0 <= fields["frames"] <= 12, "batch/GATT association")
            writes[-1]["assigned"] = True
            awaiting = fields["frames"]
            chunks.append(dict(at=at, **fields, us=writes[-1]["us"]))
    require(not awaiting, "missing final DATA completions")
    if begins:
        require(t.get("begin") == {"first": begins[0], "count": len(begins)}, "BEGIN raw/summary mismatch")
        protocol, initial = begins[0]["protocol"], begins[0]["off"]
        require(all(b["protocol"] == protocol and b["ackTimeoutMs"] == begins[0]["ackTimeoutMs"] and
                    b["maxRetries"] == begins[0]["maxRetries"] and b["windowSegments"] == begins[0]["windowSegments"]
                    for b in begins), "conflicting effective configuration")
        if stamp["schema"] >= 10:
            require(stamp["ackTimeoutMs"] == begins[0]["ackTimeoutMs"], "requested/effective ACK timeout differs")
    else:
        require(historical or (t["outcome"] == "fail" and not sends), "actual BEGIN state missing")
        initial = None
        count = len(sends) + len(retries)
        data_bytes = sum(c["bytes"] for c in chunks)
        payload_bytes = sum(v[1] for v in sends.values()) + sum(sends[o][1] for o in retries)
        overhead = (data_bytes - payload_bytes) // count if count else None
        protocol = {14: 1, 18: 2}.get(overhead)
    require(protocol in (1, 2) or not sends, "unrecognized DATA wire version")
    require(t["segmentsUnique"] == len(sends) and t["segmentSendTotal"] == len(sends) + len(retries) and
            t["retransmitFrames"] == len(retries), "DATA count summary mismatch")
    require(set(latencies) <= set(sends) and set(early_invalid) <= set(sends) and
            set(early_invalid) <= set(early) and not set(latencies) & set(early), "ACK origin/early overlap")
    for off, latency in latencies.items():
        require(end is None or sends[off][0] + latency <= end, "ACK sample from a different clock")
    for off, at in early_invalid.items():
        require(early[off] == at <= sends[off][0], "early ACK must not be manufactured as a zero latency")
    if protocol == 2 and begins:
        for off, (sent, length) in sends.items():
            confirmations = [at for at, value in durable if value >= off + length]
            if not confirmations:
                require(off not in latencies and off not in early, "ACK has no durable confirmation")
                continue
            first = confirmations[0]
            if off in early:
                require(early[off] == first and off in early_invalid, "wrong first early durable ACK")
            elif off in latencies:
                require(latencies[off] == first - sent >= 0, "wrong first durable ACK latency")
    missing = len(sends) - len(latencies)
    integrity = []
    if missing: integrity.append("missing=" + str(missing))
    if early_invalid: integrity.append("early=" + str(len(early_invalid)))
    require(t["ackSamples"] == ("partial:" + ",".join(integrity) if integrity else "complete") and
            t["ackEarlyInvalid"] == len(early_invalid) and
            t["ackEarlyUnsent"] == len(set(early) - set(sends)), "ACK completeness summary mismatch")
    require(t["ackLatency"] == distribution(list(latencies.values())), "ACK percentile summary mismatch")
    require(t["durable"] == dict(events=len(durable), finalOff=durable[-1][1] if durable else None),
            "durable summary mismatch")
    gatt = summary["gattWrites"]
    require(gatt["calls"] == len(writes) and gatt["bytes"] == sum(w["bytes"] for w in writes) and
            gatt["errors"] == sum(w["error"] for w in writes), "GATT count/byte summary mismatch")
    for key, value in distribution([w["us"] for w in writes]).items():
        if key not in ("count", "p99Us"):
            require(gatt[key] == value, "GATT distribution summary mismatch")
    wire_data = sum(length + (18 if protocol == 2 else 14) for _, length in sends.values()) + sum(
        sends[off][1] + (18 if protocol == 2 else 14) for off in retries)
    if "dataBatch" in t:
        batch = t["dataBatch"]
        require(batch["schema"] == 1 and batch["chunks"] == len(chunks) and
                batch["bytes"] == sum(c["bytes"] for c in chunks) and batch["maxFrames"] in (3, 12) and
                all(c["frames"] <= batch["maxFrames"] for c in chunks), "batch summary mismatch")
        require(stamp.get("dataBatchFrames") == batch["maxFrames"], "runtime/batch mismatch")
        if t["outcome"] == "ok":
            require(batch["bytes"] == wire_data, "DATA wire byte count mismatch")
    if t["outcome"] == "ok":
        require(durable and durable[-1][1] == total, "no final durable confirmation")
        if not historical:
            end_cmd, begin_cmd = ((0x13, 0x11) if protocol == 2 else (3, 1))
            require(not pending_controls and any(f["cmd"] == begin_cmd for f, _ in control_ends) and
                    any(f["cmd"] == end_cmd for f, _ in control_ends), "missing successful BEGIN/END write")
            require(gatt["errors"] == 0 and gatt["bytes"] == wire_data + sum(f["bytes"] for f, _ in control_ends),
                    "DATA/control/query/ABORT byte accounting mismatch")
        else:
            controls = [w["bytes"] for w in writes if not w["assigned"]]
            require(sum(controls) + wire_data == gatt["bytes"], "historical wire byte count mismatch")
    mono = {}
    for line in messages:
        match = re.fullmatch(r"OTA_MONO (MONO_BUDGET_START|MONO_END_ACK_OK|MONO_REBOOT_VERIFIED) monoUs=(\d+) wallUs=\d+(?: .*)?", line)
        if match:
            require(match[1] not in mono, "duplicate public monotonic endpoint")
            mono[match[1]] = int(match[2])
    if success:
        require(set(mono) == {"MONO_BUDGET_START", "MONO_END_ACK_OK", "MONO_REBOOT_VERIFIED"} and
                mono["MONO_BUDGET_START"] < mono["MONO_END_ACK_OK"] <= mono["MONO_REBOOT_VERIFIED"],
                "missing END/reboot or mixed public clock")
    full = (initial == 0 and begins[0]["bitmap"] == 0 and len(begins) == 1 and
            list(sends) == list(range(0, total, 128))) if begins else False
    ack_eligible = bool(not historical and success and full and sends and missing == 0)
    params = {key: stamp.get(key) for key in GROUP_FIELDS}
    params.update(protocol=protocol, ackTimeoutMs=begins[0]["ackTimeoutMs"] if begins else stamp.get("ackTimeoutMs"),
                  maxRetries=begins[0]["maxRetries"] if begins else None,
                  sentinel=envelope["sentinel"], platform=envelope["platform"],
                  input={k: v for k, v in envelope["input"].items() if k != "appLifecycle"},
                  mtuChunkBytes=summary.get("bind", {}).get("mtuChunkBytes"),
                  writeMode=summary.get("bind", {}).get("writeMode"))
    params["requestedWindowSegments"] = stamp.get("senderWindowSegments")
    params["requestedDataBatchFrames"] = stamp.get("dataBatchFrames")
    if begins: params["senderWindowSegments"] = begins[0]["windowSegments"]
    params["dataBatchFrames"] = t.get("dataBatch", {}).get("maxFrames", 1)
    params["input"]["deviceAddress"] = params["input"]["deviceAddress"].lower()
    elapsed = t["elapsedUs"]
    ignored = t["acks"].get("ignoredErrors", {}).get("counts", {})
    clean = (not any(t["acks"].get(k, 0) for k in ("error", "malformed", "noProgress", "abort")) and
             "firstError" not in t["acks"] and not ignored and not envelope["ackErrorObservations"]["ignored"])
    return dict(captureId=envelope["captureId"], rawSha256=envelope["rawSha256"], parameters=params,
        success=success, transferOutcome=t["outcome"], initialDurable=initial,
        firstSentOffset=next(iter(sends), None), finalDurable=durable[-1][1] if durable else None,
        fullZeroStart=full, reference=total == 1048576, historical=historical, clean=clean,
        transferUs=elapsed, publicTransferUs=mono.get("MONO_END_ACK_OK", 0) - mono["MONO_BUDGET_START"]
            if "MONO_END_ACK_OK" in mono and "MONO_BUDGET_START" in mono else None,
        throughputKiBs=total * 1000000 / (1024 * elapsed) if elapsed and full else None,
        dataFrames=len(sends), dataSendTotal=len(sends) + len(retries), retransmitFrames=len(retries),
        retransmitRate=len(retries) / (len(sends) + len(retries)) if sends else None,
        missingAckSamples=missing, earlyAckSamples=len(early_invalid), ackSamplesUs=list(latencies.values()),
        ackEligible=ack_eligible, observedAckP99Us=rank(list(latencies.values()), 99),
        failure=summary.get("failure"), ignoredAckErrors=envelope["ackErrorObservations"],
        scope="App-local clock only; UART/staging requires matching production MCU metrics; no time sums are removable cost")


def inspect(data, sentinel, target, *, historical=False):
    envelope, messages = verify(data, sentinel=sentinel, target=target)
    return analyze(envelope, messages.splitlines(), historical=historical)


def aggregate(runs, *, expected_count):
    require(uint(expected_count) and expected_count > 0 and len(runs) == expected_count,
            "every planned attempt, including missing/failed, must remain listed")
    groups = {}
    ids, captures, hashes = set(), set(), set()
    gaps = []
    for run in runs:
        require(run["id"] not in ids, "duplicate planned run ID")
        ids.add(run["id"])
        if "gap" in run:
            gaps.append(dict(id=run["id"], gap=run["gap"]))
            continue
        value = run["observation"]
        require(value["captureId"] not in captures and value["rawSha256"] not in hashes, "duplicate original capture")
        captures.add(value["captureId"])
        hashes.add(value["rawSha256"])
        key = json.dumps(value["parameters"], sort_keys=True, separators=(",", ":"))
        groups.setdefault(key, []).append(run)
    results = []
    for key, entries in groups.items():
        values = [e["observation"] for e in entries]
        samples_all = [sample for v in values for sample in v["ackSamplesUs"]]
        eligible = not gaps and all(v["success"] and v["ackEligible"] and v["clean"] for v in values)
        p99 = rank(samples_all, 99)
        full = [v for v in values if v["success"] and v["fullZeroStart"] and v["reference"]]
        durations = [v["transferUs"] for v in full]
        p95 = rank(durations, 95)
        stability = (len(entries) == expected_count == 30 and len(full) == 30 and not gaps and eligible and
            all(v["transferUs"] <= 150000000 and v["throughputKiBs"] >= 9 and
                v["retransmitRate"] <= .01 for v in full) and p95 <= 120000000)
        results.append(dict(parameters=json.loads(key), attempts=len(entries),
            ids=[e["id"] for e in entries], successes=sum(v["success"] for v in values),
            failures=sum(not v["success"] for v in values), fullReferenceSuccesses=len(full),
            missingAckSamples=sum(v["missingAckSamples"] for v in values),
            earlyAckSamples=sum(v["earlyAckSamples"] for v in values),
            observedAckP99Us=p99, ackP99Eligible=eligible,
            recommendedAckTimeoutMs=min(2000, max(500, (3 * p99 + 999) // 1000)) if eligible and p99 is not None else None,
            fullReferenceP95Us=p95, stability30MeetsObservedGates=stability))
    recoveries = {}
    for run in runs:
        case = run.get("recoveryCase")
        if case is None: continue
        require(run.get("role") in ("disconnect", "resume"), "recovery must distinguish disconnect/resume")
        pair = recoveries.setdefault(case, {})
        require(run["role"] not in pair, "duplicate recovery role")
        pair[run["role"]] = run.get("observation")
    recovery_ok = 0
    for pair in recoveries.values():
        a, b = pair.get("disconnect"), pair.get("resume")
        if not a or not b: continue
        reason = (a.get("failure") or {}).get("reason")
        recovery_ok += bool(not a["success"] and reason in ("DISCONNECTED", "DEVICE_LINK_CHANGED") and
            b["success"] and a["parameters"] == b["parameters"] and
            a["finalDurable"] == b["initialDurable"] and (b["initialDurable"] or 0) > 0)
    return dict(plannedAttempts=expected_count, observedAttempts=len(captures), evidenceGaps=gaps, groups=results,
        recoveryCases=len(recoveries), successfulRecoveries=recovery_ok,
        recovery10MeetsObservedGates=len(recoveries) == recovery_ok == 10 and not gaps,
        independentAcceptance="NOT_RUN", soakDurationSeconds=None,
        scope="All listed attempts retained; groups never mix baud/timeout/retry/MTU/assets/APK. "
              "Soak wall duration and physical disconnect actions require the frozen host/controller evidence, not summed App clocks.")


def read_plan(path):
    require(path.stat().st_size <= 4 * 1024 * 1024, "oversized run plan")
    plan = decode(path.read_bytes())
    require(set(plan) == {"schema", "expectedCount", "runs"} and plan["schema"] == 1 and isinstance(plan["runs"], list),
            "run plan schema")
    runs = []
    for item in plan["runs"]:
        require(set(item) <= {"id", "input", "sha256", "sentinel", "target", "role", "recoveryCase"} and
                {"id", "input", "sha256", "sentinel", "target"} <= set(item) and
                isinstance(item["id"], str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", item["id"]), "planned input fields")
        row = {k: item[k] for k in ("id", "role", "recoveryCase") if k in item}
        try:
            require(item["input"] is not None and digest(item["sha256"]), "planned original not captured")
            source = path.parent / item["input"]
            require(source.stat().st_size <= MAX_BYTES + 8192, "oversized snapshot")
            raw = source.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == item["sha256"], "original snapshot hash differs")
            row["observation"] = inspect(raw, item["sentinel"], item["target"])
        except (ValueError, KeyError, TypeError, OSError) as error:
            row["gap"] = str(error)
        runs.append(row)
    result = aggregate(runs, expected_count=plan["expectedCount"])
    result["runs"] = runs
    result["planSha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path)
    group.add_argument("--plan", type=Path)
    parser.add_argument("--expect-sentinel")
    parser.add_argument("--expect-target")
    parser.add_argument("--historical", action="store_true")
    args = parser.parse_args()
    if args.plan:
        require(not args.historical, "historical runs cannot enter a formal plan")
        result = read_plan(args.plan)
    else:
        require(args.input.stat().st_size <= MAX_BYTES + 8192, "oversized snapshot")
        result = inspect(args.input.read_bytes(), args.expect_sentinel, args.expect_target, historical=args.historical)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise SystemExit("P34_STATS_REJECTED: " + str(error))
