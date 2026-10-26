"""Stage only existing P3-8 originals; no network, device or build entry."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as e

ROOT, BUNDLE, CACHE = e.ROOT, e.BUNDLE, e.CACHE
PRIOR = ROOT.parent / "p38-acceptance-20261024"
V4 = PRIOR / ".acceptance-p3-8/v4"
FAST = ROOT / ".cache/recovery-fast/session-001"
DOWNLOADS = ROOT / ".cache/p38-closeout-20261026"
origins = {}


def copy(source, relative, *, select=None):
    source = Path(source)
    original = source.read_bytes()
    data = original
    origin = dict(path=source.relative_to(ROOT.parent.parent).as_posix(), bytes=len(data), sha256=e.sha(data))
    if select is not None:
        lines = original.splitlines(keepends=True)
        indexes = [n for n, line in enumerate(lines) if select(line)]
        data = b"".join(lines[n] for n in indexes)
        origin["line_numbers"] = [n + 1 for n in indexes]
        origin["selection"] = "Exact original lines only; omitted unrelated device state remains private."
    path = e.output(BUNDLE / "inputs" / relative)
    if path.exists():
        e.require(path.read_bytes() == data, "staged original changed: " + relative)
        item = dict(path=path.relative_to(BUNDLE).as_posix(), bytes=len(data), sha256=e.sha(data))
    else:
        item = e.write(path, data)
    origins[item["path"]] = origin
    return item


def native_sample(directory, relative, *, active=False):
    result = {}
    for name in ("services", "power"):
        selector = None if name == "services" else lambda line: any(k in line for k in
            (b"POWER MANAGER", b"mWakefulness=", b"Wake Locks:", b"trace:DeviceOta"))
        result[name] = copy(directory / (name + ".txt"), relative + "/" + name + ".txt", select=selector)
    if (directory / "notification.txt").exists():
        result["notification"] = copy(directory / "notification.txt", relative + "/notification.txt")
    if active:
        for name in ("pid", "activities"):
            result[name] = copy(directory / (name + ".txt"), relative + "/" + name + ".txt")
        data = (directory / "events.jsonl").read_bytes()
        result["events_prefix"] = dict(bytes=len(data), sha256=e.sha(data))
        origins[relative + "/events_prefix"] = dict(path=(directory / "events.jsonl").relative_to(ROOT.parent.parent).as_posix(),
                                                      bytes=len(data), sha256=e.sha(data))
    return result


def standard():
    sys.path.insert(0, str(ROOT / "Tools/ota/p34-acceptance"))
    import live_host as h
    from Tools.flutter import dev_apk
    out = e.output(CACHE / "standard-001")
    result_path = out / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_bytes())
    e.require(not out.exists(), "uncertain prior standard verification; preserve before another attempt")
    h.fresh(out)
    archives = {}
    for name, relative in (("android", "android-download"), ("windows", "windows-download"), ("logs", "standard-logs")):
        receipt = h.read_json(DOWNLOADS / relative / "result.json")
        source = h.pinned(receipt["zip"])
        e.artifact_members(source)
        dev_apk.extract_distribution(ROOT, source, out / name)
        archives[name] = source
    apk = out / "android/ble-monitor-android.apk"
    exe = out / "windows/ble-monitor-windows.exe"
    env = h.environment(out)
    for key in ("JAVA_TOOL_OPTIONS", "JAVA_OPTS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS"):
        env.pop(key, None)
    known = ROOT / ".cache/recovery/apk-verified"
    command = h.read_json(known / "signature.started.json")["argv"]
    java, jar = command[0], command[command.index("-jar") + 1]
    args = [java, "-XX:-UsePerfData", "-Djava.io.tmpdir=" + env["TEMP"], "-Duser.home=" + env["HOME"],
            "-jar", jar, "verify", "--verbose", "--print-certs"]
    signature = h.command(out, "signature", args + [apk], env, seconds=60)
    previous = h.read_json(V4 / "software/result.json")["standards"]["apk"]
    old_signature = h.command(out, "prior-signature", args + [h.pinned(previous)], env, seconds=60)
    cert = lambda data: re.findall(rb"Signer #[0-9]+ certificate SHA-256 digest: ([0-9a-f]{64})", data)
    e.require(b"Verifies" in signature and b"Verifies" in old_signature and len(cert(signature)) == 1
              and len(cert(old_signature)) == 1, "standard signature verification failed")
    aapt = h.read_json(known / "badging.started.json")["argv"][0]
    badging = h.command(out, "badging", [aapt, "dump", "badging", apk], env, seconds=45)
    value = dict(apk_sha256=e.sha(apk.read_bytes()), exe_sha256=e.sha(exe.read_bytes()),
                 signature_sha256=e.sha(signature), badging_sha256=e.sha(badging),
                 signer=cert(signature)[0].decode(), prior_signer=cert(old_signature)[0].decode(),
                 fixed_signing="NOT_ADJUDICATED", source=e.SOURCE, no_new_build_or_download=True)
    e.write_json(result_path, value)
    return value


def stage():
    standard()
    inputs = {"schema": 1, "source_commit": e.SOURCE,
              "scope": "Seven P3-8 criteria, independent offline evaluation of existing original observations; no replay."}
    software = {}
    for name in ("run", "jobs", "artifacts"):
        software[name] = copy(DOWNLOADS / "ci-status-002" / (name + ".stdout"), "software/" + name + ".json")
    for name, folder, filename in (("android", "android-download", "artifact.stdout"),
                                  ("windows", "windows-download", "artifact.stdout"), ("logs", "standard-logs", "logs.stdout")):
        software[name] = copy(DOWNLOADS / folder / filename, "software/" + name + ".zip")
    for name in ("signature", "prior_signature", "badging"):
        software[name] = copy(CACHE / "standard-001" / (name.replace("_", "-") + ".stdout"), "software/" + name + ".txt")
    software["verified_assets"] = copy(CACHE / "standard-001/result.json", "software/verified-assets.json")
    old = json.loads((V4 / "inputs/software.json").read_bytes())
    software["native_xml"] = copy(old["native_xml"]["path"], "software/native.xml")
    inputs["software"] = software
    snapshots = {}
    for name, path in (("fallback", V4 / "d1/usb/salvage/snapshot-1.jsonl"),
                       ("notification", V4 / "d2/usb/salvage/snapshot-1.jsonl"),
                       ("disconnect", V4 / "d3a/usb/salvage/snapshot-1.jsonl"),
                       ("resume", PRIOR / ".cache/p38/resume-20261026/watch/usb/salvage/snapshot-1.jsonl"),
                       ("fast", FAST / "usb/snapshot.jsonl")):
        snapshots[name] = copy(path, "snapshots/" + name + ".jsonl")
    inputs["snapshots"] = snapshots
    bindings = {}
    for name, cell in (("fallback", "d1"), ("notification", "d2"), ("disconnect", "d3a")):
        plan = json.loads((V4 / ("inputs/phone-" + cell + ".json")).read_bytes())
        receipt = json.loads((V4 / cell / "result.json").read_bytes())
        bindings[name] = dict(sentinel=plan["sentinel"], target=plan["ble_address"], apk_sha256=plan["apk"]["sha256"],
                              pid=receipt["pid"], capture=receipt["capture"])
    for name, plan_path, launch_path in (("resume", PRIOR / ".cache/p38/resume-20261026/fresh/plan.json",
                                        PRIOR / ".cache/p38/resume-20261026/fresh/result.json"),
                                       ("fast", FAST / "plan.json", FAST / "usb/launched.json")):
        plan, launch = (json.loads(p.read_bytes()) for p in (plan_path, launch_path))
        bindings[name] = dict(sentinel=plan["sentinel"], target=plan["ble_address"], apk_sha256=plan["apk"]["sha256"],
                              pid=launch["pid"], capture=launch["capture"])
    inputs["capture_bindings"] = bindings
    historical = e.git("show", "60cb25c459bcde95f2be42edc28ef3fdb2448111:app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart")
    historical_path = e.output(BUNDLE / "inputs/fallback-transport-v4.dart")
    if not historical_path.exists():
        e.write(historical_path, historical)
    e.require(historical_path.read_bytes() == historical, "historical transport changed")
    inputs["fallback_source"] = dict(path=historical_path.relative_to(BUNDLE).as_posix(),
                                    bytes=len(historical), sha256=e.sha(historical))
    origins[inputs["fallback_source"]["path"]] = dict(commit="60cb25c459bcde95f2be42edc28ef3fdb2448111",
        path="app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart", sha256=e.sha(historical))
    inputs["runtime"] = copy(FAST / "usb/runtime.json", "fast-runtime.json")
    inputs["fallback_terminal"] = native_sample(V4 / "d1/sample-0068", "terminal/fallback")
    inputs["locked_samples"] = [native_sample(FAST / ("sample-%04d" % n), "locked/%04d" % n, active=True)
                                for n in range(14, 19)]
    inputs["notification"] = dict(intent=copy(V4 / "d2/intent-observation.txt", "notification/intent.txt"),
        samples=[{name: copy(V4 / ("d2/sample-%04d/" % n) / filename,
                            "notification/%04d-%s" % (n, filename)) for name, filename in
                  (("notification", "notification.txt"), ("health", "health.json"), ("pid", "pid.txt"))}
                 for n in (15, 18, 19, 20, 22)],
        activities=copy(V4 / "d2/sample-0022/activities.txt", "notification/returned-activities.txt"),
        screen=copy(V4 / "d2/sample-0022/screen.png", "notification/returned-page.png"),
        adjudication=copy(BUNDLE / "notification-adjudication.md", "notification/adjudication.md"))
    mcu = FAST / "final-state/mcu/0001-full-state"
    inputs["mcu"] = {name: copy(mcu / (name + ".bin"), "mcu/" + name + ".bin") for name in ("app_region", "boot")}
    inputs["mcu"]["target"] = copy(ROOT / ".cache/recovery-fast/reference/target.bin", "mcu/target.bin")
    inputs["mcu"]["state"] = {name: copy(mcu / (name + ".bin"), "mcu/" + name + ".bin") for name in
                              ("state", "confirmed", "snapped", "owner", "active", "isr", "cfsr", "hfsr", "vtor", "dhcsr", "sdio", "sd", "health0", "health1")}
    disconnect_last = sorted((V4 / "d3a").glob("sample-*"))[-1]
    inputs["terminal_samples"] = dict(failure=inputs["fallback_terminal"],
        cancelled=native_sample(V4 / "d2/sample-0024", "terminal/cancelled"),
        disconnected=native_sample(disconnect_last, "terminal/disconnected"),
        completed=native_sample(FAST / "sample-9999", "terminal/completed"))
    inputs["closures"] = [copy(FAST / relative, "closures/" + name + ".json") for name, relative in
        (("adb", "usb/adb-server.closed.json"), ("network", "network/closed.json"), ("logcat", "logcat.closed.json"))]
    inputs["session_result"] = copy(FAST / "result.json", "fast-result.json")
    inputs["lineage"] = []
    for n in range(1, 5):
        inputs["lineage"].append(dict(contract=copy(PRIOR / ("docs/acceptance-contracts/P3-8-v%d.contract.json" % n),
            "lineage/v%d.contract.json" % n), matrix=copy(PRIOR / (".acceptance-p3-8/v%d/evidence-matrix.json" % n),
            "lineage/v%d.matrix.json" % n)))
    # Preserve failed recovery observations, without publishing full device logcat.
    inputs["prior_failures"] = [copy(ROOT / ".cache/recovery/final-transfer-20261026/result.json", "failures/query-timeout-result.json"),
                                copy(V4 / "recovery-findings.md", "failures/v4-recovery-findings.md")]
    e.write_json(BUNDLE / "inputs/origins-v4.json", origins)
    e.write_json(BUNDLE / "inputs/inputs-v4.json", inputs)
    print(json.dumps(dict(staged=True, inputs=len(origins), source=e.SOURCE)), flush=True)


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    e.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit root required")
    stage()
