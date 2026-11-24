"""Bind existing App artifacts for pre-initialization fault-path review, no build."""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_boot_checkpoint_model as model
import p34_boot_candidate as toolchain

AREA = ROOT / ".cache/p34-app-handoff"
APP = ROOT / ".cache/p34-sha-candidate"


def main():
    cli, host = model.cli, model.host
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    s = cli.Store(ROOT); s.checked(AREA)
    cli.require(not AREA.exists(), "preserve existing evidence")
    build = s.read(APP / "build/result.json")
    assets = s.read(APP / "assets/result.json")
    records = build["artifacts"] + [build["source"]]
    records += [assets["groups"][n]["target"] for n in ("bootstrap", "measure")]
    for record in records:
        cli.require(cli.record(record["path"]) == record, "App binding mismatch")
    source = s.read(Path(build["source"]["path"]))
    for record in source["files"]:
        cli.require(cli.record(record["path"]) == record, "App source drift")
    inputs = [APP / "build/result.json", APP / "assets/result.json", Path(__file__),
              ROOT / "Tools/ota/p34_install_cost.py", ROOT / "Tools/ota/p34_boot_candidate.py"]
    records += [cli.record(p) for p in inputs]
    s.checked(AREA / "elf.bin"); s.checked(AREA / "result.json")
    for tag in ("objcopy", "symbols", "disassembly", "sections"):
        for suffix in (".log", ".json"): s.checked(AREA / (tag + suffix))
    env = host.environment(s, AREA)
    elf = Path(next(r["path"] for r in build["artifacts"] if r["path"].endswith(".elf")))
    raw = Path(next(r["path"] for r in build["artifacts"] if r["path"].endswith(".bin"))).read_bytes()
    arm = toolchain.ARM / "bin"
    host.command(s, AREA, "objcopy", [arm / "arm-none-eabi-objcopy.exe", "-O", "binary", elf, AREA / "elf.bin"], env, 60)
    cli.require((AREA / "elf.bin").read_bytes() == raw, "ELF load bytes differ from raw build")
    for tag, binary, args in (("symbols", "nm", ["-n", "-S"]),
                              ("disassembly", "objdump", ["-d"]), ("sections", "readelf", ["-h", "-S", "-A"])):
        host.command(s, AREA, tag, [arm / ("arm-none-eabi-" + binary + ".exe"), *args, elf], env, 60)
    groups = {}
    for n in ("bootstrap", "measure"):
        rec = assets["groups"][n]["target"]; data = Path(rec["path"]).read_bytes()
        cli.require(data[:0x400] + data[0x460:] == raw[:0x400] + raw[0x460:], "executable differs beyond finalized header")
        groups[n] = dict(image=rec, version=struct.unpack_from("<I", data, 0x408)[0],
                         msp=struct.unpack_from("<I", data)[0],
                         vectors=list(struct.unpack_from("<16I", data)), header_only_difference=True)
    for record in records:
        cli.require(cli.record(record["path"]) == record, "input changed")
    s.write(AREA / "result.json", dict(result="EXISTING_APP_ARTIFACTS_BOUND", inputs=records,
             groups=groups, extracted_binary=cli.record(AREA / "elf.bin"), hardware=False,
             roles=dict(current="30275 from previous verified observation",
                        predecessor="30274; not proof of current physical backup payload",
                        future_candidate="NOT_SELECTED", recovery="IDENTITY_NOT_ESTABLISHED"),
             preinit_safety="NOT_PROVEN", full_handoff_stack_bound=None))
    print("EXISTING_APP_ARTIFACTS_BOUND versions30274/30275; no hardware/build; preinit_safety NOT_PROVEN")


if __name__ == "__main__": main()
