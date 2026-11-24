"""Offline P3-4 install workload census; never operates on a device."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
IO_PATH = ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"
IO = runpy.run_path(str(IO_PATH))
PHASES = ("candidate", "backup", "boot", "boot_resume", "confirmation_commit")
RESOURCES = ("package", "candidate", "backup", "internal", "eeprom")
OPERATIONS = ("read", "erase", "program")
SCENARIOS = ("normal", "bad-package", "bad-candidate", "bad-backup-write",
             "not-confirmed", "cut-before", "cut-after", "bad-resume", "bad-staged")
SOURCES = (
    "tests/ota/install_workload.c", "Libraries/OTA/ota_package.c",
    "Libraries/OTA/ota_backup.c", "Libraries/OTA/ota_slot_header.c",
    "Libraries/OTA/ota_keys.c", "Libraries/EEPROM/eeprom_bcb.c",
    "boot/src/boot_state_machine.c", "boot/src/boot_slot.c",
    "boot/src/boot_fw_header.c", "boot/src/boot_crc32.c", "boot/src/boot_sha256.c",
    "bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c",
    "bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c",
)
INCLUDES = ("Libraries", "boot/include", "bsdiff_lzma_AES128-main/bspatch/lzma",
            "bsdiff_lzma_AES128-main/bspatch/AES128_CTR")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def verify_record(item):
    require(isinstance(item, dict) and set(item) == {"path", "bytes", "sha256"},
            "invalid input binding")
    require(type(item["bytes"]) is int and 0 < item["bytes"] <= 0x180000,
            "invalid input length")
    observed = record(item["path"])
    require(observed["bytes"] == item["bytes"] and observed["sha256"] == item["sha256"],
            "input hash/length mismatch: " + str(item["path"]))
    return observed


def load_assets(path):
    original = record(path)
    data = json.loads(Path(original["path"]).read_text(encoding="utf-8"))
    inputs = {"package": verify_record(data["groups"]["screen"]["package"]),
              "current": verify_record(data["baseline"]),
              "target": verify_record(data["target"])}
    for name in ("current", "target"):
        raw = Path(inputs[name]["path"]).read_bytes()
        require(0x460 <= len(raw) <= 0xF0000 and raw[0x400:0x404] == b"ETFW",
                "invalid image header envelope")
        # Full CRC/SHA/header validation is performed by the native Boot code.
        inputs[name + "_vcode"] = struct.unpack_from("<I", raw, 0x408)[0]
    return original, inputs


def source_records():
    paths = {ROOT / name for name in SOURCES}
    paths.update((ROOT / __file__, IO_PATH, ROOT / "USER/HAL/HAL_OTA_Package.cpp"))
    for directory in ("Libraries/OTA", "Libraries/EEPROM", *INCLUDES[1:]):
        paths.update((ROOT / directory).glob("*.h"))
    return [record(path) for path in sorted(paths)]


def cases_for(image_length):
    require(type(image_length) is int and 0x460 <= image_length <= 0xF0000,
            "image length outside App slot")
    blocks = (image_length + 4095) // 4096
    cases = [(name, 0) for name in SCENARIOS if name not in
             ("cut-before", "cut-after", "bad-resume")]
    for block in sorted({1, max(1, blocks // 2), blocks}):
        cases.extend((("cut-before", block), ("cut-after", block)))
    cases.append(("bad-resume", max(1, blocks // 2)))
    return cases


def validate_result(value, scenario, cut_block, inputs):
    require(isinstance(value, dict) and type(value.get("schema")) is int and value["schema"] == 1 and
            value.get("kind") == "HOST_INSTALL_WORKLOAD", "invalid native result schema")
    require(value.get("hardware") is False and value.get("hardware_timing") is False,
            "host model cannot claim hardware measurements")
    require(value.get("scenario") == scenario and type(value.get("cut_block")) is int and
            value["cut_block"] == cut_block,
            "scenario mismatch")
    require(value.get("passed") is True and type(value.get("failures")) is int and
            value["failures"] == 0 and type(value.get("checks")) is int and value["checks"] > 0,
            "native checks failed or absent")
    require(value.get("package_bytes") == inputs["package"]["bytes"] and
            value.get("current_bytes") == inputs["current"]["bytes"] and
            value.get("target_bytes") == inputs["target"]["bytes"], "native input sizes differ")
    require(scenario in SCENARIOS, "unknown scenario")
    require(value.get("injection_seen") is (scenario not in ("normal", "not-confirmed")),
            "fault injection not observed")
    phases = value.get("phases", {})
    require(set(phases) == set(PHASES), "phase set mismatch")
    successful_target = scenario in ("normal", "cut-before", "cut-after")
    ran = {"candidate"}
    if scenario != "bad-package":
        ran.add("backup")
    if scenario in ("normal", "cut-before", "cut-after", "bad-resume", "bad-staged"):
        ran.add("boot")
    if cut_block:
        ran.add("boot_resume")
    if successful_target:
        ran.add("confirmation_commit")
    expected_codes = {name: 0 for name in PHASES}
    if scenario == "bad-package":
        expected_codes["candidate"] = -15
    if scenario in ("bad-candidate", "bad-backup-write", "not-confirmed"):
        expected_codes["backup"] = {"bad-candidate": -6, "bad-backup-write": -10,
                                    "not-confirmed": -2}[scenario]
    for name in PHASES:
        item = phases[name]
        interrupted = name == "boot" and cut_block != 0
        require(item.get("ran") is (name in ran) and item.get("interrupted") is interrupted,
                "phase execution mismatch: " + name)
        result = item.get("result_code")
        require((result is None) if name not in ran or interrupted else type(result) is int,
                "invalid phase result: " + name)
        if name in ran and not interrupted:
            require(result == expected_codes[name], "unexpected phase outcome: " + name)
        require(set(item.get("io", {})) == set(RESOURCES), "resource set mismatch")
        for resource in RESOURCES:
            ops = item["io"][resource]
            require(set(ops) == set(OPERATIONS), "operation set mismatch")
            for op in OPERATIONS:
                count = ops[op]
                require(set(count) == {"calls", "bytes"} and all(
                    type(count[key]) is int and 0 <= count[key] < 2**32 for key in count),
                    "invalid I/O count")
                require((count["calls"] == 0) == (count["bytes"] == 0), "empty I/O count")
                require(name in ran or count["calls"] == 0, "I/O in unexecuted phase")
    expected_state = 3 if scenario == "not-confirmed" else 4
    expected_vcode = inputs["target_vcode"] if successful_target else inputs["current_vcode"]
    require(value.get("final_bcb_state") == expected_state and
            value.get("final_vcode") == expected_vcode, "final modeled identity mismatch")
    if scenario != "bad-package":
        require(phases["candidate"]["io"]["candidate"]["program"]["bytes"] == inputs["target"]["bytes"],
                "missing candidate payload writes")
    if successful_target:
        require(phases["backup"]["io"]["backup"]["program"]["bytes"] == inputs["current"]["bytes"] + 32,
                "missing backup payload/header writes")
        require(phases["confirmation_commit"]["io"]["eeprom"]["program"] == {"calls": 1, "bytes": 64},
                "missing confirmation commit")
    return value


class Run:
    def __init__(self, root, out):
        require(Path(root).is_absolute() and Path(root).resolve() == ROOT and
                Path.cwd().resolve() == ROOT, "explicit active project root/cwd required")
        self.root = ROOT
        self.out = IO["checked_output"](ROOT, out)
        require(not self.out.exists(), "output already exists; never overwrite an earlier run")
        self.env = os.environ.copy()
        locations = {
            "TEMP": "temp", "TMP": "temp", "TMPDIR": "temp",
            "HOME": "home", "USERPROFILE": "home", "APPDATA": "appdata",
            "LOCALAPPDATA": "localappdata", "XDG_CACHE_HOME": "cache",
            "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
        }
        self.directories = {key: IO["checked_output"](ROOT, self.out / "environment" / name)
                            for key, name in locations.items()}
        for name in ("build", "logs", "results"):
            IO["checked_output"](ROOT, self.out / name)
        for path in {self.out, *self.directories.values(), *(self.out / name for name in
                                                          ("build", "logs", "results"))}:
            IO["checked_output"](ROOT, path).mkdir(parents=True, exist_ok=True)
        self.env.update({key: str(path) for key, path in self.directories.items()})
        self.env.update(PYTHONDONTWRITEBYTECODE="1", CCACHE_DISABLE="1", GIT_OPTIONAL_LOCKS="0")
        self.commands = []

    def save(self, relative, value):
        return IO["write_json"](self.root, self.out / relative, value)

    def command(self, label, args, timeout=120):
        log = IO["checked_output"](self.root, self.out / "logs" / (label + ".log"))
        require(not log.exists(), "command log already exists")
        receipt = {"args": [str(x) for x in args], "cwd": str(self.out / "build"),
                   "timeout_seconds": timeout}
        self.save("logs/" + label + "-intent.json", receipt)
        try:
            result = subprocess.run(receipt["args"], cwd=receipt["cwd"], env=self.env,
                                    capture_output=True, timeout=timeout, check=False)
            raw = result.stdout + b"\n--- STDERR ---\n" + result.stderr
            with log.open("xb") as stream:
                stream.write(raw)
            receipt.update(exit_code=result.returncode, log=record(log))
            self.commands.append(receipt)
            self.save("logs/" + label + "-closed.json", receipt)
            require(result.returncode == 0, label + " failed; see " + str(log))
            return result.stdout.decode("utf-8")
        except subprocess.TimeoutExpired as error:
            with log.open("xb") as stream:
                stream.write((error.stdout or b"") + b"\n--- TIMEOUT ---\n" + (error.stderr or b""))
            receipt.update(exit_code=None, timed_out=True, log=record(log))
            self.commands.append(receipt)
            self.save("logs/" + label + "-closed.json", receipt)
            raise

    def build(self):
        cc = shutil.which("gcc")
        require(cc is not None, "host GCC required; do not fall back to firmware/device builds")
        version = self.command("compiler-version", [cc, "--version"])
        exe = IO["checked_output"](self.root, self.out / "build" / (
            "install_workload.exe" if os.name == "nt" else "install_workload"))
        command = [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pipe",
                   *["-I" + str(ROOT / path) for path in INCLUDES],
                   *[str(ROOT / path) for path in SOURCES], "-o", str(exe)]
        self.command("compile", command)
        diagnostics = (self.out / "logs/compile.log").read_text(encoding="utf-8", errors="replace")
        return exe, {"executable": record(exe), "compiler": record(cc),
                     "version": version.splitlines()[0],
                     "warnings": len(re.findall(r"\bwarning:", diagnostics, flags=re.IGNORECASE)),
                     "errors": len(re.findall(r"\berror:", diagnostics, flags=re.IGNORECASE)),
                     "warning_policy": "-Wall -Wextra -Werror"}


def execute(root, out, assets):
    original, inputs = load_assets(assets)
    before = source_records()
    run = Run(root, out)
    result = {"kind": "HOST_INSTALL_WORKLOAD", "hardware": False, "hardware_timing": False,
              "independent_acceptance": False, "assets": original, "inputs": inputs,
              "sources": before, "result": "INCOMPLETE", "cases": []}
    run.save("inputs.json", result)
    try:
        exe, result["build"] = run.build()
        for scenario, block in cases_for(inputs["target"]["bytes"]):
            label = scenario + "-" + str(block)
            raw = run.command(label, [exe, inputs["package"]["path"], inputs["current"]["path"],
                                      inputs["target"]["path"], scenario, str(block)])
            observed = json.loads(raw)
            run.save("results/" + label + ".json", observed)
            validate_result(observed, scenario, block, inputs)
            result["cases"].append(observed)
        require(before == source_records(), "source changed while model was running")
        require(original == record(assets) and inputs == load_assets(assets)[1], "asset drift")
        result.update(result="HOST_MODEL_PASS", native_checks=sum(c["checks"] for c in result["cases"]),
                      source_preservation=True, input_preservation=True)
    except Exception as error:
        result.update(result="HOST_MODEL_FAIL", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        result["commands"] = run.commands
        result["output_paths"] = [str(IO["checked_output"](ROOT, path))
                                  for path in sorted(run.out.rglob("*")) if path.is_file()]
        run.save("result.json", result)
        print(json.dumps({"result": result["result"], "cases": len(result["cases"]),
                          "native_checks": result.get("native_checks"),
                          "report": str(run.out / "result.json")}), flush=True)
    return result


def main():
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "use Python -I -S -B -X utf8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    execute(args.root, args.out, args.assets)


if __name__ == "__main__":
    main()
