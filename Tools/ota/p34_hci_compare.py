"""Compare one four-frame diagnostic with original, connection-bound HCI bytes."""
import binascii
import struct


def require(value, message):
    if not value:
        raise ValueError(message)


def frame(cmd, session, sequence, payload):
    data = b"\xa5\x5a" + struct.pack("<BBHH", cmd, session, sequence, len(payload)) + payload
    return data + struct.pack("<H", binascii.crc_hqx(data[2:], 0xffff))


def valid_frame(data):
    require(len(data) >= 10 and data[:2] == b"\xa5\x5a" and
            len(data) == 10 + int.from_bytes(data[6:8], "little") and
            binascii.crc_hqx(data[2:-2], 0xffff) == int.from_bytes(data[-2:], "little"),
            "invalid original protocol frame")


def compare(decoded, trial):
    require(decoded["result"] == "TARGET_ATT_DECODED" and
            decoded["capture"]["truncated_packets"] == decoded["capture"]["reported_drops"] == 0,
            "complete target-bound HCI decoding required")
    require(trial["window"] == 4 and trial["chunkBytes"] == 142 and trial["endSent"] is False,
            "only the non-installing four-frame142-byte discriminator is supported")
    writes = [bytes.fromhex(e["hex"]) for e in trial["events"] if e["kind"] == "write"]
    notifications = [bytes.fromhex(e["hex"]) for e in trial["events"] if e["kind"] == "notify"]
    require(len(writes) == 7 and [x[2] for x in writes] == [0, 1, 2, 2, 2, 2, 4],
            "unexpected command sequence; do not treat a different run as this probe")
    for data in writes:
        valid_frame(data)
    require([int.from_bytes(x[4:6], "little") for x in writes] == list(range(7)), "sequence differs")
    session = trial["session"]
    require(all(x[3] == session and len(x) == 142 for x in writes[2:6]) and
            all(x[8:-2] == writes[2][8:-2] for x in writes[2:6]) and writes[2][8:12] == bytes(4),
            "not four same-offset identical DATA frames")
    tx = [row for row in decoded["att"] if row["direction"] == "tx" and row["opcode"] == 0x52]
    matches = [tx[i:i + 7] for i in range(len(tx) - 6)
               if [row["value_hex"] for row in tx[i:i + 7]] == [x.hex() for x in writes] and
               len({(row["generation"], row["value_handle"]) for row in tx[i:i + 7]}) == 1]
    require(len(matches) == 1, "ambiguous or missing original GATT write sequence")
    sent = matches[0]
    generation = sent[0]["generation"]
    replies = [row for row in decoded["notifications"] if row["generation"] == generation and
               sent[0]["end_record"] < row["start_record"] < sent[-1]["start_record"]]
    require(len(notifications) >= 3, "original browser notification prefix missing")
    handles = {row["value_handle"] for row in replies if row["value_hex"] == notifications[0].hex()}
    require(len(handles) == 1, "unique INFO notification handle required")
    rx_handle = handles.pop()
    replies = [row for row in replies if row["value_handle"] == rx_handle]
    # Attribute declaration responses bind FFF1/FFF2, not guessed numeric handles.
    declarations = {}
    for row in decoded["att"]:
        raw = bytes.fromhex(row["att_hex"])
        if row["generation"] == generation and row["direction"] == "rx" and raw[:2] == b"\x09\x07":
            require((len(raw) - 2) % 7 == 0, "invalid characteristic declaration response")
            for at in range(2, len(raw), 7):
                _, props, handle, uuid = struct.unpack_from("<HBHH", raw, at)
                if uuid in (0xfff1, 0xfff2):
                    require(uuid not in declarations, "ambiguous characteristic declaration")
                    declarations[uuid] = (handle, props)
    require(declarations.get(0xfff1, (None, 0))[0] == rx_handle and
            declarations.get(0xfff2, (None, 0))[0] == sent[0]["value_handle"] and
            declarations[0xfff1][1] & 0x10 and declarations[0xfff2][1] & 0x04,
            "FFF1/FFF2 value handles/capabilities not proved")
    info, begin = notifications[:2]
    valid_frame(info)
    require(info[2] == 0x80 and info[24:56].hex() == trial["identity"]["imageSha256"] and
            int.from_bytes(info[20:24], "little") == trial["identity"]["version"], "INFO identity mismatch")
    require(begin == frame(0x81, session, 1, bytes((0, session)) + bytes(8)), "BEGIN state mismatch")
    expected = info + begin + b"".join(frame(0x82, session, seq, b"\0" + struct.pack("<II", 0, 1))
                                       for seq in range(2, 6))
    actual_hci = b"".join(bytes.fromhex(row["value_hex"]) for row in replies)
    actual_browser = b"".join(notifications)
    if actual_browser == expected:
        verdict = "EXPECTED_BYTES_IN_BROWSER" if actual_hci == expected else "HCI_BROWSER_INCONSISTENT"
    elif actual_hci == actual_browser:
        verdict = "CORRUPTION_ALREADY_PRESENT_AT_HCI"
    elif actual_hci == expected:
        verdict = "HCI_COMPLETE_BROWSER_DIFFERS"
    else:
        verdict = "HCI_BROWSER_DIFFER_BOTH_UNEXPECTED"
    gap = len(info) + len(begin) + 19
    missing_six = actual_browser == expected[:gap] + expected[gap + 6:]
    return dict(result=verdict, generation=generation, write_handle=sent[0]["value_handle"],
                notify_handle=rx_handle, tx_records=[row["start_record"] for row in sent],
                rx_records=[row["start_record"] for row in replies],
                expected_bytes=len(expected), hci_bytes=len(actual_hci), browser_bytes=len(actual_browser),
                notifications_byte_identical=[row["value_hex"] for row in replies] == [x.hex() for x in notifications],
                missing_ack3_prefix_hex=expected[gap:gap + 6].hex() if missing_six else None,
                hci_notification_hex=[row["value_hex"] for row in replies],
                browser_notification_hex=[x.hex() for x in notifications],
                scope="locates the observed boundary; does not distinguish MCU UART, module, or controller internals",
                throughput="NOT_MEASURED")


def link_parameters(data, connection):
    at, index, events = 16, 0, []
    while at < len(data):
        require(at + 24 <= len(data), "short snoop record header")
        _, length, _, _, stamp = struct.unpack_from(">IIIIQ", data, at)
        require(at + 24 + length <= len(data), "short snoop packet")
        packet = data[at + 24:at + 24 + length]
        at += 24 + length
        index += 1
        if not connection["start_record"] <= index <= connection["end_record"] or packet[:2] != b"\x04\x3e":
            continue
        require(len(packet) >= 4, "short LE event")
        sub, value = packet[3], None
        if sub in (1, 10, 3, 12):
            require(len(packet) >= 7, "short connection/PHY event")
            if packet[4] != 0 or int.from_bytes(packet[5:7], "little") != connection["handle"]:
                continue
            if sub == 12:
                require(len(packet) >= 9, "short PHY update")
                value = dict(kind="phy-update", tx_phy=packet[7], rx_phy=packet[8])
            else:
                offset = {1: 15, 10: 27, 3: 7}[sub]
                require(len(packet) >= offset + 6, "short connection parameters")
                interval, latency, timeout = struct.unpack_from("<HHH", packet, offset)
                value = dict(kind="connection" if sub in (1, 10) else "connection-update",
                             interval_ms=interval * 1.25, latency=latency, timeout_ms=timeout * 10)
        elif sub == 7:
            require(len(packet) >= 14, "short data-length event")
            if int.from_bytes(packet[4:6], "little") != connection["handle"]:
                continue
            tx, tt, rx, rt = struct.unpack_from("<HHHH", packet, 6)
            value = dict(kind="data-length", tx_octets=tx, tx_time_us=tt, rx_octets=rx, rx_time_us=rt)
        if value is not None:
            events.append(dict(record=index, timestamp=stamp, raw_hex=packet.hex(), **value))
    return events
