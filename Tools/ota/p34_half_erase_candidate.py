"""Prepare/test/build a contained optional 32KiB installation erase candidate."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_pump_candidate as previous
import p34_batch_review as review

cli, host = previous.cli, previous.host
BASE, AREA = previous.AREA, ROOT / ".cache/p34-half-erase"
HEADER = ROOT / "Tools/ota/p34_half_erase.h"
COPIED_HEADER = "Libraries/OTA/ota_half_erase_plan.h"
OVERLAY = ("Libraries/OTA/ota_backup.c", "Libraries/OTA/ota_backup.h",
           "Libraries/W25Q128/qspi_cmd_en25qh128a.cpp", "Libraries/W25Q128/qspi_cmd_en25qh128a.h",
           "USER/HAL/HAL_OTA_Package.cpp", COPIED_HEADER)


def prepare(s):
    fw = s.checked(AREA / "f")
    cli.require(not fw.exists(), "preserve candidate source")
    proof, report = review.load_report(s, ROOT / ".cache/p34-pump-batch12/trials/measure")
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30264, "confirmed30264 required")
    manifest = s.read(BASE / "build/source.json")
    copies = []
    for item in manifest["files"]:
        src = s.checked(item["path"])
        cli.require(cli.record(src) == item, "built base source changed")
        copies.append((src, s.checked(fw / src.relative_to(BASE / "f"))))
    target = s.checked(fw / COPIED_HEADER)
    for src, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    shutil.copyfile(HEADER, target)
    s.write(AREA / "prepared.json", dict(base=cli.record(BASE / "build/source.json"), predecessor=proof,
        header=cli.record(HEADER), copied_header=cli.record(target), hardware=False))
    print("HALF_ERASE_SOURCE_PREPARED", len(copies))


def sources(s):
    prepared = s.read(AREA / "prepared.json")
    cli.require(prepared["base"] == cli.record(BASE / "build/source.json") and
                prepared["header"] == cli.record(HEADER) and
                (AREA / "f" / COPIED_HEADER).read_bytes() == HEADER.read_bytes(), "prepared input changed")
    for item in s.read(BASE / "build/source.json")["files"]:
        src = Path(item["path"])
        relative = src.relative_to(BASE / "f")
        cli.require(cli.record(src) == item, "base source changed")
        if relative.as_posix() not in OVERLAY:
            cli.require((AREA / "f" / relative).read_bytes() == src.read_bytes(), "unrelated candidate change")
    paths = [Path(__file__), HEADER, ROOT / "Tools/ota/p34_half_erase_tests.py",
             ROOT / "tests/ota/test_p34_half_erase_plan.c", ROOT / "tests/ota/test_p34_half_erase_backup.c",
             ROOT / "tests/ota/p34_half_erase_hal.cpp", ROOT / "tests/ota/test_ota_backup.c",
             ROOT / "tests/ota/test_qspi_install_restore.py", ROOT / "Tools/ota/p34_erase_candidate.py",
             ROOT / ".cache/p34-erase/tests/latest.json", ROOT / ".cache/p34-erase/tests/r2/result.json"]
    paths += [AREA / "f" / name for name in OVERLAY]
    return [cli.record(p) for p in paths]


def build(s):
    ref = s.read(AREA / "tests/latest.json")["report"]
    cli.require(cli.record(ref["path"]) == ref, "tests changed")
    tested = s.read(ref["path"])
    cli.require(tested["result"] == "HALF_ERASE_HOST_PASS" and tested["sources"] == sources(s), "current tests required")
    fw, bld, out = (s.checked(AREA / x) for x in ("f", "b", "build"))
    cli.require(not bld.exists() and not out.exists(), "preserve build")
    s.checked(AREA / "install")
    args = [str(x).replace(str(BASE), str(AREA)) for x in s.read(BASE / "build/configure.json")["command"]]
    args = [x + " -DCONFIG_OTA_INSTALL_HALF_ERASE=1" if x.startswith("-DCMAKE_CXX_FLAGS:STRING=") else x for x in args]
    cli.require(sum("CONFIG_OTA_INSTALL_HALF_ERASE=1" in x for x in args) == 1, "candidate flag missing")
    s.write(out / "source.json", dict(base=cli.record(BASE / "build/source.json"), overlays=list(OVERLAY),
        files=[cli.record(p) for p in sorted(fw.rglob("*")) if p.is_file()]))
    env = host.environment(s, out)
    host.command(s, out, "configure", args, env, 180)
    raw = host.command(s, out, "build", [args[0], "--build", bld, "--target", "X_Track_App_GCC", "--parallel", "6"], env, 900)
    def normalized(data):
        return previous.previous.review.warnings(data.replace(b"p34-half-erase", b"p34-pump-cadence"))
    old, new = normalized((BASE / "build/build.log").read_bytes()), normalized(raw)
    value = dict(result="HALF_ERASE_APP_BUILT", artifacts=[cli.record(bld / "app-gcc" / ("X-Track-App-GCC" + ext))
        for ext in (".bin", ".elf", ".map", ".hex")], warnings=sum(new.values()), new_warnings=dict(new-old),
        errors=raw.count(b"error:"), boot_built=False, hardware=False, source=cli.record(out / "source.json"), tests=ref)
    s.write(out / "result.json", value)
    cli.require(not value["new_warnings"] and not value["errors"], "new build diagnostics need review")
    print(json.dumps(value))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("prepare", "launch", "worker"))
    a = p.parse_args()
    s = cli.Store(ROOT)
    if a.mode == "prepare": prepare(s)
    else:
        owner = cli.load_module("half_erase_build_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        if a.mode == "launch":
            print(owner.owned.launch(s.checked(AREA / "runtime/build-001"), Path(__file__), ["worker"], 1500))
        else:
            cli.require(owner.owned.in_job(), "finite build owner required")
            build(s)
