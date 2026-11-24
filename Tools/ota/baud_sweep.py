"""Contained development preparation for the 115200/460800/921600 OTA screen.

This entry does not operate a phone or MCU. Device execution is admitted only
after the matched assets, recovery route and observation workers are prepared.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/p34b"
SRC = OUT / "src"
BASE = "4e5ae68ccbaff9134a268e8aa3d284450ead5a84"
P34_BASE = "73a3563af99ac5a9e0931126be1bc508490cb049"
P34 = "fbc3b5aae468e9ab382ac018c1247de43d890491"
BRANCH = "dev/flutter/p3-4-baud-sweep"
REPO = "Eitan-S-23/E-Track"
P3 = ROOT / ".cache/worktrees/p3-4-link-stats"
OLD_GIT = P3 / ".cache/p3-4-batch-20260922/git"
ALTERNATES = (ROOT / ".git/objects", OLD_GIT / "objects",
              P3 / ".cache/governance-skill-feedback-20260922/git/objects")
SPARSE = (
    "/.gitattributes", "/.gitignore", "/AGENTS.md", "/PLAN-OTA-EXEC.md",
    "/.github/", "/.agents/", "/app/bluetooth_flutter_Trace/",
    "/Tools/flutter/", "/Tools/provenance/manifest_profiles.json",
    "/Tools/ota/p3-4-link-stats/", "/tests/ota/", "/docs/",
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


io = load("baud_sweep_io", ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
host = load("baud_sweep_host", ROOT / ".cache/project-governance-20260922/run.py")
host.OUT = OUT


def checked(path):
    return io.checked_output(ROOT, path)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def record(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(name, value):
    return io.write_json(ROOT, checked(OUT / name), value)


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def numbered(name):
    number = len(list(OUT.glob(name + "-*.json"))) + 1
    return name + "-%03d.json" % number


def environment(credential=None):
    for path in (OUT / "host", SRC / ".git"):
        checked(path)
    value = host.environment(credential)
    value["GIT_CONFIG_VALUE_1"] = "false"
    require(all(path.is_dir() for path in ALTERNATES), "read-only source object store missing")
    value["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = os.pathsep.join(map(str, ALTERNATES))
    return value


def command(args, *, input_bytes=None, credential=None, check=True, timeout=120, cwd=ROOT, extra_env=None):
    for path in (OUT / "host", OUT / "commands.jsonl", SRC, SRC / ".git"):
        checked(path)
    cwd = checked(cwd)
    env = environment(credential)
    env.update(extra_env or {})
    result = subprocess.run(args, cwd=cwd, env=env, input=input_bytes,
                            capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    entry = dict(time=now(), args=args, cwd=str(cwd), exit=result.returncode,
                 stdout=result.stdout.decode("utf-8", "replace"),
                 stderr=result.stderr.decode("utf-8", "replace"))
    with checked(OUT / "commands.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry) + "\n")
    require(not check or result.returncode == 0, "command failed; preserve commands.jsonl: " + args[0])
    return result


def git(*args, **kwargs):
    return command(["git", "-c", "credential.helper=", "-C", str(SRC), *args],
                   **kwargs).stdout.decode("utf-8").strip()


def api(path, credential, *, data=None, missing=False):
    require(path == "/user" or path.startswith("/repos/" + REPO + "/"), "unscoped API resource")
    if data is not None:
        require(path == "/repos/" + REPO + "/actions/workflows/flutter-dev-checks.yml/dispatches" and
                data["ref"] == BRANCH, "only the bounded development dispatch is writable")
    request = urllib.request.Request("https://api.github.com" + path,
        data=None if data is None else json.dumps(data).encode(), headers={
            "Authorization": "Bearer " + credential, "Accept": "application/vnd.github+json",
            "Content-Type": "application/json", "User-Agent": "E-Track-P34-Baud-Screen"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        if error.code == 404 and missing:
            return 404, None
        raise RuntimeError("scoped API HTTP " + str(error.code)) from None


def credential():
    value = host.token()
    require(api("/user", value)[1]["login"] == "Eitan-S-23", "wrong GitHub identity")
    return value


def original_state():
    args = ["git", "--no-optional-locks", "-C", str(ROOT)]
    head = command(args + ["rev-parse", "HEAD"]).stdout.decode().strip()
    paths = command(args + ["diff", "--name-only", "-z"]).stdout.decode().split("\0")
    return dict(head=head, index=record(ROOT / ".git/index"),
                dirty={path: record(ROOT / path) for path in paths if path})


def unchanged_original():
    require(original_state() == read("prepared.json")["original"],
            "original worktree changed; reconcile without reverting it")


def scope_allowed(path):
    return path.startswith("app/bluetooth_flutter_Trace/") or path in {
        ".github/workflows/flutter-dev-checks.yml", "Tools/flutter/dev_apk.py",
        "Tools/flutter/dev_checks.py", "tests/ota/test_flutter_dev_checks.py",
        "tests/ota/test_flutter_dev_apk.py", "tests/ota/test_p3_4_observation_capture.py",
        "Tools/ota/p3-4-link-stats/observation_capture.py",
        "docs/ota-exec-notes/P3-4-batch-optimization-2026-09-22.md",
        "docs/ota-exec-notes/P3-4-baud-screen-2026-09-22.md",
    }


def prepare():
    require(not SRC.exists() and not (OUT / "prepared.json").exists(), "preserve existing preparation")
    for path in (SRC, SRC / ".git", OUT / "p34-bootstrap.patch", OUT / "prepared.json"):
        checked(path)
    token = credential()
    require(api("/repos/" + REPO + "/git/ref/heads/main", token)[1]["object"]["sha"] == BASE,
            "published governance base changed; review before preparing")
    require(api("/repos/" + REPO + "/git/ref/heads/" + BRANCH, token, missing=True)[0] == 404,
            "validation branch already exists")
    original = original_state()
    remote = command(["git", "--no-optional-locks", "-C", str(ROOT), "remote", "get-url", "origin"]).stdout.decode().strip()
    require(remote in ("https://github.com/" + REPO + ".git", "git@github.com:" + REPO + ".git"),
            "repository remote mismatch")
    old = ["git", "--no-optional-locks", "--git-dir=" + str(OLD_GIT)]
    changes = command(old + ["diff", "--name-only", P34_BASE, P34]).stdout.decode().splitlines()
    require(changes and all(scope_allowed(path) for path in changes), "unreviewed P3-4 bootstrap scope")
    for revision in (BASE, P34):
        listing = command(old + ["ls-tree", "-r", "-z", revision]).stdout
        for entry in listing.split(b"\0"):
            if not entry:
                continue
            meta, raw_path = entry.split(b"\t", 1)
            path = raw_path.decode("utf-8")
            if any(path == item.strip("/") or path.startswith(item.strip("/") + "/") for item in SPARSE):
                require(meta.split()[0] in (b"100644", b"100755"), "linked/submodule source rejected")
                checked(SRC / path)
    patch = checked(OUT / "p34-bootstrap.patch")
    command(old + ["diff", "--binary", "--output=" + str(patch), P34_BASE, P34, "--", *changes])
    command(["git", "-c", "credential.helper=", "init", "--template=" + str(checked(OUT / "host/empty-template")), str(SRC)])
    git("sparse-checkout", "set", "--no-cone", "--stdin", input_bytes=("\n".join(SPARSE) + "\n").encode())
    git("checkout", "-b", BRANCH, BASE)
    git("apply", "--index", "--3way", str(patch))
    git("diff", "--cached", "--check")
    save("prepared.json", dict(time=now(), root=str(ROOT), source=str(SRC), branch=BRANCH,
        base=BASE, bootstrap=P34, bootstrap_patch=record(patch), bootstrap_paths=changes,
        original=original, rates=[115200, 460800, 921600], hardware_contacted=False))
    print("DEVELOPMENT_SOURCE_READY", SRC, BRANCH, flush=True)


def stage():
    unchanged_original()
    require(git("branch", "--show-current") == BRANCH, "wrong validation branch")
    paths = set(git("diff", "HEAD", "--name-only").splitlines())
    paths.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    require(paths and all(scope_allowed(path) for path in paths), "unreviewed development scope")
    for path in paths:
        checked(SRC / path)
    git("add", "--", *sorted(paths))
    git("diff", "--cached", "--check")
    value = dict(time=now(), paths=sorted(paths), tree=git("write-tree"),
                 files={path: record(SRC / path) for path in paths},
                 stat=git("diff", "--cached", "--stat"))
    save(numbered("stage"), value)
    print(value["stat"], flush=True)


def latest(name):
    paths = sorted(OUT.glob(name + "-*.json"))
    require(paths, "missing " + name + " receipt")
    return json.loads(paths[-1].read_text(encoding="utf-8"))


def host_tests():
    out = checked(OUT / ("host-tests-%03d" % (len(list(OUT.glob("host-tests-*"))) + 1)))
    require(not out.exists(), "preserve existing test outputs")
    names = ("test_flutter_dev_checks.py", "test_flutter_dev_apk.py", "test_p3_4_observation_capture.py")
    for leaf in ("flutter-dev-checks-tests", "flutter-dev-apk-tests", "p3-4-observation-capture-tests"):
        checked(SRC / ".cache" / leaf)
    for name in (*names, "result.json"):
        checked(out / (name + ".log" if name.endswith(".py") else name))
    out.mkdir(parents=True)
    results = []
    for name in names:
        script = SRC / "tests/ota" / name
        code = "import sys,runpy;sys.path.insert(0," + repr(str(script.parent)) + ");runpy.run_path(" + repr(str(script)) + ",run_name='__main__')"
        result = command([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", code],
                         cwd=SRC, timeout=300, check=False)
        raw = result.stdout + result.stderr
        log = checked(out / (name + ".log"))
        with log.open("xb") as stream:
            stream.write(raw)
        counts = re.findall(r"Ran (\d+) tests?", raw.decode("utf-8", "replace"))
        results.append(dict(name=name, exit=result.returncode, count=int(counts[-1]) if counts else None,
                            source=record(script), log=record(log)))
        print(name, result.returncode, raw.decode("utf-8", "replace")[-1600:], flush=True)
    io.write_json(ROOT, out / "result.json", dict(time=now(), passed=all(item["exit"] == 0 for item in results),
                  results=results, hardware_contacted=False, flutter_executed=False))
    require(all(item["exit"] == 0 for item in results), "host regression failed; preserve original receipts")


def firmware_source():
    revision = "9e41a5379203cc2cd7ab6e8c0469fcd098db3d0b"
    destination = checked(OUT / "fw")
    archive = checked(OUT / "firmware-source.tar")
    receipt = checked(OUT / "firmware-source.json")
    require(not destination.exists() and not archive.exists() and not receipt.exists(),
            "preserve existing firmware source preparation")
    selected = ["ArduinoAPI", "Libraries", "MDK-ARM_F435", "Simulator/LVGL.Simulator",
                "USER", "boot", "bsdiff_lzma_AES128-main", "cmake", "segger_rtt",
                "vendor", "Tools", "tests/ota", ".gitattributes", ".gitignore"]
    command(["git", "--no-optional-locks", "-C", str(P3), "archive", "--format=tar",
             "--output=" + str(archive), revision, "--", *selected], timeout=180)
    from pathlib import PurePosixPath
    with tarfile.open(archive, "r:") as source:
        members = source.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and ".." not in path.parts and
                    "\\" not in member.name and ":" not in member.name and
                    (member.isfile() or member.isdir()), "unsafe firmware source archive entry")
            checked(destination / Path(*path.parts))
        for member in members:
            path = checked(destination / member.name)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as reader, path.open("xb") as writer:
                    while data := reader.read(1024 * 1024):
                        writer.write(data)
    save("firmware-source.json", dict(time=now(), revision=revision, archive=record(archive),
        source=str(destination), selected=selected, files=sum(member.isfile() for member in members),
        instruction_root=str(ROOT), published_governance=BASE, hardware_contacted=False))
    print("FIRMWARE_SOURCE_READY", destination, flush=True)


def firmware_tests():
    fw = checked(OUT / "fw")
    out = checked(OUT / ("firmware-tests-%03d" % (len(list(OUT.glob("firmware-tests-*"))) + 1)))
    require(not out.exists(), "fresh firmware test outputs required")
    cases = ("p34_link_profile_host", "bt_bx_host_test")
    for name in cases:
        for suffix in (".exe", ".build.log", ".run.log"):
            checked(out / (name + suffix))
    checked(out / "result.json")
    out.mkdir(parents=True)
    results = []
    for name in cases:
        source = fw / "tests/ota" / (name + ".c")
        exe = checked(out / (name + ".exe"))
        result = command([r"D:\install\mingw64\bin\gcc.exe", "-std=c99", "-Wall", "-Wextra", "-Werror",
            "-O2", "-I" + str(fw), "-I" + str(fw / "USER"), str(source), "-o", str(exe)],
            cwd=fw, timeout=90, check=False)
        raw = result.stdout + result.stderr
        with checked(out / (name + ".build.log")).open("xb") as stream:
            stream.write(raw)
        require(result.returncode == 0, "firmware host compile failed: " + name)
        run = command([str(exe)], cwd=fw, timeout=30, check=False)
        with checked(out / (name + ".run.log")).open("xb") as stream:
            stream.write(run.stdout + run.stderr)
        success = run.returncode == 0 and (b'"passed":true' in run.stdout if name == cases[0]
                                            else b"RESULT: PASS" in run.stdout)
        results.append(dict(name=name, exit=run.returncode, passed=success,
            compiler_diagnostics=raw.decode("utf-8", "replace"), source=record(source), binary=record(exe),
            log=record(out / (name + ".run.log"))))
        print(name, run.returncode, run.stdout.decode("utf-8", "replace")[-1800:], flush=True)
    io.write_json(ROOT, out / "result.json", dict(time=now(), passed=all(item["passed"] for item in results),
        results=results, hardware_contacted=False, inputs=[record(fw / "USER/HAL/BtBaudExperiment" / name)
        for name in ("p34_link_profile.h", "bt_baud_experiment.h")]))
    require(all(item["passed"] for item in results), "firmware host tests failed")


def firmware_build():
    fw = checked(OUT / "fw")
    build = checked(OUT / "build")
    tag = "firmware-build-%03d" % (len(list(OUT.glob("firmware-build-*.json"))) + 1)
    for path in (build, OUT / (tag + ".json"), OUT / (tag + ".configure.log"), OUT / (tag + ".build.log")):
        checked(path)
    for directory, children, files in os.walk(build, followlinks=False):
        for name in children + files:
            checked(Path(directory) / name)
    toolchain = Path(r"D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming")
    cmake = r"C:\Program Files\CMake\bin\cmake.exe"
    args = [cmake, "-S", str(fw / "MDK-ARM_F435/cmake-generated"), "-B", str(build), "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024", "-DP3_4_LINK_PROFILE=ON",
            "-DKEIL_GCC_COMPILER_CACHE:FILEPATH=", "-DARM_TOOLCHAIN_ROOT=" + str(toolchain),
            "-DCMAKE_MAKE_PROGRAM=D:/singlechip/gcc+gdb+openocd/tools/ninja-win/ninja.exe"]
    for language, compiler in (("C", "gcc"), ("CXX", "g++"), ("ASM", "gcc")):
        args.append("-DCMAKE_" + language + "_COMPILER=" + str(toolchain / "bin" / ("arm-none-eabi-" + compiler + ".exe")))
    env = dict(SOURCE_DATE_EPOCH="1786320000", CCACHE_DISABLE="1", SCCACHE_DISABLE="1")
    configured = command(args, cwd=fw, extra_env=env, timeout=180, check=False)
    raw_configure = configured.stdout + configured.stderr
    with checked(OUT / (tag + ".configure.log")).open("xb") as stream:
        stream.write(raw_configure)
    require(configured.returncode == 0, "firmware configure failed; original log retained")
    result = command([cmake, "--build", str(build), "--target", "X_Track_App_GCC", "--parallel", "8"],
                     cwd=fw, extra_env=env, timeout=1200, check=False)
    raw = result.stdout + result.stderr
    with checked(OUT / (tag + ".build.log")).open("xb") as stream:
        stream.write(raw)
    text = raw.decode("utf-8", "replace")
    artifacts = [record(path) for path in sorted((build / "app-gcc").glob("X-Track-App-GCC.*")) if path.is_file()]
    save(tag + ".json", dict(time=now(), passed=result.returncode == 0, exit=result.returncode,
        configure=record(OUT / (tag + ".configure.log")), log=record(OUT / (tag + ".build.log")),
        warnings=len(re.findall(r"\bwarning:", text)), errors=len(re.findall(r"\berror:", text)),
        scope="GCC diagnostic App only; original whole Boot retained, no simulator or AC5", artifacts=artifacts,
        modified_sources=[record(fw / path) for path in ("USER/HAL/HAL_Bluetooth.cpp",
            "USER/HAL/BtBaudExperiment/p34_link_profile.h", "MDK-ARM_F435/Platform/Core/HardwareSerial.cpp",
            "MDK-ARM_F435/Platform/Core/HardwareSerial.h", "MDK-ARM_F435/cmake-generated/CMakeLists.txt")],
        hardware_contacted=False))
    print(text[-6500:], flush=True)
    require(result.returncode == 0, "firmware build failed; original diagnostics retained")


def commit():
    unchanged_original()
    value = latest("stage")
    require(git("branch", "--show-current") == BRANCH and git("write-tree") == value["tree"], "stage drift")
    require(all(record(SRC / path) == item for path, item in value["files"].items()), "source drift")
    git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
        "WIP(p3-4): single-App immutable baud experiment configuration")
    sha = git("rev-parse", "HEAD")
    save(numbered("commit"), dict(time=now(), sha=sha, branch=BRANCH, stage=value))
    unchanged_original()
    print("DEVELOPMENT_COMMIT", sha, flush=True)


def push():
    unchanged_original()
    sha = latest("commit")["sha"]
    require(git("rev-parse", "HEAD") == sha and git("branch", "--show-current") == BRANCH, "commit drift")
    token = credential()
    before = api("/repos/" + REPO + "/git/ref/heads/" + BRANCH, token, missing=True)[1]
    if before is None or before["object"]["sha"] != sha:
        git("push", "https://github.com/" + REPO + ".git", "HEAD:refs/heads/" + BRANCH,
            credential=token, timeout=180)
    actual = api("/repos/" + REPO + "/git/ref/heads/" + BRANCH, token)[1]["object"]["sha"]
    require(actual == sha, "push result unresolved; do not repeat blindly")
    save(numbered("push"), dict(time=now(), sha=sha, branch=BRANCH))
    print("DEVELOPMENT_PUSH_VERIFIED", sha, flush=True)


def status():
    token = credential()
    sha = latest("commit")["sha"]
    runs = api("/repos/" + REPO + "/actions/runs?head_sha=" + sha + "&per_page=30", token)[1]["workflow_runs"]
    values = []
    for run in runs:
        require(run["head_branch"] == BRANCH, "unexpected run branch")
        if run["path"] != ".github/workflows/flutter-dev-checks.yml":
            continue
        value = {key: run.get(key) for key in ("id", "head_sha", "event", "status", "conclusion", "html_url", "run_attempt")}
        value["jobs"] = api("/repos/" + REPO + "/actions/runs/%d/jobs" % run["id"], token)[1]["jobs"]
        values.append(value)
        print(json.dumps({key: value[key] for key in value if key != "jobs"}), flush=True)
        for job in value["jobs"]:
            print(job["name"], job["status"], job["conclusion"], flush=True)
    save(numbered("status"), dict(time=now(), sha=sha, runs=values))


def dispatch():
    unchanged_original()
    sha = latest("commit")["sha"]
    require(not (OUT / "apk-dispatch-intent.json").exists(), "existing APK dispatch must be reconciled")
    token = credential()
    require(api("/repos/" + REPO + "/git/ref/heads/" + BRANCH, token)[1]["object"]["sha"] == sha, "remote drift")
    inputs = dict(test_scope="all", build_apk="true", app_id_suffix=".p34baud",
        device_observation="true", observation_target="02:00:00:00:00:01",
        observation_firmware_latest_url="https://p34-runtime-required.invalid/api/public/firmware/latest",
        ota_link_candidate="runtime")
    save("apk-dispatch-intent.json", dict(time=now(), sha=sha, branch=BRANCH, inputs=inputs))
    code, _ = api("/repos/" + REPO + "/actions/workflows/flutter-dev-checks.yml/dispatches", token,
                  data=dict(ref=BRANCH, inputs=inputs))
    require(code == 204, "dispatch outcome uncertain")
    save("apk-dispatch-accepted.json", dict(time=now(), sha=sha, status=code, inputs=inputs))
    print("DEBUG_APK_DISPATCH_ACCEPTED", sha, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status", "dispatch", "host-tests", "firmware-source", "firmware-tests", "firmware-build"))
    args = parser.parse_args()
    require(Path.cwd().resolve() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "explicit project root and isolated no-bytecode Python required")
    for path in (OUT, OUT / "host", OUT / "commands.jsonl", SRC, SRC / ".git"):
        checked(path)
    globals()[args.mode.replace("-", "_")]()


if __name__ == "__main__":
    main()
