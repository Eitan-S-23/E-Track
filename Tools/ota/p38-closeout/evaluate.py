"""P3-8 v5 offline evidence evaluation. Never builds, downloads or accesses devices."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "Tools/ota/p3-4-link-stats")]
import acceptance_stats as stats
from Tools.flutter import ota_link_profile

spec = importlib.util.spec_from_file_location("p38_host_io", ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)
BUNDLE = ROOT / "docs/acceptance-contracts/P3-8-v5"
CACHE = ROOT / ".cache/p38-closeout-20261026/reviewer"
SOURCE = "410b7d57c7ed918103986f42a30af80960506826"
CRITERIA = ("SOFTWARE", "FALLBACK", "BACKGROUND", "NOTIFICATION", "RECOVERY", "FINAL-IDENTITY", "CLEANUP")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def output(path):
    path = io.checked_output(ROOT, path)
    require(path.is_relative_to(BUNDLE) or path.is_relative_to(CACHE), "output outside closeout scope")
    return path


def write(path, data):
    path = output(path)
    output(path.parent).mkdir(parents=True, exist_ok=True)
    with output(path).open("xb") as stream:
        stream.write(data)
    return dict(path=path.relative_to(BUNDLE).as_posix() if path.is_relative_to(BUNDLE) else str(path),
                bytes=len(data), sha256=sha(data))


def write_json(path, value):
    return write(path, (json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def read(item, base=BUNDLE):
    require(isinstance(item, dict) and {"path", "bytes", "sha256"} <= item.keys(), "unbound input")
    p = Path(item["path"])
    require(not p.is_absolute() and ".." not in p.parts, "nonportable evidence path")
    p = io.checked_output(base, base / p)
    data = p.read_bytes()
    require(len(data) == item["bytes"] and sha(data) == item["sha256"], "input identity mismatch: " + item["path"])
    return data


def json_input(item, base=BUNDLE):
    return json.loads(read(item, base))


def git(*args):
    result = subprocess.run(["git", "--no-optional-locks", *args], cwd=ROOT,
                            capture_output=True, timeout=45, check=True)
    return result.stdout


def snapshot(item, binding, base=BUNDLE):
    data = read(item, base)
    header = json.loads(data.splitlines()[0])
    require(re.fullmatch(r"[0-9a-f]{64}", binding["apk_sha256"]), "APK identity not bound")
    require(header["pid"] == binding["pid"] and header["captureId"] == binding["capture"], "external capture/PID differs")
    value = stats.inspect(data, binding["sentinel"], binding["target"])
    rows = [json.loads(line) for line in data.splitlines()]
    messages = [r["message"] for r in rows if isinstance(r.get("message"), str)]
    return data, header, value, messages


def firmware(raw):
    require(len(raw) >= 0x460, "short App read")
    header = raw[0x400:0x460]
    require(header[:4] == b"ETFW" and struct.unpack_from("<I", header, 4)[0] == 1, "firmware header")
    require(zlib.crc32(header[:92]) == struct.unpack_from("<I", header, 92)[0], "firmware header CRC")
    length = struct.unpack_from("<I", header, 36)[0]
    require(0x460 <= length <= min(len(raw), 0xf0000), "App bounds")
    image = bytearray(raw[:length])
    image[0x428:0x448], image[0x45c:0x460] = bytes(32), bytes(4)
    require(hashlib.sha256(image).digest() == header[40:72], "firmware embedded digest")
    return dict(version=struct.unpack_from("<I", header, 8)[0], bytes=length, sha256=sha(raw[:length]))


def recovery(disconnect, resumed):
    a, b = disconnect["parameters"]["input"], resumed["parameters"]["input"]
    require(a == b, "disconnect/resume package or device identity differs")
    require(not disconnect["success"] and resumed["success"], "disconnect/resume outcomes")
    require(0 < disconnect["finalDurable"] == resumed["initialDurable"] == resumed["firstSentOffset"]
            < resumed["finalDurable"] == a["packageBytes"], "receiver durable continuity")
    require(disconnect["captureId"] != resumed["captureId"], "same capture reused as recovery")
    return dict(initial=resumed["initialDurable"], final=resumed["finalDurable"],
                package=a["packageSha256"], explicit_resume=True, automatic_reconnect="NOT_INFERRED")


def active_lock(power, pid=None):
    lines = [line for line in power.splitlines() if re.search(rb"^\s*PARTIAL_WAKE_LOCK\s+['\"]trace:DeviceOta['\"]\s+ACQ=", line)]
    return any(pid is None or re.search(rb"\bpid=" + str(pid).encode() + rb"\)", line) for line in lines)


def native_terminal(power, services, notification=None):
    require(b"DeviceOtaService" not in services and not active_lock(power), "native resources remain")
    if notification is not None:
        require(not notification.strip(), "OTA notification remains")


def pause_order(messages):
    pauses = [n for n, m in enumerate(messages) if "MONO_PAUSE " in m]
    resumes = [n for n, m in enumerate(messages) if "MONO_RESUME " in m]
    require(pauses and resumes, "pause/resume markers absent")
    first, resumed = pauses[0], resumes[0]
    require(resumed > first, "pause/resume order")
    completed = [n for n in range(first + 1, resumed) if re.search(r"kind=segment_(?:first_send|retransmit) ", messages[n])]
    # Single-frame v1 awaits one write. Its completion observer may follow pause;
    # it is not a start observer and has a different clock origin from MONO.
    require(len(completed) <= 1, "multiple DATA completions during unowned background")
    quiet = [n for n in pauses if first <= n < resumed and (not completed or n > completed[-1])]
    require(quiet, "no observed paused interval after in-flight completion")
    return dict(pause_record=first, resume_record=resumed, quiet_pause_record=quiet,
                tail_completion_records=completed, completion_is_not_write_start=True,
                write_start_measurement="NOT_OBSERVED", cross_clock_subtraction="NOT_PERFORMED")


def test_counts(text):
    plain = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    compact = re.findall(r"\+(\d+)(?:\s+~(\d+))?(?:\s+-(\d+))?: All tests passed!", plain)
    require(not re.search(r"Some tests failed|\b\d+ tests failed", plain), "failed terminal summary")
    hosted = re.findall(r"(?m)^(?:\S+Z )?(?:\U0001f389 )?(\d+) tests passed(?:, (\d+) skipped)?\.\r?$", plain)
    require(not (compact and hosted), "mixed test reporters")
    if hosted:
        require(len(hosted) == 1, "ambiguous hosted test summary")
        return dict(passed=int(hosted[0][0]), skipped=int(hosted[0][1] or 0))
    require(len(compact) == 1 and not compact[0][2], "test summary missing/failed")
    return dict(passed=int(compact[0][0]), skipped=int(compact[0][1] or 0))


def notification_progress(raw, header, samples, package_bytes, intent, base=BUNDLE):
    rows = raw.splitlines(keepends=True)
    values, handles = [], []
    for sample in samples:
        health = json_input(sample["health"], base)
        require(health["healthy"] and not health["lost"] and not health["error"] and
                health["captureId"] == header["captureId"] and health["upgradeStarts"] == 1 and
                health["upgradeEnds"] == 0, "notification sample capture unhealthy/different")
        count = health["records"]
        require(type(count) is int and 0 < count <= len(rows) and
                len(b"".join(rows[:count])) == health["bytes"], "notification sample cutoff differs")
        require(read(sample["pid"], base).strip() == str(header["pid"]).encode(), "notification PID differs")
        durable = [int(match[1]) for line in rows[:count]
                   if (match := re.search(r"kind=durable us=\d+ off=(\d+)", json.loads(line).get("message", "")))]
        text = read(sample["notification"], base)
        progress = sorted(set(re.findall(rb"android.progress=Integer \((\d+)\)", text)))
        require(len(progress) == 1 and b"id=2408" in text and b"android.progressMax=Integer (100)" in text and
                b"android.progressIndeterminate=Boolean (false)" in text, "native progress missing")
        percentage = int(progress[0])
        require((b"Transferring (MCU durable confirmation): " + progress[0] + b"%") in text, "progress phase/text mismatch")
        matched = [off for off in durable if off * 100 // package_bytes == percentage]
        # Native dump precedes recorder health. Bound the observed sampling lag to
        # one receiver block; never substitute sent bytes or a later observation.
        require(durable and matched and 0 <= durable[-1] - matched[-1] <= 4096, "percentage lacks contemporaneous MCU durable")
        handle = sorted(set(re.findall(rb"contentIntent=PendingIntent\{[^\r\n]*PendingIntentRecord\{([0-9a-f]+) ", text)))
        require(len(handle) == 1, "notification content Intent ambiguous")
        handles.append(handle[0])
        values.append(dict(percent=percentage, durable=matched[-1], cutoff_durable=durable[-1], records=count))
    require(len(values) >= 2 and len(set(handles)) == 1 and
            all(a["percent"] < b["percent"] for a, b in zip(values, values[1:])), "notification task changed or no progress")
    blocks = intent.split(b"PendingIntentRecord{")[1:]
    current = [block for block in blocks if block.startswith(handles[0] + b" ")]
    require(len(current) == 1 and b"startActivity" in current[0] and b"act=com.wen.gaia.gaia.DEVICE_OTA_OPEN " in current[0],
            "current notification not bound to OPEN activity")
    uri = re.findall(rb"dat=(trace-device-ota://task/([^/ ]+)/(\d+)/open) ", current[0])
    require(len(uri) == 1 and uri[0][1].split(b"_")[-2] == uri[0][2], "OPEN task generation differs")
    return dict(samples=values, current_open=uri[0][0].decode(), pending_intent=handles[0].decode())


def formal_precheck(source, target, contract_path, matrix_path):
    if not target.is_relative_to(BUNDLE):
        require(contract_path is None and matrix_path is None, "cache smoke cannot claim a formal contract")
        return None
    require(contract_path is not None and matrix_path is not None, "formal output requires frozen contract/matrix")
    from Tools.acceptance import validate_bundle as validator
    contract, matrix, contract_hash, _ = validator._load_bundle(contract_path, matrix_path)
    require(contract.get("status") == "FROZEN" and matrix.get("overall_result") == "NOT_RUN", "formal execution not frozen/unexecuted")
    errors = validator.validate_contract(contract)
    errors += validator.validate_matrix(matrix, contract, contract_hash)
    errors += validator.validate_freeze_objects(contract, ROOT)
    errors += validator.validate_execution_worktree(contract, ROOT)
    errors += validator.validate_external_inputs(contract, BUNDLE)
    require(not errors, "formal precheck: " + "; ".join(errors))
    require(any(item["evidence_path"] == source.relative_to(BUNDLE).as_posix() and
                item["evidence_sha256"].lower() == sha(source.read_bytes()) for item in contract["external_inputs"]), "inputs not frozen")
    command = next((c for c in contract["commands"] if c["id"] == "CMD-P38-OFFLINE"), None)
    require(command and command["command"] == "python -I -S -B -X utf8 " + " ".join(
        str(Path(arg).relative_to(ROOT)).replace("\\", "/") if Path(arg).is_absolute() else arg.replace("\\", "/")
        for arg in sys.argv), "formal command differs from frozen runner/arguments")
    require(any(a["path"] == target.relative_to(BUNDLE).as_posix() for a in contract["artifacts"]), "unfrozen result destination")
    require(not git("diff", "--name-only", SOURCE, contract["freeze_commit"], "--", "app/bluetooth_flutter_Trace/lib",
                    "app/bluetooth_flutter_Trace/android", "app/bluetooth_flutter_Trace/pubspec.yaml").strip(), "frozen product differs from evaluated source")
    return dict(contract_sha256=contract_hash, freeze_commit=contract["freeze_commit"], result="PASS")


def fixed_signing(inputs, base):
    run, jobs = json_input(inputs["run"], base), json_input(inputs["jobs"], base)["jobs"]
    require(run["conclusion"] == "success" and run["path"] == ".github/workflows/build.yml", "fixed-signing CI not successful")
    signed = [j for j in jobs if j["name"] == "Build Android APK"]
    require(len(signed) == 1 and signed[0]["conclusion"] == "success" and signed[0]["run_id"] == run["id"] and
            signed[0]["head_sha"] == run["head_sha"], "signed APK job/run/source differs or failed")
    signature_steps = [s for s in signed[0]["steps"] if s["name"] == "Verify release APK signature and identity"]
    require(len(signature_steps) == 1 and signature_steps[0]["conclusion"] == "success", "signature step failed/missing")
    require(all(j["conclusion"] == "skipped" for j in jobs if "Release" in j["name"] or "Pages" in j["name"]), "unexpected publication")
    require(not git("diff", "--name-only", SOURCE, run["head_sha"], "--", "app/bluetooth_flutter_Trace/lib",
                    "app/bluetooth_flutter_Trace/android", "app/bluetooth_flutter_Trace/pubspec.yaml").strip(), "signed build product changed")
    log = read(inputs["log"], base).decode("utf8")
    actual = re.findall(r"(?m)^\S+Z Verified fixed APK signer SHA-256: ([0-9a-f]{64})\r?$", log)
    require(actual == ["9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579"], "actual fixed signer confirmation absent")
    apk = re.findall(r"(?m)^\S+Z ([0-9a-f]{64})  build/app/outputs/flutter-apk/app-release.apk\r?\n\S+Z (\d+)\r?$", log)
    require(len(apk) == 1 and int(apk[0][1]) > 0, "signed APK bytes/hash not recorded")
    return dict(run=run["id"], source=run["head_sha"], signer=actual[0], apk_sha256=apk[0][0],
                apk_bytes=int(apk[0][1]), locally_downloaded=False)


def healthy_state(fields):
    scalar = lambda key: int.from_bytes(fields[key], "little")
    require(fields["state"] == b"\x04" and fields["confirmed"] == fields["snapped"] == b"\x01", "not confirmed")
    require(fields["sd"] == b"\x01", "SD not ready")
    require(all(scalar(k) == 0 for k in ("owner", "active", "isr", "cfsr", "hfsr")), "active or faulted")
    require(scalar("vtor") == 0x08010800 and not scalar("dhcsr") & 0xa0000 and not scalar("sdio") & 0x3800, "core/peripheral fault")
    a, b = (struct.unpack("<9I", fields[k]) for k in ("health0", "health1"))
    require(a[3] == b[3] and a[7:] == b[7:] == (1, 1) and b[4] > a[4] and b[5] > a[5], "health not advancing")
    return dict(confirmed=True, sd_ready=True, advancing=True)


def locked_progress(raw, header, samples, base=BUNDLE):
    values = []
    for sample in samples:
        prefix = sample["events_prefix"]
        require(type(prefix["bytes"]) is int and 0 < prefix["bytes"] <= len(raw), "sample prefix bounds")
        events = raw[:prefix["bytes"]]
        require(sha(events) == prefix["sha256"], "sample is not this immutable snapshot's prefix")
        require(read(sample["pid"], base).strip() == str(header["pid"]).encode(), "sample PID differs")
        power, services = read(sample["power"], base), read(sample["services"], base)
        require(b"mWakefulness=Asleep" in power and active_lock(power, header["pid"]), "locked ownership absent")
        require(b"mDreamingLockscreen=true" in read(sample["activities"], base), "not locked")
        require(b"DeviceOtaService" in services and b"foregroundId=2408" in services and b"isForeground=true" in services,
                "foreground owner absent")
        matches = [int(m[1]) for line in events.splitlines()
                   if (m := re.search(r"kind=durable us=\d+ off=(\d+)", json.loads(line).get("message", "")))]
        require(matches, "no receiver durable observations")
        values.append(max(matches))
    require(len(values) >= 2 and all(a < b for a, b in zip(values, values[1:])), "no locked durable advancement")
    return values


def artifact_members(archive):
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None, "ZIP CRC failed")
        return {name: z.read(name) for name in z.namelist() if not name.endswith("/")}


def software(inputs, base=BUNDLE):
    run, jobs = json_input(inputs["run"], base), json_input(inputs["jobs"], base)["jobs"]
    require(run["head_sha"] == SOURCE and run["conclusion"] == "success", "wrong/failed standard build")
    require(run["id"] == 40242995708 and run["path"] == ".github/workflows/build.yml", "wrong build workflow")
    named = {j["name"]: j for j in jobs}
    for name in ("Build Android APK", "Build Windows EXE"):
        require(named[name]["conclusion"] == "success", "required standard job missing/failed")
        require(all(s["conclusion"] == "success" for s in named[name]["steps"]
                    if s["name"] in ("Analyze project", "Run Flutter tests")), "standard analyzer/test step failed")
    for j in jobs:
        if "Release" in j["name"] or "Pages" in j["name"]:
            require(j["conclusion"] == "skipped", "unexpected publication")
    artifact_records = json_input(inputs["artifacts"], base)["artifacts"]
    for name, artifact_id in (("android", 12617602035), ("windows", 12617872448)):
        records = [a for a in artifact_records if a["id"] == artifact_id]
        require(len(records) == 1 and records[0]["workflow_run"]["id"] == run["id"] and
                records[0]["workflow_run"]["head_sha"] == SOURCE and
                records[0]["digest"] == "sha256:" + sha(read(inputs[name], base)), "artifact/run/digest binding")
    archives = {}
    import io as streams
    for name in ("android", "windows", "logs"):
        archives[name] = artifact_members(streams.BytesIO(read(inputs[name], base)))
    apk = archives["android"]["ble-monitor-android.apk"]
    windows = archives["windows"]
    inner = artifact_members(streams.BytesIO(windows["ble-monitor-windows.zip"]))
    executables = [v for k, v in inner.items() if k.endswith("/ble_monitor.exe") or k == "ble_monitor.exe"]
    require(executables == [windows["ble-monitor-windows.exe"]], "EXE differs from distribution")
    require(artifact_members(streams.BytesIO(apk)), "empty APK")
    logs = archives["logs"]
    diagnostics = {}
    for host, analyze, tests, build in (
            ("Build Android APK", "9_Analyze project.txt", "10_Run Flutter tests.txt", "12_Build release APK.txt"),
            ("Build Windows EXE", "6_Analyze project.txt", "7_Run Flutter tests.txt", "8_Build Windows release.txt")):
        decoded = {k: logs[host + "/" + v].decode("utf-8", "replace")
                   for k, v in (("analyze", analyze), ("tests", tests), ("build", build))}
        require("No issues found!" in decoded["analyze"], "standard analyzer not clean")
        counts = test_counts(decoded["tests"])
        require("Built " in decoded["build"], "missing actual build output")
        setup_name = "5_Set up Flutter.txt" if host == "Build Android APK" else "3_Set up Flutter.txt"
        setup = logs[host + "/" + setup_name].decode("utf8")
        sdk = set(re.findall(r"flutter-(?:linux|windows)-stable-(\d+\.\d+\.\d+)-x64-([0-9a-f]{40})", setup))
        require(len(sdk) == 1, "SDK selection identity ambiguous")
        diagnostics[host] = dict(**counts, selected_sdk=list(next(iter(sdk))),
                                warnings=[s for s in decoded["build"].splitlines() if re.search(r"\bwarning\b", s, re.I)])
    signing = read(inputs["signature"], base)
    require(b"Verifies" in signing and len(re.findall(rb"Signer #[0-9]+ certificate SHA-256 digest: [0-9a-f]{64}", signing)) == 1,
            "standard APK signature not verified")
    badging = read(inputs["badging"], base)
    require(b"package: name='com.wen.gaia.gaia'" in badging and b"versionCode='87'" in badging
            and b"versionName='1.0.61'" in badging, "standard package/version differs")
    verified = json_input(inputs["verified_assets"], base)
    require(verified["apk_sha256"] == sha(apk) and verified["exe_sha256"] == sha(executables[0]), "verifier asset identity")
    require(verified["signature_sha256"] == sha(signing) and verified["badging_sha256"] == sha(badging), "verifier output binding")
    prior_signature = read(inputs["prior_signature"], base)
    cert = lambda raw: re.findall(rb"Signer #[0-9]+ certificate SHA-256 digest: ([0-9a-f]{64})", raw)
    require(b"Verifies" in prior_signature and len(cert(prior_signature)) == 1, "historical signature evidence absent")
    native = ET.fromstring(read(inputs["native_xml"], base))
    require(native.attrib.get("tests") == "18" and all(native.attrib.get(k) == "0" for k in ("errors", "failures", "skipped"))
            and len(native.findall("testcase")) == 18 and not native.findall(".//failure") and not native.findall(".//error"), "native regression failures")
    require(not git("diff", "--name-only", "27048aa1", SOURCE, "--", "app/bluetooth_flutter_Trace/android").strip(), "native originals no longer applicable")
    require(not git("diff", "--name-only", "3daf949f", SOURCE, "--", "app/bluetooth_flutter_Trace/lib", "app/bluetooth_flutter_Trace/android").strip(), "device APK code differs from release code")
    fixed = fixed_signing(inputs["fixed_signing"], base)
    return dict(run=run["id"], commit=SOURCE, apk_sha256=sha(apk), exe_sha256=sha(executables[0]), diagnostics=diagnostics,
                baseline_signer=cert(signing)[0].decode(), fixed_signing=fixed,
                release_fast_path="NOT_CLAIMED")


def evaluate(inputs, base=BUNDLE):
    observations, results = {}, {}
    def criterion(name, action):
        try:
            observations[name] = action()
            results["P38-" + name] = dict(result="PASS", observed=True)
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
            results["P38-" + name] = dict(result="NOT_OBSERVED", observed=None, reason=str(error))
    criterion("SOFTWARE", lambda: software(inputs["software"], base))
    loaded = {}
    for name in ("fallback", "notification", "disconnect", "resume", "fast"):
        try:
            loaded[name] = snapshot(inputs["snapshots"][name], inputs["capture_bindings"][name], base)
        except (OSError, ValueError, KeyError, TypeError) as error:
            observations[name + "_error"] = str(error)

    def fallback():
        _, _, value, messages = loaded["fallback"]
        pauses = [m for m in messages if "PAUSE" in m or "RESUME" in m]
        require(not value["success"] and value["finalDurable"] > 0 and len(pauses) >= 2, "permission fallback observations missing")
        order = pause_order(messages)
        original = read(inputs["fallback_source"], base).decode("utf8")
        require(re.search(r"await _sendSegment\(package, blockStart, seg, seq\);.{0,600}recordSegmentSendEnd", original, re.S),
                "historical completion semantics differ")
        native_terminal(read(inputs["fallback_terminal"]["power"], base), read(inputs["fallback_terminal"]["services"], base))
        return dict(finalDurable=value["finalDurable"], pause_markers=pauses, order=order, historical_source=True)
    criterion("FALLBACK", fallback)

    def background():
        raw, header, value, messages = loaded["fast"]
        runtime = json_input(inputs["runtime"], base)
        require(ota_link_profile.runtime_bytes(runtime) == read(inputs["runtime"], base), "noncanonical runtime")
        experiments = [json.loads(m[15:]) for m in messages if m.startswith("OTA_EXPERIMENT ")]
        ota_link_profile.check_observation(value, runtime, experiments=experiments)
        return dict(locked_durable=locked_progress(raw, header, inputs["locked_samples"], base),
                    capture=value["captureId"], transfer_us=value["transferUs"])
    criterion("BACKGROUND", background)

    def notification():
        raw, header, value, _ = loaded["notification"]
        require(not value["success"] and value["finalDurable"] > value["initialDurable"], "D2 transfer missing")
        intent = read(inputs["notification"]["intent"], base)
        progress = notification_progress(raw, header, inputs["notification"]["samples"],
                                         value["parameters"]["input"]["packageBytes"], intent, base)
        require(b"mCurrentFocus=Window" in read(inputs["notification"]["activities"], base) and
                b"com.wen.gaia.gaia.MainActivity" in read(inputs["notification"]["activities"], base), "return activity absent")
        require(read(inputs["notification"]["screen"], base).startswith(b"\x89PNG\r\n\x1a\n"), "D2 return screenshot missing")
        review = read(inputs["notification"]["adjudication"], base).decode("utf8")
        require(inputs["notification"]["screen"]["sha256"] in review and progress["current_open"] in review,
                "independent visual adjudication not bound")
        return dict(**progress, independent_review_sha256=sha(review.encode()), fast_visual_pass=False,
                    screenshot_numeric_progress="NOT_VISIBLE")
    criterion("NOTIFICATION", notification)
    criterion("RECOVERY", lambda: recovery(loaded["disconnect"][2], loaded["resume"][2]))

    def final_identity():
        observed = loaded["fast"][2]
        raw = read(inputs["mcu"]["app_region"], base)
        target = read(inputs["mcu"]["target"], base)
        identity = firmware(raw)
        require(raw[:len(target)] == target and identity["sha256"] == observed["parameters"]["input"]["targetImageSha256"],
                "full target differs from fresh GET_INFO")
        require(identity["version"] == observed["parameters"]["input"]["targetVersionCode"], "target version mismatch")
        boot = read(inputs["mcu"]["boot"], base)
        require(sha(boot) == "01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527", "Boot changed")
        fields = {name: read(item, base) for name, item in inputs["mcu"]["state"].items()}
        return dict(identity=identity, boot_sha256=sha(boot), **healthy_state(fields))
    criterion("FINAL-IDENTITY", final_identity)

    def cleanup():
        for name, sample in inputs["terminal_samples"].items():
            native_terminal(read(sample["power"], base), read(sample["services"], base),
                            read(sample["notification"], base) if "notification" in sample else None)
        for item in inputs["closures"]:
            value = json_input(item, base)
            require(value.get("cleanup_complete") is True and not value.get("cleanup_errors"), "host cleanup incomplete")
        end = json_input(inputs["session_result"], base)
        require(end["private_port_closed"] and not end["cleanup_errors"], "private ADB cleanup incomplete")
        require(results["P38-SOFTWARE"]["result"] == "PASS", "current software resource/race regression binding missing")
        return dict(terminal_outcomes=sorted(inputs["terminal_samples"]), physical_cleanup=True)
    criterion("CLEANUP", cleanup)
    return dict(criteria=results, observations=observations, independent_offline_evaluation=True,
                new_device_operations=0, result="PASS" if all(v["result"] == "PASS" for v in results.values()) else "EVIDENCE_GAP")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--matrix", type=Path)
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit root required")
    target = output(args.out)
    require(not target.exists(), "prior evaluation exists; do not overwrite")
    source = args.inputs.resolve(strict=True)
    precheck = formal_precheck(source, target, args.contract, args.matrix)
    result = evaluate(json.loads(source.read_bytes()), source.parent.parent)
    result["formal_precheck"] = precheck
    write_json(target, result)
    print(json.dumps(dict(result=result["result"], criteria=result["criteria"])), flush=True)
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
