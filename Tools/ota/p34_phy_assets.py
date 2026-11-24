"""Two header-only full packages for observe/prefer2m, with unchanged MCU code."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_half_erase_trial as previous
import p34_batch_review as review

cli = previous.cli
AREA = ROOT / ".cache/p34-phy"
OUT = AREA / "assets"
PRIOR = previous.TRIALS / "measure"
ORDER = ("observe", "prefer2m")


def prepare(s):
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    anchor, report = review.load_report(s, PRIOR)
    old = previous.assets(s, "measure")
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30266 and
        report["summary"]["input"]["targetImageSha256"] == old["target"]["sha256"], "wrong receiver")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    pack_path = previous.AREA / "f/Tools/etu_pack.py"
    unpack_path = previous.AREA / "f/Tools/etu_unpack.py"
    inputs = [anchor, report["after"], cli.record(previous.asset_api.OUT / "result.json"),
        cli.record(__file__), decoder, old["target"], old["target_bindings"]["whole_boot"],
        cli.record(pack_path), cli.record(unpack_path)]
    for item in inputs:
        cli.require(cli.record(s.checked(item["path"])) == item, "asset input changed")
    for arm in ORDER:
        for name in (arm + ".bin", "p34-phy-" + arm + "-full.etu", "result.json", "host"):
            s.checked(OUT / name)
        for tag in ("positive", "payload-crc", "truncated", "same-version", "wrong-flags"):
            for suffix in (".etu", ".log", ".json"):
                s.checked(OUT / (arm + "-" + tag + suffix))
    host, shared = previous.asset_api.host, previous.asset_api.shared
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("phy_pack", pack_path)
    unpack = cli.load_module("phy_unpack", unpack_path)
    tools = cli.load_module("phy_negatives", ROOT / "Tools/ota/prepare_baud_assets.py")
    receiver, bindings, groups = old["target"], old["target_bindings"], {}
    for arm, version in zip(ORDER, (30267, 30268)):
        before = Path(receiver["path"]).read_bytes()
        raw = bytearray(before)
        label = "3.2.%d-p34p" % (version - 30200)
        raw[0x400:0x460] = pack.build_fw_header(bytes(raw), label, 1786320000)
        cli.require(before != raw and before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:],
                    "header successor changed executable")
        target = s.raw(OUT / (arm + ".bin"), bytes(raw))
        identity = shared.identity(bytes(raw), unpack)
        cli.require(identity["version_code"] == version, "wrong successor version")
        blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
        served = "p34-phy-" + arm + "-full.etu"
        package = s.raw(OUT / served, blob)
        def native(tag, item, expected):
            return json.loads(host.command(s, OUT, arm + "-" + tag,
                [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
        decoded = native("positive", package, "ok")
        cli.require(all(decoded[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                    "positive native decode failed")
        negatives = []
        for tag, broken, expected in tools.negatives(blob, version - 1):
            item = s.raw(OUT / (arm + "-" + tag + ".etu"), broken)
            result = native(tag, item, expected)
            cli.require(result["passed"] and result["prepares"] == 0, "negative reached preparation")
            negatives.append(dict(name=tag, package=item, native=result))
        target_bindings = copy.deepcopy(bindings)
        target_bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
        groups[arm] = dict(specification=dict(receiver=version - 1, target_version=version, version_name=label,
            served_name=served, release_key="p34-phy-" + arm, kind="full", pauseScanDuringOta=True,
            androidHighPriority=True, dataBatchFrames=12, reuseRebootInfoLink=True,
            rebootProbeIntervalMs=500, androidPhyPolicy=arm), receiver=receiver,
            receiver_bindings=bindings, target=target, target_identity=identity, target_bindings=target_bindings,
            package=package, package_kind="full", decoded=decoded, negatives=negatives)
        receiver, bindings = target, target_bindings
    s.write(OUT / "result.json", dict(result="PHY_ASSETS_VERIFIED", hardware=False,
        groups=groups, inputs=inputs, no_build=True, executable_changed=False,
        scope="two header-only sequential screening cells; no Boot replacement or current-firmware mutation"))
    print("PHY_ASSETS_VERIFIED", {name: g["package"]["bytes"] for name, g in groups.items()}, flush=True)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact asset mode required")
    s = cli.Store(ROOT)
    owner = cli.load_module("phy_assets_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        s.checked(OUT)
        print(owner.owned.launch(s.checked(AREA / "runtime/assets-001"), Path(__file__), ["worker"], 900))
    else:
        cli.require(owner.owned.in_job(), "finite asset owner required")
        prepare(s)
