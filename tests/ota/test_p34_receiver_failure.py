"""Run the original-package receiver fault matrix; no hardware or OTA actions."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host
import p34_session as cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--package-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compiler", choices=("gcc", "msvc"), default="gcc")
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit root and isolated Python required")
    store = cli.Store(ROOT)
    out = store.checked(args.out)
    cli.require(not out.exists(), "preserve previous receiver evidence")
    source_root = args.source_root.resolve(strict=True)
    package = args.package.resolve(strict=True)
    package_bytes = package.read_bytes()
    cli.require(hashlib.sha256(package_bytes).hexdigest() == args.package_sha256.lower(),
                "original package hash mismatch")
    cli.require(len(package_bytes) >= 13 * 4096, "original 13-block prefix required")
    cc = shutil.which("gcc") or shutil.which("cc")
    vcvars = Path("D:/vs2019/VC/Auxiliary/Build/vcvars64.bat")
    cli.require((cc is not None) if args.compiler == "gcc" else
                (os.name == "nt" and vcvars.is_file()), "selected host compiler is unavailable")
    sources = [ROOT / "tests/ota/test_p34_receiver_failure.c"]
    sources += [source_root / "Libraries/OTA" / (name + ".c") for name in (
        "ota_pipeline", "ota_pipeline_sync", "ota_ble_session", "ota_ble_frame",
        "ota_ble_ring", "ota_sd", "ota_staging")]
    sources += [source_root / "boot/src" / (name + ".c") for name in ("boot_crc32", "boot_sha256")]
    inputs = sources + [Path(__file__), Path(host.__file__), Path(cli.__file__), package,
                        source_root / "tests/ota/test_ota_pipeline_sync.c",
                        source_root / "tests/ota/test_ota_ble_session.c"]
    inputs += sorted((source_root / "Libraries/OTA").glob("*.h"))
    inputs += sorted((source_root / "boot/include").glob("*.h"))
    before = [cli.record(path) for path in inputs]
    exe = store.checked(out / ("receiver.exe" if os.name == "nt" else "receiver"))
    if args.compiler == "msvc":
        for source in sources:
            store.checked(out / (source.stem + ".obj"))
        store.checked(out / "receiver.pdb")
    for name in ("compiler", "compile", "run", "mutant"):
        store.checked(out / (name + ".log"))
        store.checked(out / (name + ".json"))
    store.checked(out / "result.json")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out / "host" / key.lower())
    env = host.environment(store, out)
    definitions = ["P34_OTA_PIPELINE=1", "P34_OTA_PIPELINE_SYNC=1", "P34_OTA_PIPELINE_WAIT_RX=1"]
    if source_root == ROOT:
        definitions.append("P34_TEST_STOPPED_ACK=1")
    includes = [source_root / relative for relative in ("tests/ota", "Libraries", "boot/include")]
    if args.compiler == "gcc":
        host.command(store, out, "compiler", [cc, "--version"], env, 30)
        command = [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
                   *["-D" + value for value in definitions],
                   *["-I" + str(path) for path in includes], *sources, "-o", exe]
    else:
        prefix = "call " + str(vcvars) + " >nul && "
        host.command(store, out, "compiler", ["cmd.exe", "/d", "/s", "/c", prefix + "where cl"], env, 30)
        cl_args = ["cl", "/nologo", "/Bv", "/utf-8", "/std:c11", "/O2", "/W4", "/WX",
                   "/D_CRT_SECURE_NO_WARNINGS", *["/D" + value for value in definitions],
                   *["/I" + str(path) for path in includes], *map(str, sources),
                   "/Fe:" + str(exe), "/Fo:" + out.as_posix() + "/",
                   "/Fd:" + str(out / "receiver.pdb")]
        command = ["cmd.exe", "/d", "/s", "/c", prefix + subprocess.list2cmdline(cl_args)]
    host.command(store, out, "compile", command, env, 180)
    raw = host.command(store, out, "run", [exe, package], env, 60)
    summary = re.search(rb"RECEIVER_FAILURE checks=(\d+) failures=0 cases=10 mutation=0", raw)
    cli.require(summary is not None, "complete ten-case result required")
    mutant_command = [str(exe), str(package), "--mutate-source"]
    mutant = subprocess.run(mutant_command, cwd=ROOT, env=env, capture_output=True, timeout=60,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    mutant_raw = mutant.stdout + mutant.stderr
    mutant_log = store.raw(out / "mutant.log", mutant_raw)
    store.write(out / "mutant.json", dict(command=mutant_command, cwd=str(ROOT),
                                         exit=mutant.returncode, log=mutant_log))
    cli.require(mutant.returncode == 1 and
                re.search(rb"borrowed source unchanged across receive callback\s+FAIL", mutant_raw),
                "negative control must fail the ownership oracle, not crash")
    cli.require(before == [cli.record(path) for path in inputs], "receiver test inputs changed")
    result = dict(result="RECEIVER_MODEL_CONTAINMENT_PASS", cases=10,
                  checks=int(summary[1]), compiler=args.compiler,
                  source_mutation_detected=True, inputs=before,
                  hardware=False, trial5_root_cause_proved=False,
                  limitation="modeled page IO/restore/read failures, not physical NOR validation")
    store.write(out / "result.json", result)
    print("RECEIVER_MODEL_CONTAINMENT_PASS cases=10 checks=" + str(result["checks"]) +
          " mutation_detected=true trial5_root_cause_proved=false")


if __name__ == "__main__":
    main()
