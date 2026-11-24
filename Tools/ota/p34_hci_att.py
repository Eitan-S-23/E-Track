"""Offline target-bound HCI/ACL/L2CAP/ATT decoding, never a throughput verdict."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import runpy
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("p34_snoop_export", ROOT / "Tools/ota/p34_hci_export.py")
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)
require = EXPORT.require


def analyze(data, peer):
    require(re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", peer), "exact peer address required")
    wanted = bytes.fromhex(peer.replace(":", ""))[::-1]
    summary = EXPORT.snoop_summary(data)
    require(summary["truncated_packets"] == summary["reported_drops"] == 0,
            "truncated/lossy capture cannot establish the corruption boundary")
    connections, handles, pending, rows = [], {}, {}, []
    at, index = 16, 0
    while at < len(data):
        _, size, flags, _, stamp = struct.unpack_from(">IIIIQ", data, at)
        packet = data[at + 24:at + 24 + size]
        at += 24 + size
        index += 1
        incoming = bool(flags & 1)
        if packet[0] == 4:
            if packet[1] == 0x3e and len(packet) >= 5 and packet[3] in (1, 0x0a):
                if packet[4] != 0:
                    continue
                minimum = 22 if packet[3] == 1 else 34
                require(len(packet) >= minimum, "short LE connection event")
                handle = int.from_bytes(packet[5:7], "little")
                require(handle not in handles, "connection handle reused without disconnect")
                if packet[9:15] == wanted:
                    connection = dict(generation=len(connections) + 1, handle=handle,
                        peer=peer.upper(), address_type=packet[8], role=packet[7],
                        start_record=index, start_timestamp=stamp, disconnected=False)
                    connections.append(connection)
                    handles[handle] = connection
                else:
                    handles[handle] = None
            elif packet[1] == 5:
                require(len(packet) == 7, "short disconnect event")
                if packet[3] == 0:
                    handle = int.from_bytes(packet[4:6], "little")
                    require(not any(key[0] == handle for key in pending), "disconnect during partial target L2CAP")
                    connection = handles.pop(handle, None)
                    if connection is not None:
                        connection.update(disconnected=True, end_record=index, end_timestamp=stamp)
            continue
        if packet[0] != 2:
            continue
        header = int.from_bytes(packet[1:3], "little")
        handle, boundary, broadcast = header & 0xfff, (header >> 12) & 3, header >> 14
        connection = handles.get(handle)
        if connection is None:
            continue
        require(broadcast == 0 and boundary in (0, 1, 2), "unexpected target ACL flags")
        key = (handle, incoming)
        fragment = packet[5:]
        if boundary in (0, 2):
            require(key not in pending, "new L2CAP start replaces unfinished target frame")
            require(len(fragment) >= 4, "short target L2CAP header")
            length, cid = struct.unpack_from("<HH", fragment)
            require(length <= 65535, "L2CAP bound")
            pending[key] = dict(length=length, cid=cid, data=fragment[4:],
                                start_record=index, start_timestamp=stamp)
        else:
            require(key in pending, "orphan target ACL continuation")
            pending[key]["data"] += fragment
        part = pending[key]
        require(len(part["data"]) <= part["length"], "target L2CAP overflow")
        if len(part["data"]) < part["length"]:
            continue
        del pending[key]
        if part["cid"] != 4:
            continue
        att = part["data"]
        require(att, "empty ATT frame")
        row = dict(generation=connection["generation"], handle=handle,
            direction="rx" if incoming else "tx", start_record=part["start_record"],
            end_record=index, start_timestamp=part["start_timestamp"], end_timestamp=stamp,
            opcode=att[0], att_hex=att.hex())
        if att[0] in (0x12, 0x52, 0x1b, 0x1d):
            require(len(att) >= 3, "short ATT value header")
            row.update(value_handle=int.from_bytes(att[1:3], "little"), value_hex=att[3:].hex())
        rows.append(row)
    require(not pending, "capture ends in a partial target L2CAP frame")
    return dict(result="TARGET_ATT_DECODED" if connections else "TARGET_CONNECTION_NOT_OBSERVED",
                peer=peer.upper(), connections=connections, att=rows,
                notifications=[row for row in rows if row["direction"] == "rx" and row["opcode"] in (0x1b, 0x1d)],
                capture=summary, throughput="NOT_MEASURED",
                limitation="address-bound connection events required; unknown pre-capture handles are not attributed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--peer", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
            sys.dont_write_bytecode, "explicit root and isolated no-bytecode Python required")
    guard = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
    out = guard["checked_output"](ROOT, args.out)
    require(not out.exists(), "preserve prior analysis")
    data = args.input.read_bytes()
    result = analyze(data, args.peer)
    result.update(input=dict(path=str(args.input.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()),
                  sources=[dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                           for path in (Path(__file__).resolve(), ROOT / "Tools/ota/p34_hci_export.py")])
    guard["write_json"](ROOT, out, result)
    print(json.dumps(dict(result=result["result"], connections=len(result["connections"]),
                         att_frames=len(result["att"]), notifications=len(result["notifications"]), out=str(out))))


if __name__ == "__main__":
    main()
