"""P3-8 admission using existing owned processes, private ADB and vendor tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Tools/ota/p34-acceptance"))
import live_host as h
from live_phone import Phone
from live_mcu import MCU, REGISTERS, START, SYMBOLS, health_gate, storage_observation


def fingerprint(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def signer(text):
    matches = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})$", text, re.M)
    h.require(len(matches) == 1, "one verified signer required; multiple signers need a separate update decision")
    return matches[0]


def apk_path(text, package):
    h.require(re.fullmatch(r"package:/data/app/[A-Za-z0-9/_.=+~-]+/base\.apk", text), "ambiguous installed APK path")
    h.require("/" + package + "-" in text, "installed path belongs to another package")
    return text[8:]


def close_phone(phone):
    # Let Commander-style owned-process accounting observe ADB's natural exit.
    try:
        if phone.server and phone.server.alive() and h.listening(phone.port):
            h.command(phone.out, "graceful-stop", [phone.base[0], "-H", "127.0.0.1", "-P",
                str(phone.port), "kill-server"], phone.env, seconds=10)
            phone.server.wait(8)
    finally:
        phone.close()


class PassiveMCU(MCU):
    """Only bound savebin reads and one-second sampling gaps, never programming."""
    def execute(self, commands, reads, label, *, seconds=300, deadline=None):
        self.remaining(seconds, deadline)
        h.require(self.logger is None, "do not race a live RTT reader")
        h.require(re.fullmatch(r"[a-z0-9-]+", label), "invalid passive label")
        self.count += 1
        directory = h.fresh(self.out / ("%04d-" % self.count + label))
        self.foreign_debuggers(directory, deadline=deadline)
        paths = {name: h.checked(directory / (name + ".bin")) for name in reads}
        lines = list(START)
        for command in commands:
            if command == "sleep 1000":
                lines.append(command)
                continue
            h.require(isinstance(command, tuple) and len(command) == 3, "passive reads only")
            name, address, size = command
            h.require(name in paths and reads[name] == size and 0 < size <= 0xf0000, "unbound passive read")
            lines.append('savebin "%s", 0x%08X, 0x%X' % (paths[name], address, size))
        lines.append("qc")
        for name in ("commands.jlink", "settings.jlink", "sdk.log"):
            h.checked(directory / name)
        h.raw(directory / "commands.jlink", ("\n".join(lines) + "\n").encode("ascii"))
        console = h.command(directory, "commander", [self.tool("commander"), "-Device", "CORTEX-M4",
            "-If", "SWD", "-Speed", "100", "-USB", str(self.plan["probe_serial"]),
            "-AutoConnect", "0", "-ExitOnError", "1", "-NoGui", "1",
            "-SettingsFile", directory / "settings.jlink", "-Log", directory / "sdk.log",
            "-CommandFile", directory / "commands.jlink"], self.env,
            seconds=self.remaining(seconds, deadline), deadline=deadline)
        data = {}
        for name, size in reads.items():
            h.require(paths[name].is_file() and paths[name].stat().st_size == size, "short/missing passive read")
            data[name] = paths[name].read_bytes()
        return data, console.decode("utf-8", "replace"), directory


def firmware_identity(raw):
    h.require(len(raw) >= 0x460, "short App memory read")
    header = raw[0x400:0x460]
    h.require(header[:4] == b"ETFW" and struct.unpack_from("<I", header, 4)[0] == 1,
              "unknown firmware header")
    h.require(zlib.crc32(header[:92]) == struct.unpack_from("<I", header, 92)[0], "firmware header CRC mismatch")
    length = struct.unpack_from("<I", header, 36)[0]
    h.require(0x460 <= length <= min(len(raw), 0xf0000), "firmware length outside App/read bounds")
    image = raw[:length]
    checked = bytearray(image)
    checked[0x428:0x448] = bytes(32)
    checked[0x45c:0x460] = bytes(4)
    h.require(hashlib.sha256(checked).digest() == header[40:72], "firmware double-zero digest mismatch")
    return dict(version_code=struct.unpack_from("<I", header, 8)[0],
                version_name=header[12:28].split(b"\0", 1)[0].decode("ascii"), bytes=length,
                raw_sha256=hashlib.sha256(image).hexdigest(), header_sha256=header[40:72].hex(),
                hardware_revision=struct.unpack_from("<I", header, 32)[0],
                layout=header[72], min_boot=header[73])


def runtime_observations(data):
    first, last = (struct.unpack("<9I", data[key]) for key in ("health0", "health1"))
    scalar = lambda key: int.from_bytes(data[key], "little")
    return dict(confirmed=data["state"] == b"\x04" and data["confirmed"] == data["snapped"] == b"\x01",
                sd_ready=data["sd"] == b"\x01",
                ota_idle=data["owner"] == data["active"] == data["isr"] == b"\x00",
                fault_free=scalar("vtor") == 0x08010800 and scalar("cfsr") == scalar("hfsr") == 0 and
                not scalar("dhcsr") & 0xa0000 and not scalar("sdio") & 0x3800,
                same_boot_advancing=first[3] == last[3] and first[7:] == last[7:] == (1, 1) and
                last[4] > first[4] and last[5] > first[5], health_samples=[first, last])


def evaluate_state(out, observations):
    # Preserve and reinterpret the original sample; do not repeat the device read.
    directory = Path(observations).resolve(strict=True)
    data = {p.stem: p.read_bytes() for p in directory.glob("*.bin")}
    reference = h.read_json(ROOT / ".cache/p38/reference-001/result.json")
    h.require(reference["result"] == "LEGAL_1MIB_REFERENCE_READY", "checked new fixture required")
    fields = runtime_observations(data)
    storage = storage_observation(data, reference["package"])
    value = dict(result="ORIGINAL_STATE_INTERPRETED_NOT_FORMAL_ACCEPTANCE", formal_acceptance="NOT_RUN",
                 observations=fields, storage=storage,
                 originals=[fingerprint(p) for p in sorted(directory.glob("*.bin"))],
                 prior_gate="P3-4 helper rejected sd_ready=false; original failure retained",
                 sd_scope="SD availability is recorded, not hidden. P3-8 BLE staging and candidate generation use QSPI, not SD.")
    h.save(out / "result.json", value)
    print(json.dumps(dict(observations=fields, storage=storage), indent=2), flush=True)


def inspect_mcu(out, inputs):
    prior = h.read_json(inputs)
    for item in prior["tool_dependencies"]:
        h.pinned(item)
    plan = dict(probe_serial=prior["probe_serial"], tools=prior["tools"])
    h.require(plan["probe_serial"] == "123456", "unexpected selected probe")
    value = dict(scope="read-only current flash/header and core-state admission", formal_acceptance="NOT_RUN",
                 prior_bindings=fingerprint(inputs), no_halt_reset_flash=True)
    h.save(out / "intent.json", value)
    mcu = PassiveMCU(plan, out / "mcu")
    try:
        reads = dict(boot=65536, app_region=0xf0000, header_after=96,
                     **{name: 4 for name in REGISTERS})
        commands = [("boot", 0x08000000, 65536), ("app_region", 0x08010000, 0xf0000),
                    ("header_after", 0x08010400, 96)]
        commands += [(name, address, 4) for name, address in REGISTERS.items()]
        data, _, directory = mcu.execute(commands, reads, "identity")
        value["read_route"] = dict(device="CORTEX-M4", swd_khz=100, maximum_seconds=300)
        h.require(data["app_region"][0x400:0x460] == data["header_after"], "header changed during read")
        value["firmware"] = firmware_identity(data["app_region"])
        value["boot"] = fingerprint(directory / "boot.bin")
        value["boot_matches_prior"] = data["boot"] == h.pinned(prior["boot"]).read_bytes()
        value["registers"] = {name: int.from_bytes(data[name], "little") for name in REGISTERS}
        value["matches_prior_images"] = [name for name, item in prior["images"].items()
                                        if item["image"]["sha256"] == value["firmware"]["raw_sha256"]]
        value["app_image"] = h.raw(out / "current-app.bin", data["app_region"][:value["firmware"]["bytes"]])
        h.require(value["boot_matches_prior"], "Boot differs; reconcile before any mutation")
        h.require(not value["registers"]["dhcsr"] & 0xa0000 and
                  value["registers"]["cfsr"] == value["registers"]["hfsr"] == 0,
                  "halt/fault observed; no automatic reset or recovery")
        value["result"] = "FLASH_IDENTITY_READ_BCB_HEALTH_STILL_PENDING"
    except BaseException as error:
        value.update(result="MCU_ADMISSION_FAILED", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        h.save(out / "result.json", value)
    print(json.dumps(value, indent=2), flush=True)


def inspect_state(out, inputs):
    plan = h.read_json(inputs)
    identity_path = ROOT / ".cache/p38/native-preflight-002/result.json"
    identity = h.read_json(identity_path)
    h.require(identity["result"] == "FLASH_IDENTITY_READ_BCB_HEALTH_STILL_PENDING" and
              identity["matches_prior_images"] == ["target"], "full current flash identity prerequisite")
    value = dict(formal_acceptance="NOT_RUN", full_identity=fingerprint(identity_path))
    h.save(out / "intent.json", value)
    mcu = PassiveMCU(plan, out / "mcu")
    try:
        bound = mcu.bind("target")
        fields = {key: (bound["table"][name][0], 36 if key == "health" else 4 if key == "jedec" else 1)
                  for key, name in SYMBOLS.items() if key not in ("session", "rtt", "main_loop")}
        fields.pop("health")
        session = bound["table"][SYMBOLS["session"]][0]
        fields.update({key: (session + offset, 1) for key, offset in bound["offsets"].items()})
        fields.update({key: (address, 4) for key, address in REGISTERS.items()})
        fields.update(candidate_slot=(0x90000000, 32), backup_slot=(0x90100000, 32),
                      recovery_slot=(0x90200000, 32), staging=(0x90300000, 4096),
                      header_after=(0x08010400, 96), rtt_signature=(bound["rtt"], 16))
        health = bound["table"][SYMBOLS["health"]][0]
        reads = dict(health0=36, health1=36, **{name: size for name, (_, size) in fields.items()})
        commands = [("health0", health, 36), "sleep 1000", ("health1", health, 36)]
        commands += [(name, address, size) for name, (address, size) in fields.items()]
        data, _, directory = mcu.execute(commands, reads, "state", seconds=90)
        h.require(data["header_after"] == bound["image"].read_bytes()[0x400:0x460], "current image header changed")
        h.require(data["rtt_signature"][:10] == b"SEGGER RTT", "RTT signature mismatch")
        value["health"] = health_gate(data)
        value["storage"] = storage_observation(data, plan["package"])
        value.update(result="CURRENT_30287_CONFIRMED_IDLE_READ_ONLY", originals=str(directory), rtt=bound["rtt"])
    except BaseException as error:
        value.update(result="STATE_ADMISSION_FAILED", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        h.save(out / "result.json", value)
    print(json.dumps(value, indent=2), flush=True)


def inspect_apks(out, candidate):
    adb = Path("D:/install/leidian/LDPlayer4/adb.exe")
    key = Path("C:/Users/SU/.android/adbkey")
    java = Path("D:/install/jdk17/bin/java.exe")
    jar = Path("D:/github/my/E-Track/.cache/worktrees/p3-3-admission/.cache/p3-3-apk/tools/android-15/lib/apksigner.jar")
    h.require(fingerprint(adb)["sha256"] == "705ddc21f33ac52105d1b075b019962ad0e44fb3d560bde69ce8cb3a36bca183",
              "ADB executable changed")
    h.require(fingerprint(candidate)["sha256"] == "1ef9cd86b35bd175b238a9c6ce542ce5fb991543fd0470684e82836e025b0f8d",
              "not the reviewed P3-8 standard candidate")
    plan = dict(adb_key=fingerprint(key), adb_port=5078, phone_serial="10ADA4197U001CK",
                phone_model="V2312A", app_id="com.wen.gaia.gaia", tools=dict(adb=fingerprint(adb)))
    value = dict(scope="read-only signer/install admission", formal_acceptance="NOT_RUN",
                 candidate=fingerprint(candidate), java=fingerprint(java), apksigner=fingerprint(jar))
    h.save(out / "intent.json", value)
    phone = Phone(plan, out / "usb", 300)
    env = h.environment(out)
    for name in ("JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS"):
        env.pop(name, None)
    try:
        phone.start(verify_apk=False)
        h.require(phone.cmd(["shell", "am", "get-current-user"]).strip() == b"0", "wrong Android user")
        path = apk_path(phone.cmd(["shell", "pm", "path", plan["app_id"]]).decode().strip(), plan["app_id"])
        size = int(phone.cmd(["shell", "stat", "-c", "%s", path]).strip())
        h.require(0 < size <= 192 * 1024 * 1024, "installed APK size bound")
        expected = phone.cmd(["shell", "sha256sum", path]).decode().split()[0]
        data = phone.cmd(["exec-out", "cat", path], seconds=90)
        h.require(len(data) == size and hashlib.sha256(data).hexdigest() == expected, "installed APK readback mismatch")
        installed = phone.out / ("adb-%05d.stdout" % phone.count)
        value["installed"] = fingerprint(installed)
        value["device_path"] = path
        for label, source in (("installed", installed), ("candidate", candidate)):
            output = h.command(out, "verify-" + label, [java, "-XX:-UsePerfData",
                "-Djava.io.tmpdir=" + env["TEMP"], "-Duser.home=" + env["HOME"],
                "-jar", jar, "verify", "--verbose", "--print-certs", source], env, seconds=45)
            value[label + "_signer_sha256"] = signer(output.decode("utf-8").replace("\r\n", "\n"))
        value["same_signer"] = value["installed_signer_sha256"] == value["candidate_signer_sha256"]
        value["result"] = "SIGNERS_MATCH_NO_INSTALL" if value["same_signer"] else "SIGNERS_DIFFER_NO_INSTALL"
    except BaseException as error:
        value.update(result="ADMISSION_FAILED", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        try:
            close_phone(phone)
            value["usb_closed"] = True
        finally:
            value["adb_key_unchanged"] = fingerprint(key) == plan["adb_key"]
            h.save(out / "result.json", value)
    h.require(value["adb_key_unchanged"], "read-only ADB key changed")
    print(json.dumps(value, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect-apks", "inspect-mcu", "inspect-state", "evaluate-state"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--prior-inputs", type=Path)
    parser.add_argument("--observations", type=Path)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "explicit acceptance worktree and isolated Python required")
    out = h.checked(args.out)
    for leaf in ("intent.json", "result.json", "usb", "host"):
        h.checked(out / leaf)
    required = args.candidate if args.action == "inspect-apks" else args.observations if args.action == "evaluate-state" else args.prior_inputs
    h.require(required is not None,
              "exact candidate/prior input required")
    h.fresh(out)
    if args.action == "inspect-apks":
        inspect_apks(out, args.candidate)
    elif args.action == "inspect-mcu":
        inspect_mcu(out, args.prior_inputs)
    elif args.action == "inspect-state":
        inspect_state(out, args.prior_inputs)
    else:
        evaluate_state(out, args.observations)


if __name__ == "__main__":
    main()
