"""Check V2-only headers while preserving the historical V1 oracle unchanged."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import p3_1_verify_contract_alignment as v1


class HeaderSnapshot:
    def __init__(self, text):
        self.text = text

    def read_text(self, **kwargs):
        return self.text

    def relative_to(self, root):
        return Path("Libraries/OTA/ota_ble_frame.h")


def preprocess(enabled=None):
    cc = shutil.which(os.environ.get("CC", "gcc"))
    if cc is None:
        raise RuntimeError("a real C preprocessor is required")
    command = [cc, "-Werror", "-E", "-dM", "-x", "c"]
    if enabled is not None:
        command.append("-DP34_OTA_PIPELINE=" + str(enabled))
    command.append(str(v1.HEADER))
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return HeaderSnapshot(result.stdout)


def extension(text):
    commands, lengths = {}, {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or not cells[1].startswith("0x"):
            continue
        names, values = cells[0].split(" / "), cells[1].split(" / ")
        if len(names) != len(values):
            raise ValueError("v2 command table shape differs")
        for name, value in zip(names, values):
            if not re.fullmatch(r"[A-Z_]+2(?:_REPLY)?", name):
                raise ValueError("unexpected v2 command name")
            if name in lengths or not re.fullmatch(r"0x[0-9A-Fa-f]{2}", value):
                raise ValueError("duplicate or invalid v2 command")
            commands["OTA_BLE_CMD_" + name] = int(value, 16)
            lengths[name] = tuple(int(n) for n in cells[3].split(".."))
            if tuple(int(n) for n in cells[4].split("..")) != tuple(n + 10 for n in lengths[name]):
                raise ValueError("v2 frame length differs from payload plus framing")
    if len(commands) != 10:
        raise ValueError("incomplete v2 command table")
    return commands, lengths


def shared_contract():
    text = v1.CONTRACT.read_text(encoding="utf-8")
    statuses = v1.parse_hex_name_table(v1.slice_section(text, v1.SECTION_STATUS))
    if len(statuses) != 20:
        raise ValueError("incomplete shared ACK status table")
    info = v1.parse_offset_table(v1.slice_section(text, v1.SECTION_INFO))
    return dict(
        OTA_BLE_SYNC0=0xA5, OTA_BLE_SYNC1=0x5A,
        OTA_BLE_HEADER_SIZE=8, OTA_BLE_CRC_SIZE=2,
        OTA_BLE_CMD_GET_INFO=0, OTA_BLE_CMD_INFO=0x80,
        OTA_BLE_LEN_GET_INFO=0,
        OTA_BLE_LEN_INFO=max(off + size for off, size, _ in info),
        OTA_BLE_INFO_PROTO_VER=1, OTA_BLE_INFO_MAX_WINDOW_SEGS=32,
        OTA_BLE_SHA256_SIZE=32,
        **{"OTA_BLE_STATUS_" + name: value for value, name in statuses.items()})


def verify_v2(shared, actual, text):
    commands, lengths = extension(text)
    expected_commands = {k: v for k, v in shared.items() if k.startswith("OTA_BLE_CMD_")}
    expected_commands.update(commands)
    if {k: v for k, v in actual.items() if k.startswith("OTA_BLE_CMD_")} != expected_commands:
        raise ValueError("V2-only command map drift")
    expected = dict(shared)
    expected.update(commands)
    expected.update(OTA_BLE_PIPELINE_ENABLED=1, OTA_BLE_MAX_PAYLOAD=lengths["DATA2"][-1])
    for name in ("CAPS2", "CAPS2_REPLY", "BEGIN2", "END2", "ABORT2", "ACK_BEGIN2"):
        expected["OTA_BLE_LEN_" + name] = lengths[name][0]
    expected["OTA_BLE_LEN_DATA2_MIN"] = lengths["DATA2"][0]
    expected["OTA_BLE_BEGIN2_EPOCH_OFFSET"] = lengths["BEGIN2"][0] - 4
    if lengths["ACK_DATA2"] != lengths["ACK_END2"] or lengths["ACK_DATA2"] != lengths["ACK_ABORT2"]:
        raise ValueError("v2 ordinary ACK lengths differ")
    expected["OTA_BLE_LEN_ACK_OTHER2"] = lengths["ACK_DATA2"][0]
    if actual != expected:
        raise ValueError("V2-only constant drift, including private status or payload length")


class BleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.disabled = preprocess(0)
        cls.enabled = preprocess(1)
        cls.base = shared_contract()
        cls.actual = v1.read_defines(preprocess())
        cls.supplement = (ROOT / "docs/ota-ble-v2-contract.md").read_text(encoding="utf-8")

    def test_legacy_build_flag_cannot_restore_v1(self):
        self.assertEqual(v1.read_defines(self.disabled), self.actual)
        self.assertEqual(v1.read_defines(self.enabled), self.actual)
        self.assertEqual(self.actual["OTA_BLE_PIPELINE_ENABLED"], 1)

    def test_default_header_matches_v2_and_shared_identity_status_contracts(self):
        verify_v2(self.base, self.actual, self.supplement)

    def test_retired_commands_cannot_reappear_in_production_header(self):
        for index, name in enumerate(("BEGIN", "DATA", "END", "ABORT"), 1):
            for key, value in (("OTA_BLE_CMD_" + name, index),
                               ("OTA_BLE_CMD_ACK_" + name, 0x80 + index)):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    verify_v2(self.base, dict(self.actual, **{key: value}), self.supplement)

    def test_each_command_mutation_is_rejected_in_v2(self):
        for key in self.actual:
            if key.startswith("OTA_BLE_CMD_"):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    verify_v2(self.base, dict(self.actual, **{key: 0x70}), self.supplement)

    def test_missing_command_is_rejected(self):
        changed = dict(self.actual)
        del changed["OTA_BLE_CMD_DATA2"]
        with self.assertRaises(ValueError):
            verify_v2(self.base, changed, self.supplement)

    def test_private_status_or_command_is_rejected(self):
        for key in ("OTA_BLE_STATUS_PRIVATE", "OTA_BLE_CMD_PRIVATE"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_v2(self.base, dict(self.actual, **{key: 0x70}), self.supplement)

    def test_each_status_mutation_is_rejected(self):
        for key in self.actual:
            if key.startswith("OTA_BLE_STATUS_"):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    verify_v2(self.base, dict(self.actual, **{key: 0x70}), self.supplement)

    def test_each_length_and_credit_cap_mutation_is_rejected(self):
        for key in self.actual:
            if key.startswith("OTA_BLE_LEN_") or key in ("OTA_BLE_MAX_PAYLOAD", "OTA_BLE_INFO_MAX_WINDOW_SEGS"):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    verify_v2(self.base, dict(self.actual, **{key: self.actual[key] + 1}), self.supplement)

    def test_incomplete_or_duplicate_supplement_is_rejected(self):
        row = next(line for line in self.supplement.splitlines() if line.startswith("| ABORT2 |"))
        for text in (self.supplement.replace(row, ""), self.supplement + "\n" + row):
            with self.subTest(text=text[-40:]), self.assertRaises(ValueError):
                extension(text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
