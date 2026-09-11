#!/usr/bin/env python3
"""Workspace-contained Android debug APK support for the development workflow."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Tools.flutter.dev_checks import APP, checked_path, make_directory


APK_RELATIVE = APP / "build/app/outputs/flutter-apk/app-debug.apk"
APPLICATION_ID_ENV = "TRACE_DEV_APP_ID_SUFFIX"
APPLICATION_ID_SUFFIX_PATTERN = re.compile(r"^\.[A-Za-z][A-Za-z0-9_]*$")


def android_versions(root):
    properties = (root / APP / "android/gradle/wrapper/gradle-wrapper.properties").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"^distributionUrl=https\\?://services\.gradle\.org/distributions/"
        r"gradle-(\d+(?:\.\d+){1,2})-all\.zip\s*$", properties, re.MULTILINE,
    )
    if not match:
        raise ValueError("Expected an official, versioned Gradle wrapper distribution")
    source = (root / APP / "android/app/build.gradle.kts").read_text(encoding="utf-8")
    compile_sdk = re.findall(r"^\s*compileSdk\s*=\s*(\d+)\s*$", source, re.MULTILINE)
    if len(compile_sdk) != 1:
        raise ValueError("APK bootstrap requires one explicit compileSdk in the app config")
    return match.group(1), compile_sdk[0]


def application_id_suffix(env):
    """显式启用的调试包名后缀；未设置即空串（生产 application id 不变）。"""
    suffix = (env.get(APPLICATION_ID_ENV) or "").strip()
    if suffix and not APPLICATION_ID_SUFFIX_PATTERN.fullmatch(suffix):
        raise ValueError(
            f"{APPLICATION_ID_ENV} must be a dot-prefixed package segment such as '.dev'"
        )
    return suffix


def expected_application_id(root, suffix):
    source = (root / APP / "android/app/build.gradle.kts").read_text(encoding="utf-8")
    found = re.findall(r'^\s*applicationId\s*=\s*"([^"]+)"\s*(?://.*)?$', source, re.MULTILINE)
    if len(found) != 1:
        raise ValueError("APK identity requires one explicit applicationId in the app config")
    return found[0] + suffix


def read_application_id(root, run_dir, apk, run=subprocess.run):
    """从产物自身读取最终 application id，而不是采信构建意图。

    调试后缀只由 Gradle 应用，工作流/helper 都无法断言它真的生效；产物身份
    必须由 APK 里的 manifest 记录证明（aapt2），否则会得到"看似可共存、实际
    仍是生产包名"的假阳性产物。
    """
    toolchain = json.loads(
        checked_path(root, run_dir / "apk-toolchain.json").read_text(encoding="utf-8")
    )
    aapt2 = checked_path(
        root, run_dir / f"android-sdk/build-tools/{toolchain['build_tools']}/aapt2"
    )
    result = run(
        [str(aapt2), "dump", "badging", str(apk)], cwd=root, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if result.returncode != 0:
        raise ValueError("aapt2 could not read the debug APK identity")
    match = re.search(r"^package: name='([^']+)'", result.stdout, re.MULTILINE)
    if not match:
        raise ValueError("aapt2 output has no package identity")
    return match.group(1)


def environment(root, run_dir, env):
    env = dict(env)
    env["ETRACK_ANDROID_SDK_SOURCE"] = env.get("ANDROID_HOME") or env.get("ANDROID_SDK_ROOT", "")
    env["JAVA_HOME"] = env.get("JAVA_HOME_17_X64", "")
    for name in ("JAVA_OPTS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "SDKMANAGER_OPTS"):
        env.pop(name, None)
    for name, relative in {
        "ANDROID_HOME": "android-sdk", "ANDROID_SDK_ROOT": "android-sdk",
        "ANDROID_USER_HOME": "home/.android", "ANDROID_SDK_HOME": "home",
        "ANDROID_AVD_HOME": "android-avd",
    }.items():
        env[name] = str(make_directory(root, run_dir / relative))
    env["JAVA_TOOL_OPTIONS"] = (
        f'-Duser.home="{env["HOME"]}" -Djava.io.tmpdir="{env["TMPDIR"]}"'
    )
    env["GRADLE_OPTS"] = "-Dorg.gradle.daemon=false"
    for name in list(env):
        if name.startswith(("ANDROID_RELEASE_", "SIDELOAD_")):
            del env[name]
    return env


def plan(root, run_dir, env):
    version, compile_sdk = android_versions(root)
    helper = [sys.executable, "-B", str(root / "Tools/flutter/dev_apk.py")]
    common = ["--repo-root", str(root), "--run-dir", str(run_dir)]
    source = Path(env.get("ETRACK_ANDROID_SDK_SOURCE") or run_dir / "missing-android-tools")
    java = Path(env.get("JAVA_HOME") or run_dir / "missing-java") / "bin/java"
    sdk = run_dir / "android-sdk"
    gradle = run_dir / f"gradle-dist/gradle-{version}/bin/gradle"
    bootstrap = run_dir / "wrapper-bootstrap"
    return [
        ("apk_prepare", helper + ["prepare", *common], root, 900),
        ("apk_java", [str(java), "-version"], root, 30),
        ("apk_sdk", [str(source / "cmdline-tools/latest/bin/sdkmanager"),
                     f"--sdk_root={sdk}", "cmdline-tools;latest", "platform-tools", f"platforms;android-{compile_sdk}",
                     "build-tools;35.0.0"], root, 600),
        ("apk_wrapper", [str(gradle), "--no-daemon", "-p", str(bootstrap), "wrapper",
                         "--gradle-version", version, "--distribution-type", "all"], root, 300),
        ("apk_install_wrapper", helper + ["install-wrapper", *common], root, 30),
        ("apk_build", [str(run_dir / "sdk/bin/flutter"), "build", "apk", "--debug",
                       "--no-pub", "--target-platform=android-arm,android-arm64"], root / APP, 1200),
        ("apk_verify", [str(sdk / "build-tools/35.0.0/apksigner"), "verify", "--verbose",
                        str(root / APK_RELATIVE)], root, 60),
        ("apk_collect", helper + ["collect", *common], root, 30),
    ]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, path, max_bytes):
    with urllib.request.urlopen(url, timeout=60) as response, path.open("xb") as output:
        if not response.url.startswith("https://"):
            raise ValueError("Insecure distribution redirect")
        size = 0
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("Distribution download exceeded its size limit")
            output.write(chunk)


def extract_distribution(root, archive, destination):
    checked_path(root, destination)
    with zipfile.ZipFile(archive) as source:
        entries = []
        for entry in source.infolist():
            relative = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if (relative.is_absolute() or ".." in relative.parts or "\\" in entry.orig_filename
                    or ":" in entry.orig_filename or stat.S_ISLNK(mode)):
                raise ValueError(f"Unsafe distribution member: {entry.filename}")
            target = checked_path(root, destination / Path(*relative.parts))
            entries.append((entry, target))
        if sum(entry.file_size for entry, _ in entries) > 512 * 1024 * 1024:
            raise ValueError("Expanded distribution exceeds its size limit")
        for entry, target in entries:
            if entry.is_dir():
                make_directory(root, target)
            else:
                make_directory(root, target.parent)
                with source.open(entry) as data, checked_path(root, target).open("xb") as output:
                    shutil.copyfileobj(data, output)


def write_new(root, path, content):
    make_directory(root, path.parent)
    with checked_path(root, path).open("x", encoding="utf-8", newline="\n") as output:
        output.write(content)


def copy_new(root, source, target):
    make_directory(root, target.parent)
    with source.open("rb") as data, checked_path(root, target).open("xb") as output:
        shutil.copyfileobj(data, output)


def assert_ignored(root, path):
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), "check-ignore", "--quiet", "--", str(path)],
        cwd=root, capture_output=True, timeout=15,
    )
    if result.returncode != 0:
        raise ValueError(f"Refusing to change a tracked or non-ignored output: {path}")


def prepare(root, run_dir, env, fetch=download):
    version, compile_sdk = android_versions(root)
    application_id = expected_application_id(root, application_id_suffix(env))
    source = Path(env.get("ETRACK_ANDROID_SDK_SOURCE", ""))
    java = Path(env.get("JAVA_HOME", "")) / "bin/java"
    if not env.get("JAVA_HOME") or not java.is_file():
        raise ValueError("Hosted JDK 17 (JAVA_HOME_17_X64) is required")
    if not (source / "cmdline-tools/latest/bin/sdkmanager").is_file():
        raise ValueError("Hosted Android command-line tools are required as read-only input")
    if checked_path(root, root / APK_RELATIVE).exists():
        raise ValueError("Refusing to reuse a pre-existing APK")
    if (root / APP / "android/key.properties").exists():
        raise ValueError("Development APK mode must not use release signing properties")
    licenses = source / "licenses"
    accepted = sorted(licenses.glob("*-license"))
    if not accepted:
        raise ValueError("Hosted Android license records are missing; do not auto-accept terms")
    for license_file in accepted:
        copy_new(root, license_file, run_dir / "android-sdk/licenses" / license_file.name)
    distribution = checked_path(root, run_dir / f"gradle-{version}-bin.zip")
    checksum = checked_path(root, run_dir / "gradle.sha256")
    url = f"https://services.gradle.org/distributions/gradle-{version}-bin.zip"
    fetch(url + ".sha256", checksum, 4096)
    expected = checksum.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ValueError("Invalid Gradle distribution checksum")
    fetch(url, distribution, 256 * 1024 * 1024)
    if sha256(distribution) != expected.lower():
        raise ValueError("Gradle distribution checksum mismatch")
    extract_distribution(root, distribution, run_dir / "gradle-dist")
    gradle = checked_path(root, run_dir / f"gradle-dist/gradle-{version}/bin/gradle")
    if not gradle.is_file():
        raise ValueError("Gradle distribution has no expected launcher")
    gradle.chmod(0o755)
    write_new(root, run_dir / "wrapper-bootstrap/settings.gradle",
              "rootProject.name = 'flutter-dev-wrapper'\n")
    # AGP 8.9.1 uses Build Tools 35.0.0; compileSdk comes from the tracked app.
    write_new(root, run_dir / "apk-toolchain.json", json.dumps({
        "gradle_version": version, "gradle_sha256": expected.lower(),
        "compile_sdk": compile_sdk, "build_tools": "35.0.0",
        "java_home": str(java.parent.parent), "android_tools_source": str(source),
        "application_id": application_id,
    }, indent=2) + "\n")


def install_wrapper(root, run_dir):
    _, compile_sdk = android_versions(root)
    sdk = run_dir / "android-sdk"
    for relative in ("cmdline-tools/latest/bin/sdkmanager", "platform-tools/adb", f"platforms/android-{compile_sdk}/android.jar",
                     "build-tools/35.0.0/apksigner", "build-tools/35.0.0/aapt2"):
        if not checked_path(root, sdk / relative).is_file():
            raise ValueError(f"Android package was not installed: {relative}")
    for relative in ("gradlew", "gradlew.bat", "gradle/wrapper/gradle-wrapper.jar"):
        target = checked_path(root, root / APP / "android" / relative)
        assert_ignored(root, target)
        make_directory(root, target.parent)
        with (run_dir / "wrapper-bootstrap" / relative).open("rb") as source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
    checked_path(root, root / APP / "android/gradlew").chmod(0o755)
    properties = checked_path(root, root / APP / "android/local.properties")
    assert_ignored(root, properties)
    previous = properties.read_text(encoding="utf-8").splitlines() if properties.exists() else []
    kept = [line for line in previous if not line.startswith(("flutter.sdk=", "sdk.dir="))]
    with properties.open("w", encoding="utf-8", newline="\n") as output:
        output.write("\n".join([*kept, f"flutter.sdk={run_dir / 'sdk'}", f"sdk.dir={sdk}"]) + "\n")


def collect(root, run_dir, commit, env):
    source = checked_path(root, root / APK_RELATIVE)
    if not source.is_file() or not source.stat().st_size:
        raise ValueError("Debug APK is missing or empty")
    with zipfile.ZipFile(source) as apk:
        if "AndroidManifest.xml" not in apk.namelist():
            raise ValueError("Debug APK has no Android manifest")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit or ""):
        raise ValueError("An exact tested commit is required for the APK record")
    expected = expected_application_id(root, application_id_suffix(env))
    observed = read_application_id(root, run_dir, source)
    if observed != expected:
        raise ValueError(
            f"Debug APK declares application id {observed}, expected {expected}"
        )
    target = checked_path(root, run_dir / "artifacts/trace-dev-debug.apk")
    copy_new(root, source, target)
    metadata = {
        "artifact_kind": "development-debug-apk", "formal_acceptance": "NOT_RUN",
        "commit": commit, "sha256": sha256(target), "bytes": target.stat().st_size,
        "file": target.name, "release_signing": False, "application_id": observed,
    }
    write_new(root, target.with_suffix(".json"), json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "install-wrapper", "collect"))
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if (os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "linux"
            or not os.environ.get("GITHUB_REF", "").startswith("refs/heads/dev/flutter/")):
        parser.error("APK helper is restricted to Linux CI on dev/flutter/** branches")
    root = Path(os.path.abspath(args.repo_root))
    if Path(os.environ.get("GITHUB_WORKSPACE", "")).absolute() != root:
        parser.error("--repo-root must equal GITHUB_WORKSPACE")
    try:
        run_dir = checked_path(root, args.run_dir)
        if not run_dir.is_relative_to(root / ".cache/flutter-dev-checks/runs"):
            raise ValueError("APK output must belong to a development-check run")
        if args.phase == "prepare":
            prepare(root, run_dir, os.environ)
        elif args.phase == "install-wrapper":
            install_wrapper(root, run_dir)
        else:
            collect(root, run_dir, os.environ.get("GITHUB_SHA"), os.environ)
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Development APK failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
