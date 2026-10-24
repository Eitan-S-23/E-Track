"""Full passive target/Boot readback and same-code symbol-bound confirmation."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import (ROOT, PassiveMCU, REGISTERS, SYMBOLS, fingerprint, h,
                     inspect_mcu, runtime_observations)


def same_executable(old, current):
    h.require(len(old) == len(current) and len(old) >= 0x460 and
              old[:0x400] == current[:0x400] and old[0x460:] == current[0x460:],
              "symbol reuse requires byte-identical executable outside the firmware header")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-inputs", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "explicit root and isolated Python required")
    out = h.checked(args.out)
    for name in ("full", "state", "result.json"):
        h.checked(out / name)
    prior, reference = h.read_json(args.prior_inputs), h.read_json(args.reference)
    target = h.pinned(reference["target"]).read_bytes()
    same_executable(h.pinned(prior["images"]["target"]["image"]).read_bytes(), target)
    h.fresh(out)
    inspect_mcu(h.fresh(out / "full"), args.prior_inputs)
    full = h.read_json(out / "full/result.json")
    current = h.pinned(full["app_image"]).read_bytes()
    h.require(current == target and full["firmware"]["version_code"] == 30288 and full["boot_matches_prior"],
              "final full image/Boot mismatch; do not reset or replay OTA")
    device = PassiveMCU(prior, out / "state")
    bound = device.bind("target")
    fields = {key: (bound["table"][name][0], 4 if key == "jedec" else 1)
              for key, name in SYMBOLS.items() if key not in ("session", "rtt", "main_loop", "health")}
    session = bound["table"][SYMBOLS["session"]][0]
    fields.update({key: (session + offset, 1) for key, offset in bound["offsets"].items()})
    fields.update({key: (address, 4) for key, address in REGISTERS.items()})
    fields.update(header_after=(0x08010400, 96), rtt_signature=(bound["rtt"], 16))
    health = bound["table"][SYMBOLS["health"]][0]
    reads = dict(health0=36, health1=36, **{name: size for name, (_, size) in fields.items()})
    commands = [("health0", health, 36), "sleep 1000", ("health1", health, 36)]
    commands += [(name, address, size) for name, (address, size) in fields.items()]
    data, _, directory = device.execute(commands, reads, "confirmation", seconds=120)
    h.require(data["header_after"] == current[0x400:0x460] and data["rtt_signature"][:10] == b"SEGGER RTT",
              "state/image binding changed")
    state = runtime_observations(data)
    h.require(all(state[k] for k in ("confirmed", "ota_idle", "fault_free", "same_boot_advancing")),
              "final confirmation/runtime not qualified")
    h.save(out / "result.json", dict(result="FULL_TARGET_BOOT_AND_CONFIRMATION_VERIFIED", full=fingerprint(out / "full/result.json"),
        state=state, originals=[fingerprint(p) for p in sorted(directory.glob("*.bin"))],
        symbol_basis="30287 ELF/map; all target executable bytes outside the 96-byte version header are identical",
        no_halt_reset_or_flash=True))


if __name__ == "__main__":
    main()
