"""Authorized isolated group1/group16 GCC Boot build; no device operations."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_boot_checkpoint_model as model
import p34_boot_candidate as toolchain

AREA = ROOT / ".cache/p34-bc-target"
SNAP = AREA / "f"
CM = Path("MDK-ARM_F435/cmake-generated/CMakeLists.txt")
ADD = '''
# Isolated BOOT-CP-02 development scope; never enabled in production sources.
set(P34_BOOT_APPLY_CHECKPOINT_BLOCKS "1" CACHE STRING "APPLY checkpoint blocks")
if(NOT P34_BOOT_APPLY_CHECKPOINT_BLOCKS MATCHES "^(1|16)$")
    message(FATAL_ERROR "Only reviewed group1/group16 target configurations allowed")
endif()
target_compile_definitions(X_Track_Boot PRIVATE
    "P34_BOOT_APPLY_CHECKPOINT_BLOCKS=${P34_BOOT_APPLY_CHECKPOINT_BLOCKS}")
target_compile_options(X_Track_Boot PRIVATE -fstack-usage)
'''


def main():
    cli, host = model.cli, model.host
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode, "isolated explicit project root required")
    s = cli.Store(ROOT)
    s.checked(AREA)
    cli.require(not AREA.exists(), "preserve target build evidence")
    model.validate(s)
    prior = s.read(model.AREA / "review-tests1/result.json")
    for r in prior["sources"]:
        cli.require(cli.record(r["path"]) == r, "reviewed source drift")
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    listing = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             cwd=ROOT, env=env, capture_output=True, check=True, timeout=30)
    cmake = (ROOT / CM).read_text(encoding="utf-8")
    refs = [(ROOT / CM.parent / p).resolve() for p in
            re.findall(r'\$\{CMAKE_CURRENT_LIST_DIR\}/([^"\n]+)', cmake) if "${" not in p]
    roots = {p.relative_to(ROOT).parts[0] for p in refs} | {"boot", "cmake", "tests", ".github"}
    suffixes = {".c", ".cpp", ".h", ".hpp", ".s", ".inc", ".def", ".cmake", ".ld", ".txt", ".yml", ".py"}
    files = set()
    for name in listing.stdout.decode("utf-8").split("\0"):
        if name and Path(name).parts[0] in roots and Path(name).suffix.lower() in suffixes:
            p = ROOT / name
            if p.is_file(): files.add(p)
    # Include generated/ignored literal CMake inputs and vendor header closures.
    for p in refs:
        if p.is_file(): files.add(p)
        elif p.is_dir():
            files.update(x for x in p.rglob("*") if x.is_file() and
                         x.suffix.lower() in {".h", ".hpp", ".inc", ".def"})
    files.update({ROOT / CM, ROOT / "cmake/reproducible_build.cmake",
                  ROOT / "tests/boot/validate_boot_artifact.py", ROOT / ".github/workflows/firmware-build.yml"})
    files = sorted(files)
    for p in files:
        s.checked(p)
        s.checked(SNAP / p.relative_to(ROOT))
    policy_out = s.checked(SNAP / "boot/include/p34_boot_checkpoint.h")
    for name in ("inputs.json", "snapshot.json", "result.json"):
        s.checked(AREA / name)
    for group in (1, 16):
        s.checked(AREA / ("b" + str(group)))
        s.checked(AREA / ("install" + str(group)))
        for tag in ("configure", "build", "validate", "size", "attributes", "disassembly", "symbols"):
            for suffix in (".json", ".log"): s.checked(AREA / ("g%d-%s%s" % (group, tag, suffix)))
    for suffix in (".json", ".log"): s.checked(AREA / ("compiler-version" + suffix))
    bound_paths = files + [model.POLICY, Path(__file__), ROOT / "Tools/ota/p34_install_cost.py",
                           ROOT / "Tools/ota/p34_boot_candidate.py", model.AREA / "review-tests1/result.json"]
    bound = [cli.record(p) for p in bound_paths]
    env = host.environment(s, AREA)
    env["PATH"] = str(toolchain.ARM / "bin") + os.pathsep + env["PATH"]
    for key in ("GCC_EXEC_PREFIX", "COMPILER_PATH", "LIBRARY_PATH", "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH"):
        env.pop(key, None)
    s.write(AREA / "inputs.json", dict(sources=bound, authorization="user-approved isolated Boot-only build",
                                     hardware=False))
    for p in files:
        dst = s.checked(SNAP / p.relative_to(ROOT))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
    # Generated experimental snapshot deltas; originals remain source-bound.
    boot = SNAP / "boot/src/boot_state_machine.c"
    original = boot.read_text(encoding="utf-8")
    cli.require(original.count(model.OLD) == 1, "unique grouping anchor")
    updated = original.replace('#include "boot_state_machine.h"',
                               '#include "boot_state_machine.h"\n#include "p34_boot_checkpoint.h"', 1)
    updated = updated.replace(model.OLD, model.NEW)
    cli.require(updated == (model.AREA / "boot_state_machine.c").read_text(encoding="utf-8"), "reviewed delta mismatch")
    boot.write_text(updated, encoding="utf-8", newline="\n")
    (SNAP / CM).write_text(cmake + ADD, encoding="utf-8", newline="\n")
    shutil.copyfile(model.POLICY, policy_out)
    snapshot_paths = sorted(p for p in SNAP.rglob("*") if p.is_file())
    snapshot = [cli.record(p) for p in snapshot_paths]
    s.write(AREA / "snapshot.json", dict(files=snapshot, deltas=[str(boot), str(SNAP / CM), str(policy_out)]))
    arm = toolchain.ARM / "bin"
    host.command(s, AREA, "compiler-version", [arm / "arm-none-eabi-gcc.exe", "--version"], env, 30)
    results = {}
    for group in (1, 16):
        b = AREA / ("b" + str(group)); tag = "g%d-" % group
        args = [toolchain.CMAKE, "-S", SNAP / CM.parent, "-B", b, "-G", "Ninja",
                "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024",
                "-DCMAKE_MAKE_PROGRAM=" + toolchain.NINJA, "-DARM_TOOLCHAIN_ROOT=" + str(toolchain.ARM),
                "-DKEIL_GCC_COMPILER_CACHE=OFF", "-DCMAKE_INSTALL_PREFIX=" + str(AREA / ("install" + str(group))),
                "-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON", "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
                "-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=ON", "-DP34_BOOT_APPLY_CHECKPOINT_BLOCKS=" + str(group)]
        config = host.command(s, AREA, tag + "configure", args, env, 180)
        build = host.command(s, AREA, tag + "build", [toolchain.CMAKE, "--build", b, "--target", "X_Track_Boot", "--parallel", "4"], env, 240)
        host.command(s, AREA, tag + "validate", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
                     SNAP / "tests/boot/validate_boot_artifact.py", "--build-dir", b], env, 30)
        elf = b / "boot/X-Track-Boot.elf"
        for name, binary, flags in (("size", "size", ["--format=berkeley"]),
                                   ("attributes", "readelf", ["-h", "-A", "-S"]),
                                   ("disassembly", "objdump", ["-d"]),
                                   ("symbols", "nm", ["-S", "--size-sort"])):
            host.command(s, AREA, tag + name, [arm / ("arm-none-eabi-" + binary + ".exe"), *flags, elf], env, 30)
        su = sorted(b.rglob("*.su"))
        cli.require(su, "missing target stack sidecars")
        commands = json.loads((b / "compile_commands.json").read_text())
        boot_commands = [c for c in commands if "X_Track_Boot.dir" in c["command"]]
        cli.require(boot_commands and all("-fstack-usage" in c["command"] for c in boot_commands), "missing stack flags")
        cli.require(all("P34_BOOT_APPLY_CHECKPOINT_BLOCKS=" + str(group) in c["command"] for c in boot_commands), "wrong group")
        results[str(group)] = dict(artifacts=[cli.record(b / "boot" / ("X-Track-Boot." + ext)) for ext in ("bin", "elf", "hex", "map")],
            stack_files=[cli.record(p) for p in su], configuration=[cli.record(b / p) for p in
            ("CMakeCache.txt", "compile_commands.json", "reproducible-build.txt", "boot/x-track-boot-gcc.ld")],
            warnings=len(re.findall(rb"(?i)warning", config + build)), errors=len(re.findall(rb"(?i)error:", config + build)))
        print("TARGET_BUILT", group, results[str(group)]["artifacts"][0]["bytes"], flush=True)
    cli.require(bound == [cli.record(p) for p in bound_paths], "original inputs changed")
    cli.require(snapshot == [cli.record(p) for p in snapshot_paths], "snapshot changed during build")
    saved = ROOT / ".cache/p34-boot/preparation/candidate/boot/X-Track-Boot.bin"
    s.write(AREA / "result.json", dict(result="ISOLATED_BOOT_TARGETS_BUILT", variants=results,
        baseline_matches_saved_candidate=(AREA / "b1/boot/X-Track-Boot.bin").read_bytes() == saved.read_bytes(),
        saved_candidate=cli.record(saved), inputs=cli.record(AREA / "inputs.json"), snapshot=cli.record(AREA / "snapshot.json"),
        hardware=False, independent_acceptance=False, stack_closure="NOT_YET_ANALYZED", measured_speedup=False))


if __name__ == "__main__":
    main()
