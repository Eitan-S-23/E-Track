"""Finite offline development invocation; no formal command or cloud route."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).absolute().parents[3]
HERE = ROOT / ".cache/p44-v7-development/successor05-02"
guard = runpy.run_path(str(ROOT / "Tools/acceptance/p44/bundle.py"))["guard"]
assert Path.cwd() == ROOT
assert sys.argv[1:] in (["node"], ["python"], ["audit"])
mode = sys.argv[1]
for value in (HERE, HERE / "host", HERE / "node", ROOT / ".cache/p44-v7-development/python"):
    guard(value)
for key in ("NODE_OPTIONS", "NODE_V8_COVERAGE", "NODE_COMPILE_CACHE", "SSLKEYLOGFILE", "GIT_TRACE",
            "GIT_TRACE2", "GIT_TRACE2_EVENT", "GIT_TRACE2_PERF", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
    assert not os.environ.get(key), "UNREVIEWED_OUTPUT_OVERRIDE"
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", GIT_OPTIONAL_LOCKS="0",
           GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1", GIT_CONFIG_COUNT="3",
           GIT_CONFIG_KEY_0="safe.directory", GIT_CONFIG_VALUE_0=str(ROOT),
           GIT_CONFIG_KEY_1="gc.auto", GIT_CONFIG_VALUE_1="0",
           GIT_CONFIG_KEY_2="maintenance.auto", GIT_CONFIG_VALUE_2="false")
for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME", "XDG_DATA_HOME", "GH_CONFIG_DIR", "npm_config_cache"):
    directory = guard(HERE / "host" / key.lower())
    directory.mkdir(parents=True, exist_ok=True)
    env[key] = str(directory)


def inventory():
    result = {}
    for version in range(1, 8):
        stem = ROOT / ("docs/acceptance-contracts/P4-4-v" + str(version))
        for file in [stem.with_name(stem.name + ".contract.json"), *stem.rglob("*")]:
            guard(file)
            if file.is_file():
                result[file.relative_to(ROOT).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
            elif file.is_dir():
                result[file.relative_to(ROOT).as_posix()] = "directory"
    return result


def write(name, value):
    file = guard(HERE / name)
    with file.open("x", encoding="utf8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


if mode == "audit":
    original = json.loads((HERE / "originals.json").read_text(encoding="utf8"))
    assert inventory() == original, "CHANGED_FROZEN_ORIGINALS"
    output_trees = [Path(__file__).absolute().parent, HERE, ROOT / ".cache/p44-v7-development/python/batch-5"]
    checked_outputs = {}
    for tree in output_trees:
        for file in [tree, *tree.rglob("*")]:
            guard(file)
            checked_outputs[file.relative_to(ROOT).as_posix()] = "file" if file.is_file() else "directory"
    hashes = {name: hashlib.sha256(guard(ROOT / name).read_bytes()).hexdigest() for name in (
        "Tools/ota/p44-after-recovery.cjs", "Tools/ota/p44-after-bundle.py",
        "tests/ota/test_p44_after_recovery.cjs", "tests/ota/test_p44_after_bundle.py",
        "docs/ota-exec-notes/P4-4-s3-preacceptance-2026-10-19.md")}
    support_hashes = {file.relative_to(ROOT).as_posix(): hashlib.sha256(guard(file).read_bytes()).hexdigest()
                      for file in (Path(__file__).absolute(), Path(__file__).absolute().with_name("stdio.cjs"))}
    write("audit.json", {"unchanged_original_paths": len(original), "final_hashes": hashes,
                         "boundary": str(ROOT), "outside_outputs": [], "development_only": True,
                         "checked_output_paths": checked_outputs, "support_hashes": support_hashes})
    print(json.dumps({"unchanged_original_paths": len(original), "checked_output_paths": len(checked_outputs), "hashes": hashes}))
    sys.exit(0)

if mode == "node":
    write("originals.json", inventory())
    command = ["node", "--require", str(Path(__file__).absolute().parent / "stdio.cjs"), "tests/ota/test_p44_after_recovery.cjs",
               "--output-dir", str(HERE / "node"), "real-io"]
    timeout = 5400
else:
    command = ["python", "-I", "-S", "-B", "tests/ota/test_p44_after_bundle.py", "--node-fixture",
               str(HERE / "node"), "AfterBundleTests.test_real_io_failure_reload_assembly_is_consumed_without_copying",
               "AfterBundleTests.test_real_io_consumer_rejects_wrong_tool_bytes"]
    timeout = 300
log = guard(HERE / (mode + ".log"))
started = time.time()
with log.open("xb") as output:
    try:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                 stdout=output, stderr=subprocess.STDOUT)
        print(json.dumps({"mode": mode, "pid": child.pid}), flush=True)
        child.wait(timeout=timeout)
        receipt = {"command": command, "cwd": str(ROOT), "timeout_seconds": timeout,
                   "exit_code": child.returncode, "pid": child.pid, "process_closed": True}
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill.exe", "/PID", str(child.pid), "/T", "/F"], cwd=ROOT, env=env,
                       stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, timeout=30)
        child.wait(timeout=30)
        receipt = {"command": command, "cwd": str(ROOT), "timeout_seconds": timeout,
                   "exit_code": None, "process_closed": True, "timed_out": True}
receipt.update(started_epoch=started, ended_epoch=time.time(), elapsed_seconds=time.time() - started,
               log=str(log.relative_to(ROOT)), log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
write(mode + "-receipt.json", receipt)
print(json.dumps(receipt))
sys.exit(0 if receipt["exit_code"] == 0 else 1)
