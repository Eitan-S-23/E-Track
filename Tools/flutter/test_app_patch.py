"""CI-only Java decoder verification, reusing the contained development runner."""
import argparse
import hashlib
import os
from pathlib import Path
import runpy
import shutil
import sys
import urllib.request
import uuid

JAR_URL = "https://repo.maven.apache.org/maven2/org/tukaani/xz/1.10/xz-1.10.jar"
JAR_SHA256 = "95c63c1a55b22dd6453890a419cc1a640f790bbf7d8ae82db1e30aefefb08888"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    root = Path(os.path.abspath(args.repo_root))
    if Path.cwd() != root or not sys.dont_write_bytecode or os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Requires GitHub Actions, explicit root cwd and -B")
    h = runpy.run_path(str(root / "Tools/flutter/dev_checks.py"))
    checked = lambda value: h["checked_path"](root, value)
    out = checked(root / ".cache/app-patch-tests" / uuid.uuid4().hex)
    classes, logs, fixtures, jar = [checked(out / name) for name in ("classes", "logs", "fixtures", "xz-1.10.jar")]
    for file in [out / "result.json", logs / "compile.log", logs / "decode.log"]:
        checked(file)
    classes.mkdir(parents=True)
    logs.mkdir()
    env = h["contained_environment"](root, out)
    for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH"):
        env.pop(key, None)
    with urllib.request.urlopen(JAR_URL, timeout=60) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024 or hashlib.sha256(data).hexdigest() != JAR_SHA256:
        raise ValueError("XZ for Java download identity mismatch")
    with jar.open("xb") as target:
        target.write(data)
    expected = runpy.run_path(str(root / "tests/ota/test_app_bsdiff_lzma.py"))["write_fixtures"](fixtures)
    sources = [root / "app/bluetooth_flutter_Trace/android/app/src" / p for p in (
        "main/java/com/wen/gaia/gaia/BsdiffLzmaPatch.java", "test/java/com/wen/gaia/gaia/BsdiffLzmaPatchTest.java")]
    home = os.environ.get("JAVA_HOME_17_X64") or os.environ.get("JAVA_HOME")
    def tool(name):
        candidate = Path(home) / "bin" / (name + (".exe" if os.name == "nt" else "")) if home else None
        found = str(candidate) if candidate and candidate.is_file() else shutil.which(name)
        if not found:
            raise RuntimeError("JDK required")
        return found
    options = ["-Djava.io.tmpdir=" + env["TEMP"], "-Duser.home=" + env["HOME"],
        "-XX:-UsePerfData", "-XX:ErrorFile=" + str(checked(out / "hs_err_pid%p.log"))]
    commands = [("compile", [tool("javac"), *("-J" + item for item in options), "--release", "8", "-Xlint:all", "-Werror",
        "-cp", str(jar), "-d", str(classes), *map(str, sources)]),
        ("decode", [tool("java"), *options, "-Xmx64m", "-cp", os.pathsep.join(map(str, (classes, jar))),
        "com.wen.gaia.gaia.BsdiffLzmaPatchTest", str(fixtures)])]
    results = []
    for name, argv in commands:
        result = h["run_command"](root, argv, root, env, logs / (name + ".log"), 120)
        results.append(dict(name=name, **result))
        print((logs / (name + ".log")).read_text(encoding="utf-8", errors="replace"), flush=True)
        if result["status"] != "PASS":
            break
    passed = len(results) == 2 and all(item["status"] == "PASS" for item in results)
    passed = passed and f"APP_PATCH_TESTS_PASS {expected}" in (logs / "decode.log").read_text(encoding="utf-8")
    h["save_report"](root, out / "result.json", dict(passed=passed, expected=expected, results=results,
        jarSha256=JAR_SHA256, inputs={str(p.relative_to(root)): h["file_hash"](p) for p in sources}, phone=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
