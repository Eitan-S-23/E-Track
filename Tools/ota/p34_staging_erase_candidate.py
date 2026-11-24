"""Isolated staging erase-ahead host tests and GCC App-only candidate build."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host
import p34_crc_review as review

cli = host.cli
BASE = ROOT / ".cache/p34-ui-cadence-r2"
AREA = ROOT / ".cache/p34-staging-erase"
HEADER = ROOT / "Tools/ota/p34_staging_erase.h"
TEST = ROOT / "tests/ota/test_p34_staging_erase.cpp"
HAL = "USER/HAL/HAL_OTA_Staging.cpp"
COPIED_HEADER = "USER/HAL/ota_staging_erase.h"


def prepare(s):
    fw = s.checked(AREA / "f")
    cli.require(not fw.exists(), "preserve candidate source")
    manifest = s.read(BASE / "build/source.json")
    copies = []
    for item in manifest["files"]:
        src = s.checked(item["path"])
        cli.require(cli.record(src) == item, "verified base source changed")
        copies.append((src, s.checked(fw / src.relative_to(BASE / "f"))))
    target = s.checked(fw / COPIED_HEADER)
    for src, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    shutil.copyfile(HEADER, target)
    s.write(AREA / "prepared.json", dict(base=cli.record(BASE / "build/source.json"),
        header=cli.record(HEADER), copied_header=cli.record(target), hardware=False,
        next="Apply reviewed HAL-only overlay, then test the exact isolated source"))
    print("STAGING_ERASE_SOURCE_PREPARED", len(copies))


def sources(s):
    fw = AREA / "f"
    prepared = s.read(AREA / "prepared.json")
    cli.require(prepared["base"] == cli.record(BASE / "build/source.json") and
                prepared["header"] == cli.record(HEADER) and
                (fw / COPIED_HEADER).read_bytes() == HEADER.read_bytes(), "prepared input changed")
    for item in s.read(BASE / "build/source.json")["files"]:
        src = Path(item["path"])
        relative = src.relative_to(BASE / "f")
        cli.require(cli.record(src) == item, "base source changed")
        if relative.as_posix() != HAL:
            cli.require((fw / relative).read_bytes() == src.read_bytes(), "unrelated candidate change")
    paths = [Path(__file__), HEADER, TEST, fw / HAL, fw / "Libraries/OTA/ota_staging.c",
             ROOT / "tests/ota/test_ota_staging_hal.cpp"]
    paths += sorted((ROOT / "tests/ota/staging_hal_stubs").rglob("*.h"))
    return [cli.record(p) for p in paths]


def tests(s, attempt):
    out = s.checked(AREA / "tests" / attempt)
    cli.require(not out.exists(), "preserve host tests")
    before = sources(s)
    env = host.environment(s, out)
    fw = AREA / "f"
    results = {}
    for enabled in (0, 1):
        for reuse in (0, 1):
            tag = f"bulk{enabled}-qe{reuse}"
            exe = s.checked(out / (tag + ".exe"))
            args = ["D:/install/mingw64/bin/g++.exe", "-x", "c++", "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
                f"-DCONFIG_OTA_STAGING_BLOCK_ERASE={enabled}", f"-DCONFIG_OTA_STAGING_QE_REUSE={reuse}",
                "-I" + str(ROOT / "tests/ota/staging_hal_stubs"),
                "-I" + str(fw / "USER"), "-I" + str(fw / "Libraries"), TEST,
                fw / HAL, fw / "Libraries/OTA/ota_staging.c", "-o", exe]
            compiled = host.command(s, out, tag + "-compile", args, env, 120)
            cli.require(not re.search(rb"\bwarning:", compiled), "native compiler warning")
            data = host.command(s, out, tag, [exe], env, 120)
            cli.require(b"STAGING_ERASE_AHEAD=PASS" in data, "native PASS missing")
            results[tag] = data.decode().splitlines()[-1]
    cli.require(sources(s) == before, "tested source changed")
    s.write(out / "result.json", dict(result="STAGING_ERASE_HOST_PASS", hardware=False,
        sources=before, variants=results, warnings=0, errors=0))
    s.write(AREA / "tests/latest.json", dict(report=cli.record(out / "result.json")),
            replace=(AREA / "tests/latest.json").exists())
    print("STAGING_ERASE_HOST_PASS", results)


def build(s):
    ref = s.read(AREA / "tests/latest.json")["report"]
    cli.require(cli.record(ref["path"]) == ref, "test report changed")
    tested = s.read(ref["path"])
    cli.require(tested["result"] == "STAGING_ERASE_HOST_PASS" and tested["sources"] == sources(s), "current tests required")
    fw, bld, out = (s.checked(AREA / n) for n in ("f", "b", "build"))
    cli.require(not bld.exists() and not out.exists(), "preserve build")
    s.checked(AREA / "install")
    args = [str(x).replace(str(BASE), str(AREA)) for x in s.read(BASE / "build/configure.json")["command"]]
    args = [x + " -DCONFIG_OTA_STAGING_BLOCK_ERASE=1" if x.startswith("-DCMAKE_CXX_FLAGS:STRING=") else x for x in args]
    cli.require(sum("CONFIG_OTA_STAGING_BLOCK_ERASE=1" in x for x in args) == 1, "candidate flag missing")
    s.write(out / "source.json", dict(base=cli.record(BASE / "build/source.json"), overlays=[HAL, COPIED_HEADER],
        files=[cli.record(p) for p in sorted(fw.rglob("*")) if p.is_file()]))
    env = host.environment(s, out)
    host.command(s, out, "configure", args, env, 180)
    raw = host.command(s, out, "build", [args[0], "--build", bld, "--target", "X_Track_App_GCC", "--parallel", "6"], env, 900)
    def normalized(data):
        return review.warnings(data.replace(b"p34-staging-erase", b"p34-ui-cadence-r2"))
    old, new = normalized((BASE / "build/build.log").read_bytes()), normalized(raw)
    value = dict(result="STAGING_ERASE_APP_BUILT", artifacts=[cli.record(bld / "app-gcc" / ("X-Track-App-GCC" + ext))
        for ext in (".bin", ".elf", ".map", ".hex")], warnings=sum(new.values()), new_warnings=dict(new-old),
        errors=raw.count(b"error:"), boot_built=False, hardware=False, source=cli.record(out / "source.json"), tests=ref)
    s.write(out / "result.json", value)
    cli.require(not value["new_warnings"] and not value["errors"], "new build diagnostics need review")
    print(json.dumps(value))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("prepare", "test", "launch", "worker"))
    p.add_argument("--attempt", default="r1")
    a = p.parse_args(); s = cli.Store(ROOT)
    cli.require(re.fullmatch(r"r[1-9][0-9]*", a.attempt), "invalid test output label")
    if a.mode == "prepare": prepare(s)
    elif a.mode == "test": tests(s, a.attempt)
    else:
        owner = cli.load_module("staging_erase_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
        if a.mode == "launch":
            print(owner.owned.launch(s.checked(AREA / "runtime/build-001"), Path(__file__), ["worker"], 1500))
        else:
            cli.require(owner.owned.in_job(), "finite build owner required")
            build(s)
