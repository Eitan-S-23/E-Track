"""Contained pure-Java PHY lifecycle tests, not a local Android/Flutter build."""
import argparse
import os
from pathlib import Path
import runpy
import shutil
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    root = Path(os.path.abspath(args.repo_root))
    if Path.cwd() != root or not sys.dont_write_bytecode:
        raise ValueError("explicit root cwd and no-bytecode required")
    h = runpy.run_path(str(root / "Tools/flutter/dev_checks.py"))
    checked = lambda path: h["checked_path"](root, path)
    out = checked(root / ".cache/p34-phy-native/runs" / uuid.uuid4().hex)
    classes, logs = checked(out / "classes"), checked(out / "logs")
    sources = root / "app/bluetooth_flutter_Trace/vendor/flutter_blue_plus_android/android/src"
    inputs = [sources / "main/java/com/lib/flutter_blue_plus/PhyProbe.java",
              sources / "test/java/com/lib/flutter_blue_plus/PhyProbeTest.java"]
    for path in inputs + [out / "result.json", logs / "compile.log", logs / "run.log"]:
        checked(path)
    classes.mkdir(parents=True)
    logs.mkdir()
    env = h["contained_environment"](root, out)
    for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH"):
        env.pop(key, None)
    java_home = os.environ.get("JAVA_HOME_17_X64") or os.environ.get("JAVA_HOME")
    def tool(name):
        candidate = Path(java_home) / "bin" / (name + (".exe" if os.name == "nt" else "")) if java_home else None
        value = str(candidate) if candidate and candidate.is_file() else shutil.which(name)
        if not value:
            raise RuntimeError("JDK required for " + name)
        return value
    java_options = ["-Djava.io.tmpdir=" + env["TEMP"], "-Duser.home=" + env["HOME"],
                    "-XX:-UsePerfData", "-XX:ErrorFile=" + str(checked(out / "hs_err_pid%p.log"))]
    commands = [
        ("compile", [tool("javac"), *("-J" + item for item in java_options),
            "--release", "8", "-Xlint:all", "-Werror", "-d", str(classes), *map(str, inputs)]),
        ("run", [tool("java"), *java_options, "-cp", str(classes), "com.lib.flutter_blue_plus.PhyProbeTest"]),
    ]
    results = []
    for name, argv in commands:
        log = checked(logs / (name + ".log"))
        result = h["run_command"](root, argv, root, env, log, 60)
        results.append(dict(name=name, **result))
        print(log.read_text(encoding="utf-8", errors="replace"), flush=True)
        if result["status"] != "PASS":
            break
    passed = len(results) == 2 and all(item["status"] == "PASS" for item in results)
    h["save_report"](root, out / "result.json", dict(passed=passed, results=results,
        inputs={str(p.relative_to(root)): h["file_hash"](p) for p in inputs},
        hardware=False, android_plugin_compiled=False))
    print("PHY_NATIVE_RESULT", passed, str(out), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
