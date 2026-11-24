"""Bounded same-package signer migration, preserving original diagnostic data."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
PKG = "com.wen.gaia.gaia.p34probe"
OLD_SHA = "ac42662d5efb8aebc6eccc56d10a0a82a85e4c5506bdbcded709965e241b3408"
NEW_SHA = "1ec71e54f738abacbf5f4360ba421076061e2026a666ef484c8e3a17759884da"
ROOTS = ("app_flutter", "databases", "files", "shared_prefs")
MAX_BYTES = 256 * 1024 * 1024
CAPTURE = "1790855482189170-bfba33ff19dfd706ce2761f9"


def archive_manifest(data):
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError("archive size outside migration bounds")
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for item in archive:
            name = item.name.rstrip("/")
            parts = name.split("/")
            if (not parts or parts[0] not in ROOTS or any(p in ("", ".", "..") for p in parts) or
                    any(c in name for c in ("\\", "\0", "\r", "\n", ":")) or
                    name in result or not (item.isfile() or item.isdir()) or len(result) >= 10000):
                raise ValueError("unsafe or ambiguous App archive member")
            raw = archive.extractfile(item).read() if item.isfile() else None
            result[name] = dict(kind="file" if raw is not None else "directory", bytes=item.size,
                sha256=hashlib.sha256(raw).hexdigest() if raw is not None else None)
    if not result or {name.split("/")[0] for name in result} != set(ROOTS):
        raise ValueError("missing persistent App directory")
    return result


def restore_name(name):
    if name == "files/p34-experiment.json":
        return "files/p34-migration-original-config.json"
    prefix = "files/p34-observations"
    if name == prefix or name.startswith(prefix + "/"):
        return "files/p34-migration-observations" + name[len(prefix):]
    return name


def restore_archive(data):
    original = archive_manifest(data)
    names = [restore_name(n) for n in original]
    if len(set(names)) != len(names):
        raise ValueError("migration archive destination collision")
    target = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as source, \
            tarfile.open(fileobj=target, mode="w", format=tarfile.PAX_FORMAT) as dest:
        for entry in source:
            raw = source.extractfile(entry).read() if entry.isfile() else None
            item = tarfile.TarInfo(restore_name(entry.name.rstrip("/")))
            item.type = tarfile.REGTYPE if raw is not None else tarfile.DIRTYPE
            item.mode = 0o600 if raw is not None else 0o700
            item.size = len(raw) if raw is not None else 0
            item.mtime = entry.mtime
            dest.addfile(item, io.BytesIO(raw) if raw is not None else None)
    value = target.getvalue()
    expected = {restore_name(k): v for k, v in original.items()}
    if archive_manifest(value) != expected:
        raise ValueError("restoration archive changed file bytes")
    return value, expected


def raw(b, path, data):
    path = b.checked(path)
    b.checked(path.parent).mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    b.require(path.read_bytes() == data, "local backup readback differs")
    return b.record(path)


def private_directory(b, path):
    path = b.checked(path)
    b.require(not path.exists(), "preserve private archive")
    path.mkdir(parents=True)
    sid = next(csv.reader([b.command(["whoami", "/user", "/fo", "csv", "/nh"]).stdout.decode().strip()]))[1]
    b.require(re.fullmatch(r"S-1-5-(?:\d+-)*\d+", sid), "invalid Windows principal")
    b.command(["icacls", str(path), "/inheritance:r", "/grant:r", "*" + sid + ":(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"])


def backup(b, d, p, out):
    b.require(d["installed"](b, p, OLD_SHA) is not None, "old APK missing")
    active = "files/p34-observations/" + CAPTURE
    health = json.loads(p.file_bytes(PKG, active + "/health.json", 8192))
    b.require(health["captureId"] == CAPTURE and health["healthy"] and health["lost"] == 0 and
              health["error"] is None and health["upgradeStarts"] == health["upgradeEnds"] == 1 and
              health["outcome"] == "completed", "current capture is not completed; do not stop App")
    b.io.write_json(ROOT, out / "quiesce-intent.json", dict(capture=CAPTURE, old_apk=OLD_SHA))
    p.command(["shell", "am", "force-stop", PKG])
    b.require(not p.command(["shell", "pidof", PKG], check=False).strip(), "old App did not stop")
    sizes = p.command(["exec-out", "run-as", PKG, "du", "-sk", *ROOTS])
    rows = [row.split() for row in sizes.splitlines()]
    b.require(len(rows) == 4 and {r[1] for r in rows} == set(ROOTS) and
              all(r[0].isdigit() for r in rows) and sum(int(r[0]) for r in rows) * 1024 < MAX_BYTES // 2,
              "unexpected backup size")
    data = p.command(["exec-out", "run-as", PKG, "tar", "-cf", "-", *ROOTS], timeout=180, binary=True)
    manifest = archive_manifest(data)
    original = raw(b, out / "original-data.tar", data)
    again = p.command(["exec-out", "run-as", PKG, "tar", "-cf", "-", *ROOTS], timeout=180, binary=True)
    b.require(archive_manifest(again) == manifest, "remote backup changed on second read")
    permanent = b.checked(ROOT / ".local-archive/p34-signing-migration")
    private_directory(b, permanent)
    durable = raw(b, permanent / "original-data.tar", data)
    transformed, expected = restore_archive(data)
    restore = raw(b, out / "restore-data.tar", transformed)
    b.io.write_json(ROOT, out / "backup.json", dict(result="BACKUP_VERIFIED", original=original, durable=durable,
        restore=restore, manifest=manifest, restore_manifest=expected, remote_second_read_equal=True,
        source=b.record(Path(__file__)), old_apk=OLD_SHA, package=PKG, old_app_stopped=True,
        preserved_capture=CAPTURE, mapping="archive old runtime config and active observations; preserve other file bytes"))
    return dict(result="BACKUP_VERIFIED", files=sum(v["kind"] == "file" for v in manifest.values()), bytes=len(data),
                old_app_stopped=True, no_uninstall=True)


def replacement(b, d, p, out):
    proof_path = b.OUT / "migration/backup-001/backup.json"
    proof = json.loads(proof_path.read_bytes())
    b.require(proof["result"] == "BACKUP_VERIFIED" and proof["old_apk"] == OLD_SHA, "backup not verified")
    for name in ("original", "durable", "restore"):
        b.require(b.record(proof[name]["path"]) == proof[name], "backup changed")
    b.require(archive_manifest(Path(proof["restore"]["path"]).read_bytes()) == proof["restore_manifest"], "restore manifest changed")
    value = b.read("apk-g2/apk.json")
    b.require(value["apk"]["sha256"] == NEW_SHA and b.record(value["apk"]["path"]) == value["apk"] and
              value["metadata"]["application_id"] == PKG and value["certificate_sha256"] ==
              "9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579", "fixed APK drift")
    b.require(d["installed"](b, p, OLD_SHA) is not None and
              not p.command(["shell", "pidof", PKG], check=False).strip(), "old App changed after backup")
    users = re.findall(r"(?m)^    User (\d+): [^\r\n]*\binstalled=true\b",
                       p.command(["shell", "dumpsys", "package", PKG]))
    b.require(users == ["0"], "diagnostic App installed for another Android user; do not uninstall")
    b.io.write_json(ROOT, out / "uninstall-intent.json", dict(package=PKG, old_apk=OLD_SHA,
        backup=b.record(proof_path), authority="User explicitly approved one-time same-package signer migration"))
    answer = p.command(["uninstall", PKG], timeout=60)
    b.require(answer.strip() == "Success" and d["installed"](b, p, OLD_SHA) is None, "uninstall outcome uncertain")
    b.io.write_json(ROOT, out / "uninstalled.json", dict(package=PKG, completed=True))
    b.io.write_json(ROOT, out / "install-intent.json", dict(apk=value["apk"], package=PKG))
    answer = p.command(["install", "--no-streaming", value["apk"]["path"]], timeout=180)
    b.require(answer.strip().splitlines()[-1:] == ["Success"], "installation outcome uncertain; do not repeat")
    current = d["installed"](b, p, NEW_SHA)
    b.require(current is not None, "new APK not installed")
    b.io.write_json(ROOT, out / "installed.json", current)
    return dict(result="FIXED_APK_INSTALLED", installed=current, no_app_launch=True, restoration_pending=True)


def restore(b, d, p, out):
    b.require(d["installed"](b, p, NEW_SHA) is not None and
              not p.command(["shell", "pidof", PKG], check=False).strip(), "new App must remain stopped")
    proof = b.read("migration/backup-001/backup.json")
    item = proof["restore"]
    b.require(b.record(item["path"]) == item, "restore archive changed")
    data = Path(item["path"]).read_bytes()
    b.require(archive_manifest(data) == proof["restore_manifest"], "restore input mismatch")
    b.io.write_json(ROOT, out / "restore-intent.json", dict(archive=item, package=PKG,
        roots=ROOTS, only_stopped_new_app=True))
    args = p.BASE + ["exec-in", "run-as", PKG, "tar", "-xf", "-"]
    process = subprocess.run(args, cwd=ROOT, env=p.environment(), input=data, capture_output=True,
        timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
    b.io.write_json(ROOT, out / "restore-command.json", dict(args=args, exit=process.returncode,
        stdout_bytes=len(process.stdout), stderr=process.stderr.decode("utf-8", "replace"), archive=item))
    b.require(process.returncode == 0, "restore command failed; reconcile before repeating")
    remote = p.command(["exec-out", "run-as", PKG, "tar", "-cf", "-", *ROOTS], timeout=180, binary=True)
    actual = archive_manifest(remote)
    b.require(actual == proof["restore_manifest"], "restored App data differs from verified backup")
    b.io.write_json(ROOT, out / "restored-manifest.json", actual)
    permissions = d["permission_state"](p.command(["shell", "dumpsys", "package", PKG]), 0)
    if not all(permissions.values()):
        p.command(["shell", "am", "start", "-W", "--user", "0", "-a",
            "android.settings.APPLICATION_DETAILS_SETTINGS", "-d", "package:" + PKG], timeout=45)
    return dict(result="RESTORED_NEEDS_PERMISSION" if not all(permissions.values()) else "MIGRATION_VERIFIED",
        files=sum(v["kind"] == "file" for v in actual.values()), permissions=permissions,
        old_observations_archived=True, old_config_archived=True, app_started=False)


def runtime():
    v = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_validation.py"))
    b = v["runtime"]()
    v["preflight"](b)
    d = runpy.run_path(str(ROOT / ".cache/p34-next/device.py"))
    p = b.load("fixed_signing_usb", ROOT / ".cache/p3-4-screening-20260922/phone.py")
    p.b.require, p.b.checked, p.b.io, p.b.record = b.require, b.checked, b.io, b.record
    lock = b.load("fixed_signing_device_lock", ROOT / "Tools/ota/repeat_cycle.py")
    b.checked(ROOT / ".cache/p34-cycles/device.lock")
    return b, d, p, lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "backup", "replace", "restore"))
    args = parser.parse_args()
    b, d, p, lock = runtime()
    b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated explicit root required")
    out = b.checked(b.OUT / "migration" / (args.mode + "-001"))
    b.require(not out.exists(), "preserve migration attempt; reconcile before continuation")
    for name in ("intent.json", "result.json", "private-root.txt", "persistent-directories.txt", "persistent-size.txt"):
        b.checked(out / name)
    if args.mode != "inspect":
        for name in ("quiesce-intent.json", "original-data.tar", "restore-data.tar", "backup.json", "uninstall-intent.json",
                     "uninstalled.json", "install-intent.json", "installed.json", "restore-intent.json", "restore-command.json",
                     "restored-manifest.json"):
            b.checked(out / name)
        tests = b.read("migration/tests.json")
        b.require(tests["passed"] and tests["source"] == b.record(Path(__file__)), "current migration self-tests required")
        if args.mode == "backup":
            private_directory(b, out)
    b.io.write_json(ROOT, out / "intent.json", dict(time=b.now(), package=PKG, source=b.record(Path(__file__)),
        authority="User explicitly approved backup, verification, uninstall and same-package fixed-signer installation",
        mode=args.mode, no_mcu=True, no_ota=True, no_app_launch=True))
    result = dict(result="MIGRATION_STEP_FAILED", no_mcu=True, no_ota=True, mode=args.mode)
    try:
        with lock.device_lock(), d["usb"](b, p, out):
            p.phone_identity()
            b.require(p.command(["shell", "am", "get-current-user"]).strip() == "0", "wrong Android user")
            if args.mode != "inspect":
                result.update({"backup": backup, "replace": replacement, "restore": restore}[args.mode](b, d, p, out))
            else:
                result.update(inspect(b, d, p, out))
        result["usb_closed"] = True
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error))
    b.io.write_json(ROOT, out / "result.json", result)
    print(json.dumps(result), flush=True)
    b.require("error" not in result and result.get("usb_closed"), "migration requires reconciliation")


def inspect(b, d, p, out):
    old = d["installed"](b, p, OLD_SHA)
    b.require(old is not None, "old App missing; reconcile first")
    listing = p.command(["exec-out", "run-as", PKG, "ls", "-la"])
    directories = p.command(["exec-out", "run-as", PKG, "find", ".", "-maxdepth", "1", "-type", "d", "-print"])
    names = [n.removeprefix("./") for n in directories.splitlines() if n != "."]
    b.require(names and all(re.fullmatch(r"[a-zA-Z0-9_-]+", n) for n in names), "ambiguous App directories")
    persistent = sorted(set(names) - {"cache", "code_cache"})
    sizes = p.command(["exec-out", "run-as", PKG, "du", "-sk", *persistent])
    for name, data in (("private-root.txt", listing), ("persistent-directories.txt", directories),
                       ("persistent-size.txt", sizes)):
        raw(b, out / name, data.encode())
    return dict(result="OLD_APP_INSPECTED", installed=old, persistent=persistent, sizes=sizes,
        pid=p.command(["shell", "pidof", PKG], check=False).strip())


if __name__ == "__main__":
    main()
