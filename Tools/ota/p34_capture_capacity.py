"""Just-in-time capture capacity gate; archive only exact owned unused captures."""
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

import p34_session as cli
import p34_session_backend as backend

CAPTURE = re.compile(r"\d{13,20}-[0-9a-f]{24}")


def validate_query(events, health_raw, capture, known_configs, sentinel, target):
    h = json.loads(health_raw)
    cli.require(h["captureId"] == capture and h["healthy"] is True and h["lost"] == 0 and h["error"] is None and
                h["upgradeStarts"] == h["upgradeEnds"] == 0 and h["outcome"] is None, "not an unused healthy capture")
    cli.require(events.endswith(b"\n") and len(events) <= 16 * 1024 * 1024, "events boundary/size")
    rows = [json.loads(line) for line in events.splitlines()]
    cli.require(len(rows) >= 2 and [r["seq"] for r in rows] == list(range(1, len(rows) + 1)) and
                h["records"] == len(rows) and h["bytes"] == len(events), "capture count/byte mismatch")
    header = rows[0]
    cli.require(header["kind"] == "open" and header["captureId"] == capture and header["sentinel"] == sentinel and
                header["target"].lower() == target.lower() and type(header["pid"]) is int, "capture identity mismatch")
    cli.require(all(r["kind"] == "line" for r in rows[1:]) and h["producerLines"] == len(rows) - 1,
                "non-query records must not be archived by this gate")
    stamp = rows[1]["message"]
    cli.require(stamp.startswith("OTA_EXPERIMENT "), "missing original runtime stamp")
    cfg = json.loads(stamp[len("OTA_EXPERIMENT "):])
    cli.require(cfg["configSha256"] in known_configs and cfg["deviceAddress"].lower() == target.lower(),
                "capture is not from an explicitly owned configuration")
    return dict(pid=header["pid"], capture=capture, config_sha=cfg["configSha256"],
                events_sha=hashlib.sha256(events).hexdigest())


def ensure_capacity(s, p, out, *, package, sentinel, target, known_configs):
    out = s.checked(out)
    cli.require(not out.exists(), "preserve capacity gate receipt")
    for name in ("result.json", "inspection.json", "move-intent.json", "candidate", "mkdir-intent.json"):
        s.checked(out / name)
    def read(path, limit):
        raw = p.command(["exec-out", "run-as", package, "head", "-c", str(limit + 1), path], binary=True)
        cli.require(len(raw) <= limit, "capacity file bound")
        return raw
    def names(path):
        return p.command(["exec-out", "run-as", package, "ls", "-1", path]).splitlines()
    def exists(path):
        return p.command(["exec-out", "run-as", package, "ls", "-d", path], check=False).strip() == path
    checked = lambda path, new=False: backend.checked_phone_path(SimpleNamespace(PKG=package), p, path, new_leaf=new)
    cli.require(not p.command(["shell", "pidof", package], check=False).strip(), "App must be stopped before capacity gate")
    before = names("files/p34-observations")
    cli.require(len(before) == len(set(before)) and len(before) <= 8 and all(CAPTURE.fullmatch(n) for n in before),
                "unexpected capture inventory")
    if len(before) < 8:
        s.write(out / "result.json", dict(result="CAPTURE_SLOT_AVAILABLE", count=len(before), archived=False))
        return
    rejected = []
    chosen = None
    for capture in sorted(before, reverse=True):
        remote = "files/p34-observations/" + capture
        files = names(remote)
        if set(files) not in ({"events.jsonl", "health.json"}, {"events.jsonl", "health.json", "health.json.tmp"}):
            rejected.append(dict(capture=capture, reason="snapshot or unknown files protected"))
            continue
        checked(remote)
        for name in files:
            checked(remote + "/" + name)
        events = read(remote + "/events.jsonl", 16 * 1024 * 1024)
        health = read(remote + "/health.json", 8192)
        try:
            proof = validate_query(events, health, capture, known_configs, sentinel, target)
        except (RuntimeError, ValueError, KeyError, TypeError) as error:
            rejected.append(dict(capture=capture, reason=str(error)))
            continue
        chosen = (capture, remote, files, proof, events, health)
        break
    s.write(out / "inspection.json", dict(before=before, rejected=rejected, selected=chosen[0] if chosen else None))
    cli.require(chosen is not None, "no safely archivable owned unused capture; do not launch App")
    capture, remote, files, proof, events, health = chosen
    data = {"events.jsonl": events, "health.json": health}
    if "health.json.tmp" in files:
        data["health.json.tmp"] = read(remote + "/health.json.tmp", 8192)
    archived = {name:s.raw(out / "candidate" / name, raw) for name, raw in data.items()}
    cli.require(all(cli.record(v["path"]) == v for v in archived.values()) and
                all(read(remote + "/" + name, max(len(raw), 8192)) == raw for name, raw in data.items()), "archive readback changed")
    parent = "files/p34-archived-observations"
    if not exists(parent):
        checked(parent, True)
        s.write(out / "mkdir-intent.json", dict(path=parent))
        p.command(["exec-out", "run-as", package, "mkdir", parent])
    checked(parent)
    destination = parent + "/" + capture
    checked(destination, True)
    cli.require(not exists(destination) and not p.command(["shell", "pidof", package], check=False).strip(),
                "archive exists or App restarted")
    s.write(out / "move-intent.json", dict(source=checked(remote), destination=checked(destination, True), proof=proof, files=archived))
    p.command(["exec-out", "run-as", package, "mv", "-n", remote, destination])
    cli.require(not exists(remote) and set(names(destination)) == set(data) and
                all(read(destination + "/" + name, max(len(raw), 8192)) == raw for name, raw in data.items()), "archive move unresolved")
    remaining = names("files/p34-observations")
    cli.require(set(remaining) == set(before) - {capture} and len(remaining) == 7 and
                not p.command(["shell", "pidof", package], check=False).strip(), "capacity changed before launch")
    s.write(out / "result.json", dict(result="OWNED_UNUSED_CAPTURE_ARCHIVED", archived=True, no_delete=True,
        selected=capture, files=archived, remaining=remaining, count=7))
