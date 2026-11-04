"""P51-UI-01: actual page methods + bundled LVGL, no device operations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def guard(path: Path) -> Path:
    path.resolve().relative_to(ROOT.resolve())
    for parent in (path, *path.parents):
        if parent.exists() and parent.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError(f"Reparse output: {parent}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", choices=("old", "fixed", "followup-baseline"), required=True)
    parser.add_argument("--reuse-lvgl", help="Read-only reuse of this runner's existing LVGL build")
    args = parser.parse_args()
    output = guard(ROOT / args.output)
    if output.exists():
        raise RuntimeError("Use a fresh output directory; preserve previous results")
    tmp = guard(output / "tmp")
    build = guard(output / "lvgl")
    exe = guard(output / "test_file_browser.exe")
    for name in ("commands.json", "inputs.json", "summary.json"):
        guard(output / name)
    env = os.environ.copy()
    env.update(TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp), PYTHONDONTWRITEBYTECODE="1")
    output.mkdir(parents=True)
    tmp.mkdir()
    commands = []

    def run(argv: list[str], name: str) -> int:
        log = guard(output / (name + ".log"))
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=300)
        log.write_bytes(result.stdout)
        print(result.stdout.decode("utf-8", errors="replace"), end="")
        commands.append(dict(argv=argv, cwd=str(ROOT), exit_code=result.returncode,
                             log=str(log.relative_to(ROOT))))
        guard(output / "commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        return result.returncode

    cc = shutil.which("gcc")
    cxx = shutil.which("g++")
    if not cc or not cxx:
        raise RuntimeError("Host gcc/g++ required")
    sources = [
        "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp",
        "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h",
        "USER/App/Pages/RouteSelect/RouteSelect.cpp",
        "tests/ui/test_file_browser.cpp", "tests/ui/lv_conf.h",
        "tests/ui/test_file_browser.py",
        "USER/App/Utils/OtaUpdate/OtaUpdate.cpp",
    ]
    inputs = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources}
    for font in (ROOT / "USER/App/Resource/Font").glob("*.c"):
        inputs[str(font.relative_to(ROOT))] = hashlib.sha256(font.read_bytes()).hexdigest()
    inputs["simulator_lv_conf_sha256"] = hashlib.sha256((ROOT / "Simulator/LVGL.Simulator/lv_conf.h").read_bytes()).hexdigest()
    lvgl_source = "Simulator/LVGL.Simulator/lvgl"
    if subprocess.check_output(["git", "status", "--porcelain", "--", lvgl_source], cwd=ROOT).strip():
        raise RuntimeError("This runner requires the unmodified bundled LVGL")
    helper = "USER/App/Utils/lv_ext/lv_file_browser_label.h"
    if (ROOT / helper).exists():
        inputs[helper] = hashlib.sha256((ROOT / helper).read_bytes()).hexdigest()
    inputs["HEAD"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    inputs["lvgl_tree"] = subprocess.check_output(["git", "rev-parse", "HEAD:" + lvgl_source], cwd=ROOT).decode().strip()
    (output / "inputs.json").write_text(json.dumps(inputs, indent=2), encoding="utf-8")
    conf = ROOT / "tests/ui/lv_conf.h"
    if args.reuse_lvgl:
        build = guard(ROOT / args.reuse_lvgl)
        previous = json.loads((build.parent / "inputs.json").read_text(encoding="utf-8"))
        if previous["tests/ui/lv_conf.h"] != inputs["tests/ui/lv_conf.h"] or previous["HEAD"] != inputs["HEAD"]:
            raise RuntimeError("Reused LVGL configuration differs")
        inputs["lvgl_library_sha256"] = hashlib.sha256((build / "lib/liblvgl.a").read_bytes()).hexdigest()
        inputs["lvgl_library_path"] = str(build)
        (output / "inputs.json").write_text(json.dumps(inputs, indent=2), encoding="utf-8")
    else:
        rc = run(["cmake", "-S", str(ROOT / "Simulator/LVGL.Simulator/lvgl"), "-B", str(build),
              "-G", "Ninja", f"-DCMAKE_C_COMPILER={cc}", f"-DCMAKE_CXX_COMPILER={cxx}",
              f"-DLV_CONF_PATH={conf}", "-DCMAKE_BUILD_TYPE=Debug",
              "-DCMAKE_C_FLAGS=-Wall -Wextra"], "configure")
        if rc:
            return rc
        rc = run(["cmake", "--build", str(build), "--target", "lvgl", "--parallel", "6"], "lvgl-build")
        if rc:
            return rc
    includes = [ROOT / "tests/ui", ROOT / "Simulator/LVGL.Simulator",
                ROOT / "USER/App", ROOT / "Libraries", ROOT / "boot/include"]
    common = ["-DLV_CONF_INCLUDE_SIMPLE", *[f"-I{p}" for p in includes]]
    objects = []
    for name in ("cn_16", "bahnschrift_13", "bahnschrift_17", "bahnschrift_24", "iconfont_20"):
        obj = guard(output / (name + ".o"))
        rc = run([cc, "-Wall", "-Wextra", *common, "-c",
                  str(ROOT / f"USER/App/Resource/Font/font_{name}.c"), "-o", str(obj)], name)
        if rc:
            return rc
        objects.append(str(obj))
    # Link the exact product formatter, not a service double's different spelling.
    ota_source = (ROOT / "USER/App/Utils/OtaUpdate/OtaUpdate.cpp").read_text(encoding="utf-8")
    begin = ota_source.index("void Session::FormatVersion(")
    end = ota_source.index("bool Session::OpenSelectedFile(", begin)
    formatter = guard(output / "format_version.cpp")
    formatter.write_text('#include "Utils/OtaUpdate/OtaUpdate.h"\n#include <stdio.h>\nnamespace OtaUpdate {\n'
                         + ota_source[begin:end] + '}\n', encoding="utf-8")
    rc = run([cxx, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-Wno-error=unused-parameter", "-g", *common,
              "-DP51_FIXED=" + str(int(args.phase != "old")),
              "-DP51_FOLLOWUP_BASELINE=" + str(int(args.phase == "followup-baseline")),
              str(ROOT / "tests/ui/test_file_browser.cpp"),
              str(ROOT / "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp"),
              str(ROOT / "USER/App/Pages/RouteSelect/RouteSelect.cpp"),
              str(ROOT / "USER/App/Utils/PageManager/PageBase.cpp"),
              str(formatter),
              *objects, str(build / "lib/liblvgl.a"), "-o", str(exe)], "page-build")
    if rc:
        return rc
    rc = run([str(exe), str(output)], "layout")
    from PIL import Image
    for bmp in output.glob("*.bmp"):
        Image.open(bmp).save(guard(bmp.with_suffix(".png")))
    logs = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in output.glob("*.log"))
    if "[Error]" in logs or (args.phase == "fixed" and "glyph dsc. not found for U+76" in logs):
        rc = rc or 1
    summary = dict(phase=args.phase, exit_code=rc, build_warnings=logs.count("warning:"),
                   runtime_warnings=logs.count("[Warn]"), errors=logs.count("error:"),
                   runtime_errors=logs.count("[Error]"),
                   executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    return rc


if __name__ == "__main__":
    sys.exit(main())
