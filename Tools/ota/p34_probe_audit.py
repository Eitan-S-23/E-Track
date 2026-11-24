"""Offline binding and observed AP-write audit. Does not grant device permission."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
from recovery_entry.probe import CORE_READS
from recovery_entry.state_probe import STATE_WORDS
from recovery_entry.dap_probe import APP_LENGTH, APP_SHA


def writes_in_scope(log, action, metadata):
    core = {a + i for _, a, n in CORE_READS for i in range(0, n, 4)}
    allowed = core | (STATE_WORDS if action == "state" else set()) | set(range(0x08000000, 0x08000010, 4))
    rows, tar = [], []
    for line in log.splitlines():
        if "CPU_WriteMem" in line:
            raise ValueError("CPU write observed")
        if not re.search(r"JLINK\w*_(?:Write|CORESIGHT_Write)", line):
            continue
        match = re.fullmatch(r".*JLINK_CORESIGHT_WriteAPDPReg\((AP|DP) reg 0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+)\)", line)
        if match is None: raise ValueError("unknown SDK write spelling")
        port, register, value = match[1], int(match[2], 16), int(match[3], 16)
        valid = False
        if port == "DP":
            valid = (register == 2 and value in (0, 0xf0)) or (register == 1 and value in (0x50000040, 0x10000040, 0x40))
        elif register == 0:
            csw = metadata["ap_csw"]
            valid = value in (csw, (csw & ~0x37) | 2, (csw & ~0x37) | 0x12)
        elif register == 1:
            tar.append(value)
            valid = value in allowed or value == metadata["original_tar"] or (
                action == "image" and value % 1024 == 0 and 0x08010000 <= value < 0x08010000 + APP_LENGTH)
        if not valid: raise ValueError("write outside observed read-route scope")
        rows.append(dict(port=port, register=register, value=value))
    if not rows or not tar or tar[-1] != metadata["original_tar"]:
        raise ValueError("missing AP setup/TAR restoration trace")
    return rows


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / ".cache/p34-native-audit1/result.json")
    cli.require(not out.exists(), "preserve audit")
    manifests, paths, observed = [], [], []
    names = ([f"p34-native-probe-test{i}" for i in range(1, 9)] +
             [f"p34-native-settings{i}" for i in range(1, 8)] +
             ["p34-native-acquire1", "p34-native-dap1", "p34-native-dap2", "p34-native-state1", "p34-native-image1",
              "p34-native-reference2", "p34-entry-review1"])
    for name in names:
        area = store.checked(ROOT / ".cache" / name)
        for path in area.rglob("*"):
            store.checked(path)
            if path.is_file(): paths.append(cli.record(path))
        path = area / "plan.json"
        if not path.exists(): path = area / "result.json"
        if not path.exists(): continue  # A failed test still retains log, receipt and source.
        value = json.loads(path.read_text(encoding="utf-8"))
        for item in value.get("inputs", []):
            original = Path(item["path"])
            snapshot = area / "source" / original.relative_to(ROOT)
            check = snapshot if snapshot.exists() else original
            data = check.read_bytes()
            cli.require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"], "input binding drift")
        manifests.append(cli.record(path))
        if (area / "parent.json").exists():
            parent = store.read(area / "parent.json")
            cli.require(not parent["timeout"] and parent["exit"] in (0, 1), "uncertain worker lifetime")
            cli.require(parent["after_history"] == value["before_history"], "native history changed; disclose exact delta")
    for name, action in (("p34-native-dap2", "dap"), ("p34-native-state1", "state"), ("p34-native-image1", "image")):
        area = ROOT / ".cache" / name
        result = store.read(area / "worker.json")
        cli.require(result["close_returned"] and all(result["dap"][k] for k in ("tar_restored", "csw_restored", "dp_restored")), "restore/close missing")
        rows = writes_in_scope((area / "sdk.log").read_text(), action, result["dap"])
        cli.require(cli.record(Path(result["readback"]["path"])) == result["readback"], "raw readback drift")
        observed.append(dict(area=name, ap_dp_writes=len(rows), observed_api_writes_within_read_profile=True,
                             cpu_write_calls=0, proof_scope="logged SDK API calls; not all electrical transients"))
    # Mutant checks ensure that data writes and unknown API spellings cannot pass.
    base = ROOT / ".cache/p34-native-dap2"
    raw = (base / "sdk.log").read_text()
    metadata = store.read(base / "worker.json")["dap"]
    for mutant in ("CPU_WriteMem(4 bytes @ 0xE0001000)", "JLINK_WriteMem(0x20060000, 4)",
                   "JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x03, 0x00000000)",
                   "JLINK_CORESIGHT_WriteAPDPReg(DP reg 0x01, 0x54000040)"):
        try: writes_in_scope(raw + "\n" + mutant, "dap", metadata)
        except ValueError: pass
        else: raise RuntimeError("unsafe write mutant passed")
    app = (ROOT / ".cache/p34-native-image1/app-readback.bin").read_bytes()
    cli.require(hashlib.sha256(app).hexdigest() == APP_SHA and len(app) == APP_LENGTH, "fresh App binding")
    build = (ROOT / ".cache/p34-sha-candidate/b/app-gcc/X-Track-App-GCC.bin").read_bytes()
    cli.require(app[:0x400] == build[:0x400] and app[0x460:] == build[0x460:] and len(app) == len(build), "map-bearing build differs outside finalized header")
    selected = store.read(ROOT / ".cache/p34-native-probe-test8/result.json")
    for item in selected["inputs"]:
        cli.require(cli.record(Path(item["path"])) == item, "selected current input drift")
    for name in ("native_probe", "dap_probe", "state_probe", "probe"):
        path = ROOT / "Tools/ota/recovery_entry" / (name + ".py")
        text = path.read_text()
        ast.parse(text)
        cli.require(text.isascii() and all(line == line.rstrip() for line in text.splitlines()), "source style")
    store.write(out, dict(result="SCOPED_NATIVE_OBSERVATION_AUDIT_PASS", files=paths, manifests=manifests,
        observed=observed, write_parser_negative_checks=4, selected_tests=33,
        complete_app_matched=True, map_build_header_only_difference=True,
        native_history_changed=False, explicit_external_write_scope="C:/Users/SU/AppData/Roaming/SEGGER history/config only; no cleanup",
        device_execute_ready=False, historical_sdk_write_audit_passed=False,
        source=cli.record(Path(__file__))))
    print("SCOPED_NATIVE_OBSERVATION_AUDIT_PASS", len(paths), "files; 4 parser negatives; full App and map-bearing build matched")


if __name__ == "__main__":
    main()
