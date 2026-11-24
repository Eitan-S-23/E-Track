"""Build an isolated App-only SHA -O2 candidate; no packaging or device actions."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_sha_screen as screen

cli, host = screen.cli, screen.host
BASE, AREA = screen.BASE, ROOT / ".cache/p34-sha-candidate"
CMAKE = "MDK-ARM_F435/cmake-generated/CMakeLists.txt"
APPEND = '\n# P3-4 local screen: preserve Boot and all other compilation options.\n' + \
    'set_property(SOURCE "${CMAKE_CURRENT_LIST_DIR}/../../boot/src/boot_sha256.c"\n' + \
    '    APPEND PROPERTY COMPILE_OPTIONS\n' + \
    '    "$<$<STREQUAL:$<TARGET_PROPERTY:NAME>,X_Track_App_GCC>:-O2>")\n'


def prepare(s):
    fw = s.checked(AREA / "f")
    cli.require(not fw.exists(), "preserve candidate")
    manifest = s.read(BASE / "build/source.json")
    copies = []
    for item in manifest["files"]:
        source = s.checked(item["path"])
        cli.require(cli.record(source) == item, "measured source changed")
        copies.append((source, s.checked(fw / source.relative_to(BASE / "f"))))
    for source, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    print("SHA_CANDIDATE_COPIED", len(copies))


def verify(s):
    proof = s.read(ROOT / ".cache/p34-sha-screen/r1/result.json")
    cli.require(proof["result"] == "SHA_OPTIMIZATION_HOST_SCREEN_PASS", "SHA screen required")
    for item in proof["inputs"]:
        cli.require(cli.record(item["path"]) == item, "screen input changed")
    for item in s.read(BASE / "build/source.json")["files"]:
        source = Path(item["path"])
        cli.require(cli.record(source) == item, "measured source changed")
        relative = source.relative_to(BASE / "f")
        target = s.checked(AREA / "f" / relative)
        if relative.as_posix() == CMAKE:
            cli.require(target.read_text(encoding="utf-8") == source.read_text(encoding="utf-8") + APPEND,
                        "unexpected SHA build integration")
        else:
            cli.require(target.read_bytes() == source.read_bytes(), "unrelated candidate delta")


def build(s):
    verify(s)
    fw, bld, out = (s.checked(AREA / name) for name in ("f", "b", "build"))
    cli.require(not bld.exists() and not out.exists(), "preserve build evidence")
    s.checked(AREA / "install")
    for name in ("source.json", "configure.log", "configure.json", "build.log", "build.json", "result.json"):
        s.checked(out / name)
    args = [str(x).replace(str(BASE), str(AREA)) for x in s.read(BASE / "build/configure.json")["command"]]
    s.write(out / "source.json", dict(base=cli.record(BASE / "build/source.json"), overlays=[CMAKE],
        files=[cli.record(p) for p in sorted(fw.rglob("*")) if p.is_file()]))
    env = host.environment(s, out)
    host.command(s, out, "configure", args, env, 180)
    lines = (bld / "build.ninja").read_text().splitlines()
    bindings = {}
    for target in ("X_Track_App_GCC", "X_Track_Boot"):
        indexes = [i for i, line in enumerate(lines) if line.startswith("build CMakeFiles/" + target + ".dir/")
                   and "/boot_sha256.c.obj:" in line]
        cli.require(len(indexes) == 1, "SHA target binding missing")
        flags = next(line for line in lines[indexes[0]:indexes[0]+8] if line.startswith("  FLAGS = "))
        cli.require(("-O2" in flags) == (target == "X_Track_App_GCC"), "optimization escaped App SHA")
        bindings[target] = flags
    raw = host.command(s, out, "build", [args[0], "--build", bld, "--target", "X_Track_App_GCC", "--parallel", "6"], env, 900)
    def warnings(data):
        return Counter(line.strip() for line in data.replace(b"p34-sha-candidate", b"p34-timed-ack").splitlines()
                       if b"warning:" in line)
    old, new = warnings((BASE / "build/build.log").read_bytes()), warnings(raw)
    added = [line.decode(errors="replace") for line in (new-old).elements()]
    value = dict(result="SHA_APP_CANDIDATE_BUILT", warnings=sum(new.values()), new_warnings=added,
        errors=raw.count(b"error:"), boot_built=False, device_operations=0, measured_speedup=False,
        compile_bindings=bindings, source=cli.record(out / "source.json"),
        artifacts=[cli.record(bld / "app-gcc" / ("X-Track-App-GCC" + ext)) for ext in (".bin", ".elf", ".map", ".hex")])
    s.write(out / "result.json", value)
    cli.require(not added and not value["errors"], "new build diagnostics require review")
    verify(s)
    print(json.dumps(value))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit isolated root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "build"))
    args = parser.parse_args()
    (prepare if args.mode == "prepare" else build)(cli.Store(ROOT))
