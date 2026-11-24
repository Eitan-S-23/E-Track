"""Offline report of original readbacks, including failed recovery and SDK audit."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_identity as identity
import p34_early_identity_finish as decoder


def main():
    cli = identity.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(identity.AREA / "summary.json")
    cli.require(not out.exists(), "preserve summary")
    paths = [Path(__file__), Path(decoder.__file__), Path(identity.__file__),
        ROOT / ".cache/p34-sha-candidate/f/Libraries/OTA/ota_slot_header.c",
        ROOT / ".cache/p34-sha-candidate/f/Libraries/OTA/ota_layout.h",
        ROOT / ".cache/p34-app-handoff/result.json"]
    inputs, writes, mru = [], [], []
    for stage in ("initial", "idle", "nor", "post", "verify-recovery"):
        area = identity.AREA / stage
        result = store.read(area / "result.json")
        for record in result["files"]:
            cli.require(cli.record(record["path"]) == record, "readback drift")
        receipt = store.read(area / "command.json")
        cli.require(receipt["exit"] == 0 and cli.record(receipt["log"]["path"]) == receipt["log"], "command receipt drift")
        inputs.extend(cli.record(p) for p in sorted(area.iterdir()) if p.is_file())
        for size, address in re.findall(r"CPU_WriteMem\((\d+) bytes @ (0x[0-9A-Fa-f]+)\)",
                                        (area / "sdk.log").read_text(errors="replace")):
            writes.append(dict(stage=stage, bytes=int(size), address=address))
        mru.append(dict(stage=stage, before=result["mru_before"], after=result["mru_after"]))
    slots = {}
    for name, kind in (("candidate", 1), ("backup", 2), ("recovery", 4)):
        raw = (identity.AREA / "nor" / (name+".bin")).read_bytes()
        slots[name] = decoder.slot(raw, kind)
    known = store.read(paths[-1])["groups"]
    cli.require(slots["candidate"]["payload_sha256"] == known["measure"]["image"]["sha256"] and
                slots["backup"]["payload_sha256"] == known["bootstrap"]["image"]["sha256"], "known payload mismatch")
    same = (identity.AREA / "nor/recovery.bin").read_bytes() == (identity.AREA / "verify-recovery/recovery.bin").read_bytes()
    raw = (identity.AREA / "nor/candidate.bin").read_bytes()
    bad = bytearray(raw); bad[0] ^= 1
    try:
        decoder.slot(bad, 1)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("invalid slot magic accepted")
    bad = bytearray(raw); bad[0x1500] ^= 1
    cli.require(decoder.slot(bad, 1)["status"] == "NOT_ADMISSIBLE", "corrupt payload accepted")
    store.write(out, dict(result="PHYSICAL_IDENTITIES_AND_BLOCKERS_RECORDED", inputs=[cli.record(p) for p in paths]+inputs,
        slots=slots, recovery_repeat_identical=same, decoder_checks=3, mru_observations=mru,
        sdk_target_writes=writes, sdk_write_audit_passed=False,
        failed_audit="p34_early_identity_finish rejected DHCSR/DEMCR writes beyond its initial DWT/CPACR allowlist",
        interpretation="Commander command lists contain no flash/reset/halt commands; SDK attachment is not bus-level read-only",
        transient_debug_state_proven_unchanged=False, hardware=True,
        recovery_admitted=False, replacement_ready=False, performance_evidence=False,
        next_action="offline safe recovery/candidate transition plan and original reviewer assessment; no automatic repair"))
    print("PHYSICAL_IDENTITIES_AND_BLOCKERS_RECORDED", "candidate", slots["candidate"]["version"],
          "backup", slots["backup"]["version"], "recovery", slots["recovery"]["version"],
          "recovery_status", slots["recovery"]["status"], "repeat_identical", same, "sdk_write_calls", len(writes))


if __name__ == "__main__":
    main()
