"""Compile the actual timer configuration functions with a captured hardware call."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def function(source, name):
    matches = list(re.finditer(r"(?m)^(?:static )?void " + name + r"\(", source))
    if len(matches) != 1:
        raise RuntimeError("unique actual timer function required: " + name)
    start = matches[0].start()
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:opening].strip() + ";", source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    guard = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))["checked_output"]
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError("explicit project-root cwd required")
    out = guard(ROOT, args.out)
    if out.exists():
        raise RuntimeError("fresh output directory required")
    names = ("tmp", "home", "appdata", "localappdata", "compile.log", "run.log", "test.exe",
             "timer_config_under_test.inc", "result.json")
    for name in names:
        guard(ROOT, out / name)
    source_path = ROOT / "MDK-ARM_F435/Platform/Core/timer.c"
    source = source_path.read_text(encoding="utf-8")
    selected = [function(source, name) for name in
                ("Timer_TimeFactorization", "Timer_SetInterrupt", "Timer_SetInterruptWithPriority")]
    config_path = ROOT / "MDK-ARM_F435/Platform/mcu_config.h"
    defaults = re.findall(r"(?m)^#define\s+TIMER_(?:PREEMPTIONPRIORITY|SUBPRIORITY)_DEFAULT[^\n]*",
                          config_path.read_text(encoding="utf-8"))
    if len(defaults) != 2:
        raise RuntimeError("actual default priority definitions required")
    hal = (ROOT / "USER/HAL/HAL.cpp").read_text(encoding="utf-8")
    if not re.search(r"Timer_SetInterruptWithPriority\(CONFIG_HAL_UPDATE_TIM,\s*10\s*\*\s*1000,\s*HAL_TimerInterrputUpdate,\s*2,\s*0\)", hal):
        raise RuntimeError("HAL periodic update priority/cadence regression")
    compiler = shutil.which("gcc") or (r"D:\install\mingw64\bin\gcc.exe" if os.name == "nt" else None)
    if not compiler or not Path(compiler).is_file():
        raise RuntimeError("host C compiler required")
    out.mkdir(parents=True)
    env = dict(os.environ)
    for key, name in dict(TEMP="tmp", TMP="tmp", TMPDIR="tmp", HOME="home", USERPROFILE="home",
                          APPDATA="appdata", LOCALAPPDATA="localappdata").items():
        path = guard(ROOT, out / name)
        path.mkdir(exist_ok=True)
        env[key] = str(path)
    env.update(CCACHE_DISABLE="1", SCCACHE_DISABLE="1", PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    extracted = "\n".join(defaults + [item[0] for item in selected] + [item[1] for item in selected]) + "\n"
    with guard(ROOT, out / "timer_config_under_test.inc").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(extracted)
    command = [compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-I" + str(out),
               str(ROOT / "tests/ota/test_timer_priority.c"), "-o", str(out / "test.exe")]
    options = dict(cwd=ROOT, env=env, capture_output=True, timeout=90)
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    results = []
    for label, argv in (("compile", command), ("run", [str(out / "test.exe")])):
        result = subprocess.run(argv, **options)
        with guard(ROOT, out / (label + ".log")).open("xb") as stream:
            stream.write(result.stdout + result.stderr)
        print((result.stdout + result.stderr).decode("utf-8", "replace"), end="")
        results.append(dict(label=label, command=argv, exit_code=result.returncode))
        if result.returncode:
            return result.returncode
    with guard(ROOT, out / "result.json").open("x", encoding="utf-8") as stream:
        json.dump(dict(passed=True, source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
            config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
            extracted_sha256=hashlib.sha256(extracted.encode()).hexdigest(), commands=results,
            scope="actual timing/configuration C functions; hardware setup call captured; HAL binding checked"), stream, indent=2)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
