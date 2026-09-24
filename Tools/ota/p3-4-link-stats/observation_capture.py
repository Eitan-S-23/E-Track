"""Verify an App-owned P3-4 snapshot before unwrapping its original messages.

A valid envelope is not throughput acceptance. UART baud, APK/source binding,
measurement grouping and the existing statistics parser remain separate gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
MAX_BYTES = 64 * 1024 * 1024
PREFIXES = ("OTA_LINK_SAMPLE ", "OTA_LINK_STATS ", "OTA_LINK_RETIRE ",
            "OTA_LINK_LATE ", "OTA_MONO ", "OTA_IDENTITY ", "OTA_EXPERIMENT ",
            "OTA_PREFIX_PROBE ")
INPUT_FIELDS = {"packageSha256", "packageBytes", "currentVersionCode",
                "currentImageSha256", "targetVersionCode", "targetImageSha256",
                "deviceAddress", "appLifecycle"}
FOOTER_FIELDS = {"kind", "schema", "captureId", "records", "bytes", "producerLines",
                 "upgradeStarts", "upgradeEnds", "outcome", "lost", "error", "healthy",
                 "sha256", "exportedAt"}


class CaptureError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise CaptureError(reason)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON field")
        result[key] = value
    return result


def decode(data):
    try:
        value = json.loads(data, object_pairs_hook=strict_object,
                           parse_constant=lambda _: require(False, "non-finite number"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CaptureError("invalid UTF-8/JSON") from error
    require(isinstance(value, dict), "JSON record must be an object")
    return value


def uint(value, maximum=0xFFFFFFFF):
    return type(value) is int and 0 <= value <= maximum


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_input(value):
    require(isinstance(value, dict) and set(value) == INPUT_FIELDS, "input identity fields")
    for key in ("packageSha256", "currentImageSha256", "targetImageSha256"):
        require(digest(value[key]), "input SHA-256 domain")
    for key in ("currentVersionCode", "targetVersionCode", "packageBytes"):
        require(uint(value[key]), "input integer domain")
    require(value["packageBytes"] >= 64, "input package length")
    require(isinstance(value["deviceAddress"], str) and re.fullmatch(r"[a-zA-Z0-9:._-]{1,128}",
            value["deviceAddress"]), "device address domain")
    require(value["appLifecycle"] in ("resumed", "inactive", "paused", "hidden", "detached", "unknown"),
            "lifecycle must be observed, not guessed")


def verify(data: bytes, *, sentinel: str, target: str, require_upgrade=True, require_prefix_probe=False):
    require(0 < len(data) <= MAX_BYTES + 8192 and data.endswith(b"\n"), "size or final line terminator")
    require(not data.startswith(b"\xef\xbb\xbf"), "BOM is not part of the format")
    raw_lines = data.splitlines(keepends=True)
    require(len(raw_lines) >= 2 and all(line.endswith(b"\n") and b"\r" not in line and
            len(line) <= 65536 for line in raw_lines), "record boundaries or record size")
    footer = decode(raw_lines[-1])
    require(set(footer) == FOOTER_FIELDS and footer["kind"] == "snapshot" and
            type(footer["schema"]) is int and footer["schema"] == 1, "snapshot footer/schema")
    prefix = b"".join(raw_lines[:-1])
    require(uint(footer["bytes"], MAX_BYTES) and footer["bytes"] == len(prefix), "prefix byte count")
    require(digest(footer["sha256"]) and hashlib.sha256(prefix).hexdigest() == footer["sha256"],
            "prefix SHA-256 mismatch")
    require(uint(footer["records"]) and footer["records"] == len(raw_lines)-1, "record count")
    require(type(footer["healthy"]) is bool and footer["healthy"] and footer["error"] is None and
            type(footer["lost"]) is int and footer["lost"] == 0, "capture reports lost/failed observations")

    header, messages, inputs, outcomes = None, [], [], []
    for index, raw in enumerate(raw_lines[:-1], 1):
        row = decode(raw)
        require(type(row.get("seq")) is int and row["seq"] == index, "missing/reordered/duplicate sequence")
        kind = row.get("kind")
        if index == 1:
            require(set(row) == {"seq", "kind", "schema", "captureId", "sentinel", "target",
                                "pid", "platform", "openedAt", "limits"} and kind == "open", "capture header")
            require(type(row["schema"]) is int and row["schema"] == 1, "header schema")
            require(isinstance(row["captureId"], str) and re.fullmatch(r"\d{13,20}-[0-9a-f]{24}", row["captureId"]),
                    "capture identity")
            require(row["captureId"] == footer["captureId"], "mixed capture identities")
            require(isinstance(sentinel, str) and re.fullmatch(r"OTAOBS[0-9a-f]{24}", sentinel) and
                    row["sentinel"] == sentinel and row["target"] == target, "wrong APK sentinel/target")
            require(uint(row["pid"]) and row["pid"] > 0 and row["platform"] in
                    ("android", "ios", "windows", "linux", "macos"), "process/platform identity")
            require(isinstance(row["limits"], dict) and set(row["limits"]) == {"captureBytes", "pendingBytes"} and
                    uint(row["limits"]["captureBytes"], MAX_BYTES) and
                    1024 <= row["limits"]["captureBytes"] and len(prefix) <= row["limits"]["captureBytes"],
                    "capture capacity declaration")
            header = row
        elif kind == "line":
            require(set(row) == {"seq", "kind", "message"}, "message fields")
            line = row["message"]
            require(isinstance(line, str) and line.startswith(PREFIXES) and
                    not any(c in line for c in ("\r", "\n", "\0")) and
                    len(line.encode("utf-8")) <= 16384, "not an allowed App observation")
            require(not re.search(r"https?://|authorization\s*:|(?:token|signature|api_key)=", line, re.I),
                    "credential-shaped observation")
            messages.append(line)
        elif kind == "upgrade-start":
            require(set(row) == {"seq", "kind", "input"} and not inputs and not outcomes, "multiple/late upgrade starts")
            validate_input(row["input"])
            inputs.append(row["input"])
        elif kind == "upgrade-end":
            require(set(row) == {"seq", "kind", "outcome"} and len(inputs) == 1 and not outcomes and
                    row["outcome"] in ("completed", "not-completed"), "upgrade end without one start")
            outcomes.append(row["outcome"])
        else:
            raise CaptureError("unknown or repeated record kind")
    for key, expected in (("producerLines", len(messages)), ("upgradeStarts", len(inputs)),
                          ("upgradeEnds", len(outcomes))):
        require(type(footer[key]) is int and footer[key] == expected, "footer counter mismatch: " + key)
    require(footer["outcome"] == (outcomes[0] if outcomes else None), "footer outcome mismatch")
    require(messages, "no actual App-origin observations; a header/host marker is insufficient")
    require(len(inputs) == len(outcomes), "unfinished business invocation")
    require(not require_upgrade or len(inputs) == 1, "no completed invocation record")

    if outcomes == ["completed"]:
        identities = {}
        for line in messages:
            if line.startswith("OTA_IDENTITY "):
                item = decode(line[len("OTA_IDENTITY "):])
                require(set(item) == {"phase", "versionCode", "imageSha256", "deviceAddress"} and
                        item["phase"] in ("pre-transfer", "post-reboot") and item["phase"] not in identities,
                        "identity phase/count")
                identities[item["phase"]] = item
        require(set(identities) == {"pre-transfer", "post-reboot"}, "actual before/after GET_INFO identities missing")
        for phase, version, sha in (("pre-transfer", "currentVersionCode", "currentImageSha256"),
                                    ("post-reboot", "targetVersionCode", "targetImageSha256")):
            item = identities[phase]
            require(type(item["versionCode"]) is int and item["versionCode"] == inputs[0][version] and
                    item["imageSha256"] == inputs[0][sha] and item["deviceAddress"] == inputs[0]["deviceAddress"],
                    "observed identity mismatch")
        for event in ("MONO_BUDGET_START", "MONO_END_ACK_OK", "MONO_REBOOT_VERIFIED"):
            require(sum(line.startswith("OTA_MONO " + event + " ") for line in messages) == 1,
                    "success is missing an unambiguous sender event: " + event)
    result = dict(schema=1, captureId=header["captureId"], sentinel=sentinel, target=target,
                  pid=header["pid"], platform=header["platform"], records=footer["records"],
                  producerLines=len(messages), input=inputs[0] if inputs else None,
                  outcome=outcomes[0] if outcomes else None, rawSha256=hashlib.sha256(data).hexdigest(),
                  eligibleForThreshold=False, independentAcceptance="NOT_RUN",
                  scope="envelope/identity integrity only; original timing/grouping gates still required")
    if require_prefix_probe:
        result["prefixProbe"] = verify_prefix_probe(result, messages)
        result["scope"] = "durable-prefix diagnostic only; no END, installation or full-ETU throughput acceptance"
    return result, "".join(line + "\n" for line in messages)


def verify_prefix_probe(envelope, messages):
    """Validate the App verdict against its input and original sender records."""
    require(envelope["outcome"] == "not-completed" and envelope["input"] is not None,
            "prefix probe must not claim a completed upgrade")

    def one(prefix):
        values = [decode(line[len(prefix):]) for line in messages if line.startswith(prefix)]
        require(len(values) == 1, "one original record required: " + prefix.strip())
        return values[0]

    probe = one("OTA_PREFIX_PROBE ")
    experiment = one("OTA_EXPERIMENT ")
    fields = {"schema", "outcome", "prefixBytes", "sentUniqueBytes", "uniqueSegments", "sentTotalBytes",
              "senderWindowSegments", "beginWriteUs", "durableAckUs", "abortWriteUs", "abortAckUs",
              "elapsedUs", "abortElapsedUs", "session", "abortSeq", "abortStatus", "durableOff",
              "blockBitmap", "endSent", "runId", "configSha256", "deviceAddress", "sourceVersionCode",
              "sourceImageSha256", "sourceIdentityVerified"}
    require(set(probe) == fields and type(probe["schema"]) is int and probe["schema"] == 1 and
            probe["outcome"] == "durable-prefix-aborted", "prefix verdict schema")
    numbers = fields - {"outcome", "endSent", "runId", "configSha256", "deviceAddress",
                        "sourceImageSha256", "sourceIdentityVerified"}
    require(all(uint(probe[key], (1 << 63)-1) for key in numbers), "prefix numeric fields")
    size = probe["prefixBytes"]
    require(4096 <= size <= 32768 and size % 4096 == 0 and size < envelope["input"]["packageBytes"] and
            probe["sentUniqueBytes"] == probe["durableOff"] == size and
            probe["uniqueSegments"] == size // 128 and probe["sentTotalBytes"] >= size and
            probe["sentTotalBytes"] % 128 == 0, "prefix DATA coverage")
    require(1 <= probe["senderWindowSegments"] <= 32 and 1 <= probe["session"] <= 255 and
            probe["abortSeq"] <= 65535 and probe["abortStatus"] == 255 and probe["blockBitmap"] == 0 and
            probe["endSent"] is False and probe["sourceIdentityVerified"] is True, "prefix closure")
    require(probe["beginWriteUs"] < probe["durableAckUs"] <= probe["abortWriteUs"] <= probe["abortAckUs"] and
            probe["elapsedUs"] == probe["durableAckUs"] - probe["beginWriteUs"] and
            probe["abortElapsedUs"] == probe["abortAckUs"] - probe["abortWriteUs"], "prefix timing")
    expected_fields = {"schema", "runId", "configSha256", "requestedBaud", "reuseGatt", "withoutResponse",
                       "endpointHost", "deviceAddress", "packageBytes", "packageSha256", "currentVersionCode",
                       "currentImageSha256", "targetVersionCode", "targetImageSha256", "senderWindowSegments",
                       "transferMode", "prefixBytes"}
    require(set(experiment) == expected_fields and type(experiment["schema"]) is int and
            experiment["schema"] == 2 and experiment["transferMode"] == "prefix" and
            type(experiment["prefixBytes"]) is int and experiment["prefixBytes"] == size and
            type(experiment["senderWindowSegments"]) is int and
            probe["senderWindowSegments"] <= experiment["senderWindowSegments"] <= 32 and
            type(experiment["requestedBaud"]) is int and experiment["requestedBaud"] in (115200, 460800, 921600) and
            type(experiment["reuseGatt"]) is bool and type(experiment["withoutResponse"]) is bool,
            "prefix experiment profile")
    require(isinstance(experiment["endpointHost"], str) and re.fullmatch(
        r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", experiment["endpointHost"]), "prefix endpoint host")
    require(isinstance(probe["runId"], str) and re.fullmatch(r"[a-z][a-z0-9-]{0,47}", probe["runId"]) and
            digest(probe["configSha256"]) and probe["runId"] == experiment["runId"] and
            probe["configSha256"] == experiment["configSha256"], "prefix config binding")
    source = envelope["input"]
    for key in INPUT_FIELDS - {"appLifecycle"}:
        require(type(experiment[key]) is type(source[key]) and experiment[key] == source[key],
                "prefix experiment input binding: " + key)
    require(probe["deviceAddress"] == source["deviceAddress"] and
            probe["sourceVersionCode"] == source["currentVersionCode"] and
            probe["sourceImageSha256"] == source["currentImageSha256"], "prefix retained identity")
    identity = one("OTA_IDENTITY ")
    require(set(identity) == {"phase", "versionCode", "imageSha256", "deviceAddress"} and
            identity["phase"] == "pre-transfer" and type(identity["versionCode"]) is int and
            identity["versionCode"] == source["currentVersionCode"] and
            identity["imageSha256"] == source["currentImageSha256"] and
            identity["deviceAddress"] == source["deviceAddress"], "prefix initial identity")
    require(not any(line.startswith(("OTA_MONO MONO_END_ACK_OK ", "OTA_MONO MONO_REBOOT_VERIFIED "))
                    for line in messages), "prefix cannot include END/reboot success")
    require(sum(line.startswith("OTA_MONO MONO_BUDGET_START ") for line in messages) == 1,
            "prefix sender start missing/ambiguous")

    summaries = [decode(line[len("OTA_LINK_STATS "):]) for line in messages if line.startswith("OTA_LINK_STATS ")]
    summaries = [value for value in summaries if value.get("label") == "prefix-probe"]
    require(len(summaries) == 1 and isinstance(summaries[0].get("transfer"), dict), "prefix link summary")
    transfer = summaries[0]["transfer"]
    require(transfer.get("outcome") == "fail" and transfer.get("endAckUs") is None and
            transfer.get("elapsedUs") is None and type(transfer.get("startUs")) is int and
            transfer["startUs"] == probe["beginWriteUs"] and
            type(transfer.get("segmentsUnique")) is int and transfer["segmentsUnique"] == size // 128 and
            type(transfer.get("segmentSendTotal")) is int and
            transfer["segmentSendTotal"] * 128 == probe["sentTotalBytes"], "prefix/full-transfer accounting")
    samples, durable = set(), set()
    for line in messages:
        match = re.fullmatch(r"OTA_LINK_SAMPLE label=prefix-probe kind=segment_(first_send|retransmit) "
                             r"us=(\d+) off=(\d+) len=(\d+)", line)
        if match:
            offset, length = int(match[3]), int(match[4])
            require(offset % 128 == 0 and 0 <= offset < size and length == 128, "prefix raw DATA bounds")
            if match[1] == "first_send": samples.add(offset)
        match = re.fullmatch(r"OTA_LINK_SAMPLE label=prefix-probe kind=durable us=\d+ off=(\d+)", line)
        if match: durable.add(int(match[1]))
    require(samples == set(range(0, size, 128)) and durable == set(range(0, size+1, 4096)),
            "prefix original DATA/durable observations incomplete")
    return probe


def checked(path):
    path = Path(path).absolute()
    try:
        path.resolve(strict=False).relative_to(ROOT.resolve(strict=True))
    except ValueError as error:
        raise CaptureError("output outside the active worktree") from error
    for parent in (path, *path.parents):
        if parent.exists() or parent.is_symlink():
            info = parent.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 1024,
                    "output reparse point")
    return path


def extract(source, out, sentinel, target, *, require_prefix_probe=False):
    out = checked(out)
    require(not out.exists(), "preserve existing extraction")
    for name in ("observations.log", "capture.json"):
        checked(out / name)
    require(source.stat().st_size <= MAX_BYTES + 8192, "oversize input")
    data = source.read_bytes()
    result, messages = verify(data, sentinel=sentinel, target=target, require_prefix_probe=require_prefix_probe)
    out.mkdir(parents=True)
    with (out / "observations.log").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(messages)
    result["unwrappedSha256"] = hashlib.sha256(messages.encode()).hexdigest()
    result["sourcePath"] = str(source.resolve())
    with (out / "capture.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "extract"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expect-sentinel", required=True)
    parser.add_argument("--expect-target", required=True)
    parser.add_argument("--out-root", type=Path)
    parser.add_argument("--require-prefix-probe", action="store_true")
    args = parser.parse_args()
    if args.mode == "extract":
        require(args.out_root is not None, "explicit output root required")
        require(Path.cwd().resolve() == ROOT and sys.dont_write_bytecode, "active worktree and Python -B required")
        result = extract(args.input, args.out_root, args.expect_sentinel, args.expect_target,
                         require_prefix_probe=args.require_prefix_probe)
    else:
        require(args.out_root is None, "inspect is read-only")
        require(args.input.stat().st_size <= MAX_BYTES + 8192, "oversize input")
        result, _ = verify(args.input.read_bytes(), sentinel=args.expect_sentinel,
                           target=args.expect_target, require_upgrade=False,
                           require_prefix_probe=args.require_prefix_probe)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OSError) as error:
        print("CAPTURE_REJECTED: " + str(error), file=sys.stderr)
        raise SystemExit(2)
