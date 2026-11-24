"""Bounded source-binding extension; preserve the original r3 source/evidence."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_boot_checkpoint_model as model


def test(out):
    cli, host = model.cli, model.host
    store = cli.Store(ROOT)
    out = store.checked(out)
    cli.require(not out.exists(), "preserve extension evidence")
    model.validate(store)
    prior_path = model.AREA / "r3/result.json"
    prior = store.read(prior_path)
    cli.require(prior["result"] == "BOOT_CHECKPOINT_HOST_MODEL_PASS", "r3 required")
    for record in prior["sources"]:
        cli.require(cli.record(record["path"]) == record, "r3 input drift")
    extension = ROOT / "tests/boot/p34_checkpoint_extension.c"
    paths = [Path(r["path"]) for r in prior["sources"]]
    paths += [prior_path, extension, Path(__file__), ROOT / "Tools/ota/p34_install_cost.py",
              ROOT / "Tools/ota/p34_session.py",
              ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"]
    bound = [cli.record(p) for p in paths]
    generated = store.checked(out / "extension.c")
    store.checked(out / "result.json")
    for group in (4, 16):
        store.checked(out / ("g%d.exe" % group))
        for tag in ("compile", "run"):
            for suffix in (".log", ".json"):
                store.checked(out / ("g%d-%s%s" % (group, tag, suffix)))
    env = host.environment(store, out)
    source = model.HARNESS.read_text(encoding="utf-8")
    cli.require(source.count("int main(void)") == 1, "unique main required")
    store.raw(generated, (source.replace("int main(void)", "int original_campaign_main(void)")
                         + "\n" + extension.read_text(encoding="utf-8")).encode("utf-8"))
    common = [ROOT / p for p in ("boot/src/boot_fw_header.c", "boot/src/boot_slot.c",
              "boot/src/boot_crc32.c", "boot/src/boot_sha256.c", "Libraries/EEPROM/eeprom_bcb.c")]
    results = {}
    for group in (4, 16):
        name = "g%d" % group
        exe = out / (name + ".exe")
        args = ["D:/install/mingw64/bin/gcc.exe", "-std=c99", "-O2", "-Wall", "-Wextra",
                "-Werror", "-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=1",
                "-DP34_BOOT_APPLY_CHECKPOINT_BLOCKS=%d" % group, "-include", model.HOOK]
        args += ["-I" + str(ROOT / p) for p in ("boot/include", "Libraries", "Tools/ota")]
        args += ["-I" + str(model.AREA), generated, model.AREA / "boot_state_machine.c",
                 *common, "-o", exe]
        host.command(store, out, name + "-compile", args, env, 120)
        raw = host.command(store, out, name + "-run", [exe], env, 180)
        cli.require(b"CHECKPOINT_EXTENSION_PASS" in raw, "missing extension oracle")
        results[name] = raw.decode().splitlines()
        print(raw.decode(), end="", flush=True)
    cli.require(bound == [cli.record(p) for p in paths], "source changed during extension")
    store.write(out / "result.json", dict(result="CHECKPOINT_EXTENSION_PASS", sources=bound,
                generated=cli.record(generated), variants=results, hardware=False,
                independent_acceptance=False, measured_speedup=False))


if __name__ == "__main__":
    model.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                      and sys.dont_write_bytecode, "isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    test(parser.parse_args().out)
