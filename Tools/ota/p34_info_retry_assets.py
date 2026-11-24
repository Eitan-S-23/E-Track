"""Prepare two executable-identical legal header successors; no build/device I/O."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_info_timeout as prior

cli = prior.cli
OUT = ROOT / ".cache/p34-info-retry/assets"


def prepare(s):
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve asset attempt/no key override")
    for arm in ("control", "extended"):
        base = OUT / arm
        for name in ["target.bin", "package.etu", "result.json", "host"] + [x + suffix
            for x in ("positive", "payload-crc", "truncated", "same-version", "wrong-flags")
            for suffix in (".etu", ".log", ".json")]: s.checked(base / name)
        for key in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir",
                    "xdg_cache_home", "xdg_config_home", "xdg_data_home", "pythonuserbase",
                    "pythonpycacheprefix", "ccache_dir", "sccache_dir"): s.checked(base / "host" / key)
    s.checked(OUT / "result.json")
    pointer, report = prior.review.load_report(s, prior.OUT)
    group = prior.assets(s)
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30269 and
        report["summary"]["input"]["targetImageSha256"] == group["target"]["sha256"], "wrong retained receiver")
    host, shared = prior.phy.previous.asset_api.host, prior.phy.previous.asset_api.shared
    pack_path = prior.phy.previous.AREA / "f/Tools/etu_pack.py"
    unpack_path = prior.phy.previous.AREA / "f/Tools/etu_unpack.py"
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    inputs = [pointer, report["after"], cli.record(prior.ASSETS / "result.json"), decoder,
              cli.record(pack_path), cli.record(unpack_path), group["target"], group["target_bindings"]["whole_boot"]]
    for item in inputs: cli.require(cli.record(s.checked(item["path"])) == item, "asset input changed")
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("info_retry_pack", pack_path)
    unpack = cli.load_module("info_retry_unpack", unpack_path)
    tools = cli.load_module("info_retry_negatives", ROOT / "Tools/ota/prepare_baud_assets.py")
    receiver, bindings, groups = group["target"], group["target_bindings"], {}
    for arm, version, attempts in (("control", 30270, 3), ("extended", 30271, 12)):
        base = OUT / arm
        env = host.environment(s, base)
        os.environ.update(env)
        before = Path(receiver["path"]).read_bytes()
        raw = bytearray(before)
        name = "3.2.%d-p34p" % (version - 30200)
        raw[0x400:0x460] = pack.build_fw_header(bytes(raw), name, 1786320000)
        cli.require(before != raw and before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:], "executable changed")
        target = s.raw(base / "target.bin", bytes(raw))
        identity = shared.identity(bytes(raw), unpack)
        cli.require(identity["version_code"] == version, "wrong header successor")
        blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
        package = s.raw(base / "package.etu", blob)
        def native(label, item, expected):
            return json.loads(host.command(s, base, label,
                [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
        decoded = native("positive", package, "ok")
        cli.require(all(decoded[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                    "native positive decode failed")
        negatives = []
        for label, broken, expected in tools.negatives(blob, version - 1):
            item = s.raw(base / (label + ".etu"), broken)
            result = native(label, item, expected)
            cli.require(result["passed"] and result["prepares"] == 0, "invalid package reached preparation")
            negatives.append(dict(name=label, package=item, native=result))
        target_bindings = copy.deepcopy(bindings)
        target_bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
        spec = dict(group["specification"], receiver=version - 1, target_version=version,
            version_name=name, served_name="p34-info-retry-" + arm + ".etu", release_key="p34-info-retry-" + arm,
            rebootInfoTimeoutMs=1000, rebootInfoMaxAttempts=attempts)
        groups[arm] = dict(specification=spec, receiver=receiver, receiver_bindings=bindings,
            target=target, target_identity=identity, target_bindings=target_bindings,
            package=package, package_kind="full", decoded=decoded, negatives=negatives)
        s.write(base / "result.json", groups[arm])
        receiver, bindings = target, target_bindings
        print("HEADER_SUCCESSOR_VERIFIED", arm, version, package["bytes"], package["sha256"], flush=True)
    s.write(OUT / "result.json", dict(result="INFO_RETRY_ASSETS_VERIFIED", groups=groups, inputs=inputs,
        source=cli.record(__file__), no_build=True, executable_changed=False, hardware=False))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated project root required")
    prepare(cli.Store(ROOT))
