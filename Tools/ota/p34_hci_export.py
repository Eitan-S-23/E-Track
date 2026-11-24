"""Bounded, local-only Bluetooth extraction from an authorized Android report."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-target50/hci-export"
REMOTE = "/data/user_de/0/com.android.shell/files/bugreports"
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_HCI = 64 * 1024 * 1024
MAX_ENTRIES = 20000


def require(value, message):
    if not value:
        raise ValueError(message)


def report_path(value):
    require(isinstance(value, str), "report path must be text")
    for parent in (REMOTE, "/bugreports"):
        if value.startswith(parent + "/"):
            leaf = value[len(parent) + 1:]
            require(re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*\.zip", leaf),
                    "report is not one safe ZIP leaf")
            return REMOTE + "/" + leaf
    raise ValueError("report outside authorized phone directory")


def completed_report(raw):
    lines = raw.decode("utf-8", "strict").splitlines()
    completed = [i for i, line in enumerate(lines) if line.startswith("OK:")]
    require(completed, "report did not complete; do not repeat")
    require(len(completed) == 1, "ambiguous report completion")
    index = completed[0]
    result = report_path(lines[index][3:])
    # Vendor progress callbacks can arrive after OK; retain the original bytes
    # and admit only progress there, never another BEGIN, failure or completion.
    for i, line in enumerate(lines):
        if i == index:
            continue
        require(re.fullmatch(r"PROGRESS:\d+/\d+", line) or
                (i < index and line.startswith("BEGIN:") and report_path(line[6:]) == result),
                "unexpected report progress or changed output path")
    return result


def snoop_summary(data):
    require(16 < len(data) <= MAX_HCI, "empty or oversized snoop file")
    require(data[:16] == b"btsnoop\x00" + struct.pack(">II", 1, 1002),
            "expected version1 HCI-UART BTSNOOP")
    at, packets, truncated, dropped = 16, 0, 0, 0
    types, first, last = {}, None, None
    while at < len(data):
        require(at + 24 <= len(data), "truncated snoop record header")
        original, included, flags, losses, timestamp = struct.unpack_from(">IIIIQ", data, at)
        at += 24
        require(0 < included <= original <= 65540 and at + included <= len(data),
                "invalid or incomplete snoop record")
        require(flags <= 3, "unknown snoop direction flags")
        packet = data[at:at + included]
        kind = packet[0]
        require(kind in (1, 2, 3, 4, 5), "unknown H4 packet type")
        if included == original:
            if kind in (1, 3):
                require(len(packet) >= 4 and len(packet) == 4 + packet[3], "invalid HCI command/SCO length")
            elif kind == 4:
                require(len(packet) >= 3 and len(packet) == 3 + packet[2], "invalid HCI event length")
            else:
                require(len(packet) >= 5, "short ACL/ISO header")
                length = int.from_bytes(packet[3:5], "little")
                if kind == 5:
                    length &= 0x3fff
                require(len(packet) == 5 + length, "invalid ACL/ISO length")
        truncated += included != original
        dropped = max(dropped, losses)
        types[kind] = types.get(kind, 0) + 1
        first = timestamp if first is None else first
        last = timestamp
        packets += 1
        require(packets <= 500000, "snoop packet count bound")
        at += included
    return dict(packets=packets, packet_types=types, truncated_packets=truncated,
                reported_drops=dropped, first_timestamp=first, last_timestamp=last,
                target_connection="NOT_ANALYZED", throughput="NOT_MEASURED")


def hci_members(blob):
    require(0 < len(blob) <= MAX_ARCHIVE, "report archive size bound")
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        entries = archive.infolist()
        require(len(entries) <= MAX_ENTRIES, "archive entry count bound")
        names = [item.filename for item in entries]
        require(len(names) == len(set(names)), "duplicate ZIP members")
        chosen, total = [], 0
        for item in entries:
            require(item.orig_filename == item.filename,
                    "ZIP member name was normalized or truncated")
            path = PurePosixPath(item.filename)
            require(not path.is_absolute() and ".." not in path.parts and
                    "\\" not in item.filename and "\x00" not in item.filename,
                    "unsafe ZIP member name")
            vendor_log = (path.parent == PurePosixPath("FS/data/misc/bluetooth/logs") and
                          re.fullmatch(r"bt_hci_\d{8}_\d{6}_d\.cfa", path.name))
            if ("btsnoop" not in path.name.lower() and not vendor_log) or item.is_dir():
                continue
            require(len(chosen) < 8 and 0 < item.file_size <= MAX_HCI and
                    not item.flag_bits & 1, "HCI member bound/encryption")
            total += item.file_size
            require(total <= MAX_HCI, "aggregate HCI byte bound")
            data = archive.read(item)
            require(len(data) == item.file_size, "HCI extraction length differs")
            try:
                summary = snoop_summary(data)
            except ValueError as error:
                summary = dict(format="UNVERIFIED", error=str(error), magic_hex=data[:16].hex())
            chosen.append((item.filename, data, summary))
        return chosen, [item.filename for item in entries
                        if any(word in item.filename.lower() for word in ("bluetooth", "btsnoop", "btsnooz"))]


def remote_preflight(c, p, out):
    parent = p.command(["shell", "readlink", "-f", REMOTE.rsplit("/", 1)[0]]).strip()
    require(parent == REMOTE.rsplit("/", 1)[0], "phone output parent resolves elsewhere")
    alias = p.command(["shell", "readlink", "/bugreports"]).strip()
    require(alias == REMOTE, "system report output alias changed")
    mode = p.command(["shell", "getprop", "persist.sys.bluetooth.btsnooplogmode"]).strip()
    require(mode == "full", "full HCI logging not active")
    for service in ("dumpstate", "dumpstatez", "bugreportd"):
        state = p.command(["shell", "getprop", "init.svc." + service]).strip()
        require(state in ("", "stopped"), "another system report owner is active")
    raw = p.command(["shell", "ls", "-ld", REMOTE], binary=True, check=False)
    last = json.loads((p.RUNTIME / "commands.jsonl").read_text().splitlines()[-1])
    if last["exit"] == 0:
        require(raw.startswith(b"d"), "phone report leaf is not an ordinary directory")
        resolved = p.command(["shell", "readlink", "-f", REMOTE]).strip()
        require(resolved == REMOTE, "phone report directory resolves elsewhere")
        before = p.command(["shell", "ls", "-1", REMOTE]).splitlines()
    else:
        require(last["exit"] == 1 and "No such file or directory" in last["stderr"] and
                "Permission denied" not in last["stderr"], "phone directory state unknown")
        before = []
    c.save(out / "preflight.json", dict(parent=parent, alias=alias, full_logging=True,
                                      before=before, phone_directory=REMOTE))
    return before


def collect(c, p, out, *, number=1):
    require(type(number) is int and number in (1, 2), "two-report authorization bound")
    before = remote_preflight(c, p, out)
    args = ["shell", "bugreportz", "-p"]
    c.save(out / "generation-intent.json", dict(command=args, maximum_seconds=900,
           authorized_directory=REMOTE, purpose="export proof" if number == 1 else "post-probe HCI evidence",
           report_number=number, maximum_reports=2, delete_existing=False, upload=False))
    print("Generating report %d/2; no BLE transfer" % number, flush=True)
    raw = p.command(args, timeout=900, binary=True, check=False)
    c.raw(out / "generation.stdout", raw)
    receipt = json.loads((p.RUNTIME / "commands.jsonl").read_text().splitlines()[-1])
    require(receipt["exit"] == 0, "report command failed; preserve original outcome")
    remote = completed_report(raw)
    require(PurePosixPath(remote).name not in before, "generator reused a pre-existing report")
    c.save(out / "generated.json", dict(remote=remote, report_number=number))
    require(p.command(["shell", "readlink", "-f", remote]).strip() == remote,
            "generated report resolves outside the approved directory")
    size = p.command(["shell", "stat", "-c", "%s", remote]).strip()
    require(size.isdigit() and 0 < int(size) <= MAX_ARCHIVE, "remote report size bound")
    digest = p.command(["shell", "sha256sum", remote]).split()[0]
    require(re.fullmatch(r"[0-9a-f]{64}", digest), "invalid remote report hash")
    print("Reading report once and extracting Bluetooth members only", flush=True)
    blob = p.command(["exec-out", "cat", remote], timeout=180, binary=True)
    require(len(blob) == int(size) and hashlib.sha256(blob).hexdigest() == digest,
            "report readback differs")
    require(p.command(["shell", "sha256sum", remote]).split()[0] == digest,
            "report changed during readback")
    selected, candidates = hci_members(blob)
    extracted = []
    for i, (name, data, summary) in enumerate(selected, 1):
        item = c.raw(out / ("hci-%02d.btsnoop" % i), data)
        extracted.append(dict(member=name, original=item, summary=summary))
    c.save(out / "archive.json", dict(remote=remote, bytes=len(blob), sha256=digest,
           bluetooth_member_names=candidates, extracted=extracted,
           whole_report_saved_on_host=False, phone_report_deleted=False))
    require(extracted, "report contains no exported BTSNOOP; preserve report, do not repeat")
    require(any(x["summary"].get("truncated_packets") == x["summary"].get("reported_drops") == 0
                for x in extracted), "no complete loss-free HCI export found")
    return dict(result="ORIGINAL_HCI_EXPORT_VERIFIED", extracted=extracted,
                physical_link_measurement=False, target_connection="NOT_ANALYZED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prove-export",))
    parser.add_argument("--tests", required=True, type=Path)
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
            sys.dont_write_bytecode, "explicit root and isolated no-bytecode Python required")
    out = AREA / "route-proof"
    io_api = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
    io_api["checked_output"](ROOT, out)
    require(not out.exists(), "spent report scope; inspect/retrieve originals, never replay")
    tests_path = io_api["checked_output"](ROOT, args.tests)
    tests = json.loads(tests_path.read_bytes())
    require({item["path"] for item in tests["sources"]} == {
        str(Path(__file__).resolve()), str(ROOT / "tests/ota/test_p34_hci_export.py")},
        "exact exporter and test source bindings required")
    for item in tests["sources"]:
        require(hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"],
                "exporter test source binding changed")
    require(tests["passed"], "exporter host tests required")
    api = runpy.run_path(str(ROOT / "Tools/ota/p34_capacity_session.py"))
    print("Verifying retained context and private USB route", flush=True)
    _, _, impl, c = api["context"](out)
    phone = impl.phone(c, "hci_report_phone")
    lock = c.load("hci_report_lock", ROOT / "Tools/ota/repeat_cycle.py")
    for name in ("preflight.json", "generation-intent.json", "generation.stdout", "generated.json",
                 "archive.json", "result.json", "phone", "failure-services.json"):
        c.checked(out / name)
    for i in range(1, 9):
        c.checked(out / ("hci-%02d.btsnoop" % i))
    c.checked(lock.RUNS / "device.lock")
    os.environ.update(c.environment())
    result = dict(result="HCI_EXPORT_INCOMPLETE")
    try:
        with lock.device_lock(), phone.usb(c, out / "phone") as p:
            try:
                result = collect(c, p, out)
            except Exception:
                try:
                    states = {name: p.command(["shell", "getprop", "init.svc." + name]).strip()
                              for name in ("dumpstate", "dumpstatez", "bugreportd")}
                except Exception as diagnostic_error:
                    states = dict(inspection_error=str(diagnostic_error))
                c.save(out / "failure-services.json", states)
                raise
        result["usb_closed"] = True
    except Exception as error:
        result.update(result="HCI_EXPORT_INCOMPLETE", error=type(error).__name__ + ": " + str(error))
    c.save(out / "result.json", result)
    print(json.dumps(result), flush=True)
    return 0 if result["result"] == "ORIGINAL_HCI_EXPORT_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
