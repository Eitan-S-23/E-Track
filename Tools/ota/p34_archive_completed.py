"""One bounded, non-deleting archive of the completed 30232 phone capture."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

CAPTURE = "1790754695082531-439081ef12a43fece7cb7d72"
PROTECTED = "1790762757650934-dd5b864e26ea6ef1d45ad8d0"
CURRENT = "20260930T094904-31700"


def run():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit root and isolated Python required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / ".cache/p34-boot/archive-30232")
    cli.require(not out.exists(), "preserve the original archive attempt")
    cli.require(store.current() == CURRENT, "current session advanced")
    profile = store.base / "profile-ack-batch-bootstrap.json"
    backend = cli.backend(store, profile, "ack-batch-bootstrap")
    predecessor = cli.completed_full_predecessor(store, store.read(profile)["predecessor"],
                                               group="ack-gap-bootstrap")
    report = predecessor["report"]
    cli.require(report["summary"]["captureId"] == CAPTURE and
                report["summary"]["outcome"] == "completed", "wrong completed capture")
    current = cli.completed_full_predecessor(store, cli.current_full_descriptor(store, CURRENT),
                                            group="ack-batch-bootstrap")
    cli.require(current["report"]["summary"]["captureId"] == PROTECTED, "wrong protected capture")
    c = backend.installed_context(out)
    backend.preflight(c, out)
    for name in ("intent.json", "result.json", "backup", "phone/usb"):
        store.checked(out / name)
    out.mkdir(parents=True)
    phone = backend.phone(c, "p34_completed_move")
    lock = c.load("p34_completed_move_lock", ROOT / "Tools/ota/repeat_cycle.py")
    result = dict(result="ARCHIVE_FAILED", deleted_files=0, no_transfer=True)
    try:
        with lock.device_lock(), phone.usb(c, out / "phone") as p:
            cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(),
                        "App must already be quiesced")
            before = backend.observation_names(c, p)
            cli.require(CAPTURE in before and PROTECTED in before and len(before) == 8,
                        "recording set changed")
            config = p.file_bytes(c.PKG, "files/p34-experiment.json", 8192)
            cli.require(config == Path(current["report"]["inputs"]["config"]["path"]).read_bytes(),
                        "current configuration changed")
            src = "files/p34-observations/" + CAPTURE
            dst = "files/p34-observation-archive/" + CAPTURE
            checked = sys.modules["p34_session_backend"].checked_phone_path
            source = checked(c, p, src)
            destination = checked(c, p, dst, new_leaf=True)
            cli.require(not phone.exists(p, c.PKG, dst), "archive destination already exists")
            names = sorted(p.command(["exec-out", "run-as", c.PKG, "ls", "-1", src]).splitlines())
            cli.require(names == ["events.jsonl", "health.json", "snapshot-1.jsonl"],
                        "unknown capture files")
            data = {name: p.file_bytes(c.PKG, src + "/" + name, c.envelope.MAX_BYTES + 8192)
                    for name in names}
            health = json.loads(data["health.json"])
            cli.require(health["captureId"] == CAPTURE and health["healthy"] is True and
                        health["lost"] == 0 and health["error"] is None and
                        health["upgradeStarts"] == health["upgradeEnds"] == 1 and
                        health["outcome"] == "completed", "unhealthy capture")
            original = report["inputs"]["snapshot"]
            cli.require(cli.record(original["path"]) == original and
                        data["snapshot-1.jsonl"] == Path(original["path"]).read_bytes(),
                        "snapshot differs from original verified completion")
            backup = {name: c.raw(out / "backup" / name, blob) for name, blob in data.items()}
            cli.require(all(Path(item["path"]).read_bytes() == data[name] for name, item in backup.items()),
                        "host backup differs")
            cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip() and
                        all(p.file_bytes(c.PKG, src + "/" + name, len(blob) + 1) == blob
                            for name, blob in data.items()), "App or capture changed before move")
            c.save(out / "intent.json", dict(source=source, destination=destination, before=before,
                backup=backup, original=original, protected=PROTECTED,
                authority="standing completed byte-verified archive; no deletion"))
            # -n prevents replacement even if another actor creates the destination.
            p.command(["shell", "run-as", c.PKG, "mv", "-n", source, destination])
            after = backend.observation_names(c, p)
            cli.require(after == sorted(set(before) - {CAPTURE}) and
                        not phone.exists(p, c.PKG, src), "archive move not reconciled")
            cli.require(sorted(p.command(["exec-out", "run-as", c.PKG, "ls", "-1", dst]).splitlines()) == names and
                        all(p.file_bytes(c.PKG, dst + "/" + name, len(blob) + 1) == blob
                            for name, blob in data.items()), "archived bytes differ")
            cli.require(p.file_bytes(c.PKG, "files/p34-experiment.json", 8192) == config and
                        not p.command(["shell", "pidof", c.PKG], check=False).strip(),
                        "configuration or process changed")
            result.update(result="COMPLETED_CAPTURE_ARCHIVED", source=source, destination=destination,
                          before=before, after=after, backup=backup, byte_identical=True,
                          configuration_preserved=True)
        result["usb_closed"] = True
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error))
    c.save(out / "result.json", result)
    print(json.dumps(result))
    cli.require(result["result"] == "COMPLETED_CAPTURE_ARCHIVED" and result.get("usb_closed"),
                "archive failed; inspect preserved evidence before any retry")


if __name__ == "__main__":
    run()
