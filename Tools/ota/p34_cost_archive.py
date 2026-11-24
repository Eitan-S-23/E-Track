"""Archive one bound completed capture before either install-cost cell."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

CURRENT = "20260930T133457-87100"
CAPTURE = "1790762757650934-dd5b864e26ea6ef1d45ad8d0"
PROTECTED = "1790777081899036-2e8880b661bed7f37dc19925"


def verify_erase_measure_recovery(s):
    cli.require(s.current() == "20260930T195151-65600", "archive recovery current owner changed")
    old = s.root / ".cache/p34-erase/archive-30240"
    originals = {
        "result.json": "c00eae951ff86806e356d5152cdc8acb241600b35d179361050176de03f02c44",
        "phone/usb/closed.json": "2c8418bc1cfd10bea4d5e71f99d46e6b2276d2ed865d906105706850768aa093",
        "phone/usb/commands.jsonl": "524226f186d9133f2ba6f169977469a26ba0a7573698a79b6d4abcc45f4b731b",
    }
    for name, digest in originals.items():
        cli.require(cli.record(old / name)["sha256"] == digest, "original USB failure evidence changed")
    failed = s.read(old / "result.json")
    cli.require(failed == dict(result="ARCHIVE_FAILED", deleted_files=0, no_transfer=True,
        error="RuntimeError", detail="exact phone did not become online in the bounded USB window"),
        "not the no-device archive failure")
    cli.require(not any((old / name).exists() for name in ("intent.json", "quiesce.json", "backup", "live")),
                "archive may have mutated phone; reconcile before recovery")
    commands = [json.loads(line) for line in (old / "phone/usb/commands.jsonl").read_text().splitlines()]
    cli.require(commands and all(row["args"] == ["get-state"] and row["exit"] == 1 and
                "device '10ADA4197U001CK' not found" in row["stderr"] for row in commands),
                "unexpected command before failed USB entry")
    closure = s.read(old / "phone/usb/closed.json")
    cli.require(closure["port"] == 5062 and closure["port_closed"] and
                closure["stop_exit"] == closure["server_exit"] == closure["launcher_exit"] == 0 and
                closure["key_before"] == closure["key_after"] == cli.record(closure["key_after"]["path"]),
                "original USB owner/key not closed unchanged")
    for name in ("s04", "network"):
        owner = cli.owner_state(s, s.run(s.current()) / "runtime" / name)
        cli.require(owner["state"] == "CLOSED" and owner["receipt"]["worker_exit"] == 0 and
                    not owner["receipt"]["forced_termination"], "completed OTA owner not closed")


def run(*, measure=False, erase=False, erase_measure=False, recovery=False, reconnect=False):
    cli.require(sum(map(bool, (measure, erase, erase_measure, reconnect))) <= 1, "choose one archive mode")
    cli.require(not recovery or erase_measure, "recovery is only for the exact erase measurement archive")
    current_run = "20260930T163130-3100" if measure else CURRENT
    selected_capture = PROTECTED if measure else CAPTURE
    protected_capture = "1790788189634122-086835854f739f7c44a5b922" if measure else PROTECTED
    group = "cost-bootstrap" if measure else cli.BOOT_COPY_GROUP
    previous_group = cli.BOOT_COPY_GROUP if measure else "ack-batch-bootstrap"
    if erase:
        current_run = "20260930T175922-37800"
        selected_capture = "1790788189634122-086835854f739f7c44a5b922"
        protected_capture = "1790792260297690-eb603a4cbe55740b41f5caf2"
        group, previous_group = "cost-measure", "cost-bootstrap"
    if erase_measure:
        current_run = "20260930T195151-65600"
        selected_capture = "1790792260297690-eb603a4cbe55740b41f5caf2"
        protected_capture = "1790798832805870-ad6986b0d944ef94565ecebb"
        group, previous_group = "erase-bootstrap", "cost-measure"
    if reconnect:
        current_run = "20261001T112936-16300"
        selected_capture = "1790798832805870-ad6986b0d944ef94565ecebb"
        protected_capture = "1790855482189170-bfba33ff19dfd706ce2761f9"
        group, previous_group = "erase-measure", "erase-bootstrap"
    s = cli.Store(ROOT)
    if recovery:
        verify_erase_measure_recovery(s)
    out = s.checked(ROOT / (".cache/p34-reconnect/archive-30241" if reconnect else
                           ".cache/p34-erase/archive-30240-resume" if recovery else
                           ".cache/p34-erase/archive-30240" if erase_measure else
                           ".cache/p34-erase/archive-30239" if erase else
                           ".cache/p34-cost/archive-30238" if measure else ".cache/p34-cost/archive-30235"))
    cli.require(not out.exists() and s.current() == current_run, "archive spent or current owner changed")
    cli.verify_tests(s)
    profile = s.base / ("profile-erase-measure.json" if reconnect else
                        "profile-erase-bootstrap.json" if erase_measure else
                        "profile-cost-measure.json" if erase else
                        "profile-cost-bootstrap-v2.json" if measure else "profile-boot-copy-measure.json")
    api = cli.backend(s, profile, group)
    previous = cli.completed_full_predecessor(s, s.read(profile)["predecessor"], group=previous_group)
    current = cli.completed_full_predecessor(s, cli.current_full_descriptor(s, current_run), group=group)
    cli.require(previous["report"]["summary"]["captureId"] == selected_capture and
                current["report"]["summary"]["captureId"] == protected_capture, "wrong selected/protected capture")
    c = api.installed_context(out)
    api.preflight(c, out)
    for leaf in ("intent.json", "result.json", "backup", "quiesce.json", "phone", "live"):
        s.checked(out / leaf)
    out.mkdir(parents=True)
    phone = api.phone(c, "cost_archive")
    lock = c.load("cost_archive_lock", ROOT / "Tools/ota/repeat_cycle.py")
    result = dict(result="ARCHIVE_FAILED", deleted_files=0, no_transfer=True)
    try:
        with lock.device_lock(), phone.usb(c, out / "phone") as p:
            live = api.capture(c, p, phone, out / "live")
            cli.require(live.get("stable_completed") and api.completed_capture(c, live, current), "current App not exact completed target")
            config = p.file_bytes(c.PKG, "files/p34-experiment.json", 8192)
            cli.require(config == Path(current["report"]["inputs"]["config"]["path"]).read_bytes(), "current config changed")
            pid = str(live["pid"]) if live["pid"] else ""
            cli.require(p.command(["shell", "pidof", c.PKG], check=False).strip() == pid, "App process changed")
            c.save(out / "quiesce.json", dict(pid=live["pid"], protected=protected_capture, config=live["config"]))
            if pid:
                p.command(["shell", "am", "force-stop", c.PKG])
            cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(), "App not stopped")
            before = api.observation_names(c, p)
            cli.require(len(before) == 8 and selected_capture in before and protected_capture in before, "capture set changed")
            src, dst = "files/p34-observations/" + selected_capture, "files/p34-observation-archive/" + selected_capture
            checked = sys.modules["p34_session_backend"].checked_phone_path
            source, destination = checked(c, p, src), checked(c, p, dst, new_leaf=True)
            cli.require(not phone.exists(p, c.PKG, dst), "destination exists")
            names = sorted(p.command(["exec-out", "run-as", c.PKG, "ls", "-1", src]).splitlines())
            cli.require(names == ["events.jsonl", "health.json", "snapshot-1.jsonl"], "unknown capture files")
            data = {name:p.file_bytes(c.PKG, src + "/" + name, c.envelope.MAX_BYTES + 8192) for name in names}
            h = json.loads(data["health.json"])
            cli.require(h["captureId"] == selected_capture and h["healthy"] and h["lost"] == 0 and h["error"] is None and
                        h["upgradeStarts"] == h["upgradeEnds"] == 1 and h["outcome"] == "completed", "unhealthy archive")
            original = previous["report"]["inputs"]["snapshot"]
            cli.require(cli.record(original["path"]) == original and data["snapshot-1.jsonl"] == Path(original["path"]).read_bytes(), "snapshot differs")
            backup = {name:c.raw(out / "backup" / name, blob) for name,blob in data.items()}
            cli.require(all(Path(backup[name]["path"]).read_bytes() == blob and
                            p.file_bytes(c.PKG, src + "/" + name, len(blob)+1) == blob for name,blob in data.items()) and
                        not p.command(["shell", "pidof", c.PKG], check=False).strip(), "backup or App changed")
            c.save(out / "intent.json", dict(source=source, destination=destination, before=before, backup=backup,
                protected=protected_capture, authority="standing completed byte-verified non-deleting archive"))
            p.command(["shell", "run-as", c.PKG, "mv", "-n", source, destination])
            after = api.observation_names(c, p)
            cli.require(after == sorted(set(before)-{selected_capture}) and not phone.exists(p, c.PKG, src) and
                        sorted(p.command(["exec-out", "run-as", c.PKG, "ls", "-1", dst]).splitlines()) == names and
                        all(p.file_bytes(c.PKG, dst + "/" + n, len(b)+1) == b for n,b in data.items()) and
                        p.file_bytes(c.PKG, "files/p34-experiment.json", 8192) == config and
                        not p.command(["shell", "pidof", c.PKG], check=False).strip(),
                        "archive outcome not reconciled; do not repeat")
            result.update(result="COMPLETED_CAPTURE_ARCHIVED", before=before, after=after, backup=backup,
                source=source, destination=destination, configuration_preserved=True, byte_identical=True)
        result["usb_closed"] = True
    except Exception as e:
        result.update(error=type(e).__name__, detail=str(e))
    c.save(out / "result.json", result)
    print(json.dumps(result))
    cli.require(result["result"] == "COMPLETED_CAPTURE_ARCHIVED" and result.get("usb_closed"), "archive failed; preserve and reconcile")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    cli.require(sys.argv[1:] in ([], ["--measure"], ["--erase"], ["--erase-measure"], ["--erase-measure-resume"], ["--reconnect"]),
                "expected one optional archive mode")
    run(measure=sys.argv[1:] == ["--measure"], erase=sys.argv[1:] == ["--erase"],
        erase_measure=sys.argv[1:] in (["--erase-measure"], ["--erase-measure-resume"]),
        recovery=sys.argv[1:] == ["--erase-measure-resume"], reconnect=sys.argv[1:] == ["--reconnect"])
