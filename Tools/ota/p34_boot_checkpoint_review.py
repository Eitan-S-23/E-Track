"""Targeted group16 reviewer-requested host faults; no device/build operations."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_boot_checkpoint_model as model


def test(out):
    cli, host = model.cli, model.host
    s = cli.Store(ROOT)
    out = s.checked(out)
    cli.require(not out.exists(), "preserve prior evidence")
    model.validate(s)
    paths = []
    for relative in ("r3/result.json", "extension1/result.json"):
        receipt = model.AREA / relative
        prior = s.read(receipt)
        for record in prior["sources"]:
            cli.require(cli.record(record["path"]) == record, "prior input drift")
            paths.append(Path(record["path"]))
        paths.append(receipt)
    fragment = ROOT / "tests/boot/p34_checkpoint_review.c"
    paths += [fragment, Path(__file__)]
    paths = sorted(set(paths))
    bound = [cli.record(p) for p in paths]
    generated = s.checked(out / "review.c")
    exe = s.checked(out / "review.exe")
    for name in ("compile.log", "compile.json", "run.log", "run.json", "result.json"):
        s.checked(out / name)
    env = host.environment(s, out)
    source = model.HARNESS.read_text(encoding="utf-8")
    substitutions = {"int main(void)": "int original_campaign_main(void)",
                     "void p34_model_checkpoint(": "void original_checkpoint("}
    for old, new in substitutions.items():
        cli.require(source.count(old) == 1, "unique generated anchor required")
        source = source.replace(old, new)
    s.raw(generated, (source + "\n" + fragment.read_text(encoding="utf-8")).encode())
    common = [ROOT / p for p in ("boot/src/boot_fw_header.c", "boot/src/boot_slot.c",
              "boot/src/boot_crc32.c", "boot/src/boot_sha256.c", "Libraries/EEPROM/eeprom_bcb.c")]
    args = ["D:/install/mingw64/bin/gcc.exe", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
            "-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=1", "-DP34_BOOT_APPLY_CHECKPOINT_BLOCKS=16",
            "-include", model.HOOK]
    args += ["-I" + str(ROOT / p) for p in ("boot/include", "Libraries", "Tools/ota")]
    args += ["-I" + str(model.AREA), generated, model.AREA / "boot_state_machine.c", *common, "-o", exe]
    host.command(s, out, "compile", args, env, 120)
    raw = host.command(s, out, "run", [exe], env, 600)
    cli.require(b"CHECKPOINT_REVIEW_PASS tears=336 io_faults=36 sequences=11 oracle_negatives=3" in raw,
                "incomplete targeted matrix")
    cli.require(bound == [cli.record(p) for p in paths], "source drift during test")
    s.write(out / "result.json", dict(result="CHECKPOINT_REVIEW_HOST_PASS", sources=bound,
            generated=cli.record(generated), executable=cli.record(exe), output=raw.decode().splitlines(),
            hardware=False, independent_acceptance=False, measured_speedup=False))
    print(raw.decode(), end="")


if __name__ == "__main__":
    model.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                      and sys.dont_write_bytecode, "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    test(parser.parse_args().out)
