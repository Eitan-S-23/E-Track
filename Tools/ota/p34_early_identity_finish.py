"""Recheck suspect recovery once, decode ETSL payloads, preserve native side effects."""
import hashlib
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_identity as identity
import p34_readonly_batch as batch


def slot(raw, expected_type):
    cli = identity.cli
    cli.require(len(raw) == 0x100000 and raw[:4] == b"ETSL" and raw[4] == expected_type and
                raw[5:8] == b"\xff"*3 and raw[28:32] == b"TMOC", "invalid/uncommitted ETSL header")
    length, crc, version = struct.unpack_from("<III", raw, 8)
    cli.require(0x460 <= length <= 0xf0000, "slot length invalid")
    payload = raw[0x1000:0x1000+length]
    value = dict(version=version, bytes=length, payload_sha256=hashlib.sha256(payload).hexdigest(),
                 expected_crc=crc, actual_crc=zlib.crc32(payload), payload_offset=0x1000,
                 committed=True, slot_type=expected_type)
    try:
        value["image"] = identity.image_identity(payload)
        cli.require(value["image"]["version"] == version and value["image"]["bytes"] == length and
                    raw[20:28].hex() == value["image"]["stored_sha256"][:16], "slot/image metadata mismatch")
        cli.require(value["actual_crc"] == crc, "slot payload CRC mismatch")
        value["status"] = "HEADER_AND_PAYLOAD_IDENTITY_VERIFIED"
    except RuntimeError as error:
        value.update(status="NOT_ADMISSIBLE", reason=str(error))
    return value


def main():
    cli = identity.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit root required")
    store = cli.Store(ROOT)
    out = store.checked(identity.AREA / "summary.json")
    cli.require(not out.exists(), "preserve summary")
    post = store.read(identity.AREA / "post/result.json")
    cli.require(post["result"] == "IDLE_XIP_OBSERVED", "post-read idle check missing")
    regions = dict(core_before=(0xe000edf0, 4), vtor_before=(0xe000ed08, 4), qspi_before=(0xa0001010, 4),
                   recovery=(0x90200000, 0x100000), qspi_after=(0xa0001010, 4),
                   vtor_after=(0xe000ed08, 4), core_after=(0xe000edf0, 4))
    verify = identity.AREA / "verify-recovery"
    batch.run(verify, regions, seconds=90)
    word = lambda n: int.from_bytes((verify / (n+".bin")).read_bytes(), "little")
    cli.require(not (word("core_before") | word("core_after")) & (1 << 17) and
                word("vtor_before") == word("vtor_after") == 0x08010000 and
                all(word(n) & (1 << 20) and not word(n) & (7 << 16) for n in ("qspi_before", "qspi_after")),
                "verification phase/mapping changed")
    slots = {n: slot((identity.AREA / "nor" / (n+".bin")).read_bytes(), kind)
             for n, kind in (("candidate", 1), ("backup", 2), ("recovery", 4))}
    same = (verify / "recovery.bin").read_bytes() == (identity.AREA / "nor/recovery.bin").read_bytes()
    logs, writes, receipts = [], [], []
    for stage in ("initial", "idle", "nor", "post", "verify-recovery"):
        area = identity.AREA / stage
        for p in sorted(area.iterdir()):
            if p.is_file():
                receipts.append(cli.record(p))
        text = (area / "sdk.log").read_text(errors="replace")
        calls = re.findall(r"CPU_WriteMem\((\d+) bytes @ (0x[0-9A-Fa-f]+)\)", text)
        writes.extend(dict(stage=stage, bytes=int(size), address=int(address, 16)) for size, address in calls)
        logs.append(dict(stage=stage, sdk_log=cli.record(area / "sdk.log"), cpu_write_calls=len(calls)))
    cli.require(all(w["address"] in (0xe0001000, 0xe000ed88) and w["bytes"] == 4 for w in writes),
                "unexpected SDK target-write address; preserve logs and stop")
    store.write(out, dict(result="PHYSICAL_IMAGE_INVENTORY_WITH_RECOVERY_FAILURE", slots=slots,
        recovery_repeat_identical=same, sdk_write_calls=writes, sdk_logs=logs,
        inputs=[cli.record(Path(__file__)), cli.record(Path(batch.__file__)), cli.record(Path(identity.__file__))]+receipts,
        hardware=True, flash_commands=0, reset_commands=0, halt_commands=0, bus_level_read_only=False,
        warning="SDK attachment writes DWT CTRL and CPACR; values/restore not independently verified",
        early_safety="Old App images do not inherit R2 proof", recovery_admitted=False,
        mutations_blocked=True, atomic_snapshot=False))
    print("PHYSICAL_IMAGE_INVENTORY", slots, "recovery_repeat_identical", same, "SDK write calls", len(writes))


if __name__ == "__main__":
    main()
