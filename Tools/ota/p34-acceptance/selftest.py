"""Contained entry for existing affected host regressions, not hardware acceptance."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import sysconfig

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p34_selftest_build", HERE / "build.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
GROUPS = {
    "firmware": ("test_ota_ble_frame.py", "test_ota_ble_session.py", "test_ota_staging.py",
                 "test_ota_package.py", "test_ota_patch.py", "test_ota_backup.py", "test_ota_device_info.py"),
    "governance": ("test_acceptance_bundle.py", "test_acceptance_efficiency.py"),
    "observation": ("test_p3_4_observation_capture.py",),
    "admission": ("test_ota_link_metrics.py", "test_p34_batch_timing.py", "test_p34_acceptance_stats.py"),
    "service": ("test_p34_service_patch.py",),
    "live": ("test_p34_live_route.py",),
}
SESSION_SOURCES = ("Libraries/OTA/ota_ble_session.c", "Libraries/OTA/ota_ble_frame.c",
    "Libraries/OTA/ota_ble_ring.c", "Libraries/OTA/ota_sd.c", "Libraries/OTA/ota_staging.c",
    "Libraries/OTA/ota_pipeline.c", "boot/src/boot_crc32.c", "boot/src/boot_sha256.c")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=tuple(GROUPS) + ("pipeline", "child"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--compiler-dir", type=Path)
    parser.add_argument("--test", choices=tuple(name for names in GROUPS.values() for name in names))
    args = parser.parse_args()
    if Path.cwd() != host.ROOT or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("explicit worktree and isolated Python required")
    if args.group == "child":
        if not args.test:
            raise RuntimeError("explicit regression required")
        for key in ("TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
            host.checked(Path(os.environ[key]))
        sys.path[:0] = [str(host.ROOT / "tests/ota"), sysconfig.get_path("platlib"), sysconfig.get_path("purelib")]
        sys.argv = [str(host.ROOT / "tests/ota" / args.test)]
        runpy.run_path(sys.argv[0], run_name="__main__")
        return
    if args.out is None:
        raise RuntimeError("explicit output directory required")
    out = host.checked(args.out)
    if out.exists():
        raise RuntimeError("preserve earlier regression outputs")
    if args.group == "pipeline":
        tests = ("pipeline", "ble-pipeline", "pipeline-sync")
    else:
        if args.test and args.test not in GROUPS[args.group]:
            raise RuntimeError("regression does not belong to the selected group")
        tests = (args.test,) if args.test else GROUPS[args.group]
    for name in tests + ("result",):
        host.checked(out / (name + ".json"))
        host.checked(out / (name + ".log"))
    env = host.environment(out)
    if args.compiler_dir:
        env["PATH"] = str(args.compiler_dir.resolve(strict=True)) + os.pathsep + env.get("PATH", "")
    if args.group == "pipeline":
        cc = __import__("shutil").which("gcc", path=env.get("PATH"))
        if cc is None:
            raise RuntimeError("existing native GCC required")
        cases = {
            "pipeline": ("test_ota_pipeline.c", ("Libraries/OTA/ota_pipeline.c", "Libraries/OTA/ota_staging.c")),
            "ble-pipeline": ("test_ota_ble_pipeline.c", SESSION_SOURCES),
            "pipeline-sync": ("test_ota_pipeline_sync.c", SESSION_SOURCES + ("Libraries/OTA/ota_pipeline_sync.c",)),
        }
        for name, (test, sources) in cases.items():
            exe = host.checked(out / (name + (".exe" if os.name == "nt" else "")))
            host.checked(out / (name + "-compile.log"))
            host.checked(out / (name + "-compile.json"))
            host.run(out, env, name + "-compile", [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                "-DP34_OTA_PIPELINE=1", *(["-DP34_OTA_PIPELINE_SYNC=1"] if name == "pipeline-sync" else []),
                "-I" + str(host.ROOT / "Libraries"), "-I" + str(host.ROOT / "boot/include"),
                host.ROOT / "tests/ota" / test, *[host.ROOT / path for path in sources], "-o", exe], 90)
            host.run(out, env, name, [exe], 90)
        host.io.write_json(host.ROOT, out / "result.json", dict(passed=True, group=args.group,
            tests=[json.loads((out / (name + ".json")).read_text()) for name in tests],
            device_operations=0, independent_acceptance=False))
        print("PIPELINE_REGRESSIONS_PASS groups=3", flush=True)
        return
    results = []
    for name in tests:
        try:
            host.run(out, env, name, [sys.executable, "-I", "-S", "-B", "-X", "utf8",
                Path(__file__), "child", "--test", name], 600)
        except RuntimeError:
            pass
        receipt = out / (name + ".json")
        if not receipt.exists():
            raise RuntimeError("command ownership/receipt missing; no further tests")
        value = json.loads(receipt.read_text())
        results.append(dict(test=name, exit=value["exit"], timed_out=value["timed_out"], log=value["log"]))
    passed = all(item["exit"] == 0 and not item["timed_out"] for item in results)
    host.io.write_json(host.ROOT, out / "result.json", dict(passed=passed, group=args.group,
        tests=results, device_operations=0, independent_acceptance=False))
    print(json.dumps(dict(group=args.group, passed=passed, tests=len(results))), flush=True)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
