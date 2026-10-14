"""Run the existing 18-case restore transaction regression with real bcb_commit."""
import argparse
import importlib.util
import os
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p34_restore_build", HERE.parent / "build.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    if Path.cwd() != host.ROOT or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("explicit worktree and isolated Python required")
    out = host.checked(args.out)
    if out.exists():
        raise RuntimeError("preserve earlier regression evidence")
    exe = host.checked(out / ("restore-test.exe" if os.name == "nt" else "restore-test"))
    for label in ("compile", "test", "result"):
        host.checked(out / (label + ".json"))
        host.checked(out / (label + ".log"))
    env = host.environment(out)
    cc = shutil.which(args.cc, path=env.get("PATH"))
    if cc is None:
        raise RuntimeError("native C compiler unavailable")
    sources = [HERE / "test_restore.c", HERE / "restore_core.c",
               host.ROOT / "Libraries/EEPROM/eeprom_bcb.c"]
    host.run(out, env, "compile", [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        "-I" + str(host.ROOT / "Libraries"), *sources, "-o", exe], 90)
    log = host.run(out, env, "test", [exe], 30)
    match = re.search(rb"RESTORE_CORE_TESTS=(\d+) PASS;", log)
    if match is None or int(match[1]) != 18:
        raise RuntimeError("complete transaction regression missing")
    host.io.write_json(host.ROOT, out / "result.json", dict(result="RESTORE_TRANSACTION_REGRESSION_PASS",
        checks=18, sources=[host.record(path) for path in sources], executable=host.record(exe),
        device_operations=0, independent_acceptance=False))
    print("RESTORE_CORE_TESTS=18 PASS", flush=True)


if __name__ == "__main__":
    main()
