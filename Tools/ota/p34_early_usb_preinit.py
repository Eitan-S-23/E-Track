"""Bounded witness for USB MSC entry while SD startup is not complete."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host

AREA = ROOT / ".cache/p34-early-fault"


def extract(text, name):
    matches = list(re.finditer(r"(?m)^usb_sts_type " + name + r"\([^\n]*\)\s*\n\{", text))
    host.cli.require(len(matches) == 1, "ambiguous function " + name)
    start = matches[0].start()
    end = text.find("\n}", matches[0].end())
    host.cli.require(end >= 0, "unterminated function " + name)
    return text[start:end+2] + "\n"


def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "usb-preinit1")
    cli.require(not out.exists(), "preserve witness evidence")
    for name in ("functions.inc", "witness.exe", "compile.log", "compile.json", "run.log", "run.json", "result.json"):
        store.checked(out / name)
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out / "host" / key.lower())
    prepared = store.read(AREA / "prepared.json")
    for record in prepared["sources"] + prepared["implementation"]:
        cli.require(cli.record(record["path"]) == record, "snapshot drift")
    disk = AREA / "f/Libraries/USB_MSC/msc_diskio.cpp"
    bot = AREA / "f/Libraries/USB_MSC/msc_class/msc_bot_scsi.c"
    harness = ROOT / "tests/boot/test_p34_early_usb_preinit.cpp"
    paths = [Path(__file__), harness, disk, bot, AREA / "prepared.json",
             AREA / "f/Libraries/USB_MSC/msc_diskio.h",
             AREA / "f/USER/HAL/HAL.cpp", AREA / "f/USER/HAL/HAL_SD_CARD.cpp",
             AREA / "f/Libraries/SdFat/src/SdCard/SdioCard_AT32.cpp",
             AREA / "f/MDK-ARM_F435/Platform/Core/at32_sdio.c"]
    records = [cli.record(p) for p in paths]
    pieces = [extract(disk.read_text(encoding="utf-8"), n) for n in ("msc_disk_capacity", "msc_disk_read")]
    pieces += [extract(bot.read_text(encoding="utf-8"), n) for n in
               ("bot_scsi_capacity", "bot_scsi_check_address", "bot_scsi_read10")]
    env = host.environment(store, out)
    inc = store.raw(out / "functions.inc", "\n".join(pieces).encode("utf-8"))
    host.command(store, out, "compile", ["D:/install/mingw64/bin/g++.exe", "-std=c++11", "-O2",
                 "-Wall", "-Wextra", "-Werror", "-I" + str(out), harness, "-o", out / "witness.exe"], env, 60)
    log = host.command(store, out, "run", [out / "witness.exe"], env, 30)
    cli.require(b"EARLY_USB_PREINIT_WITNESS cases=4 backend_called_before_ready=1" in log, "missing witness")
    cli.require(records == [cli.record(p) for p in paths], "source changed")
    store.write(out / "result.json", dict(result="EARLY_USB_PREINIT_WITNESS", cases=4, inputs=records,
                 generated=inc, artifact=cli.record(out / "witness.exe"),
                 receipts=[cli.record(out / (n + ".json")) for n in ("compile", "run")],
                 finding="Nonzero capacity permits read backend call without initialization readiness gate",
                 limits=["Host structs/stubs; not an ABI or actual interrupt-timing test",
                         "Capacity-known, initialization-incomplete state is modeled, not device-observed",
                         "Does not claim every boot or request fails; backend rejection still returns USB_FAIL"],
                 hardware=False, independent_acceptance=False))
    print(log.decode().strip())


if __name__ == "__main__":
    main()
