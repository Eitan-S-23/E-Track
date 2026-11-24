"""One header-only batch12 interaction cell on the verified active-pump receiver."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_pump_trial as previous
import p34_batch_review as review

cli, batch, ui = previous.cli, previous.batch, previous.ui
AREA = ROOT / ".cache/p34-pump-batch12"
OUT, PRIOR, ORDER = AREA / "assets", previous.TRIALS / "measure", ("measure",)


def prepare(s):
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    anchor, report = review.load_report(s, PRIOR)
    old = previous.assets(s, "measure")
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30263 and
                report["summary"]["input"]["targetImageSha256"] == old["target"]["sha256"], "wrong receiver")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    pack_path = previous.AREA / "f/Tools/etu_pack.py"
    unpack_path = previous.AREA / "f/Tools/etu_unpack.py"
    inputs = [anchor, report["after"], cli.record(previous.asset_api.OUT / "result.json"),
              cli.record(__file__), decoder, old["target"], old["target_bindings"]["whole_boot"],
              cli.record(pack_path), cli.record(unpack_path)]
    for item in inputs:
        cli.require(cli.record(s.checked(item["path"])) == item, "asset input changed")
    for name in ("measure.bin", "p34-pump-batch12-full.etu", "result.json", "host"):
        s.checked(OUT / name)
    for tag in ("positive", "payload-crc", "truncated", "same-version", "wrong-flags"):
        for suffix in (".etu", ".log", ".json"):
            s.checked(OUT / ("measure-" + tag + suffix))
    host = previous.asset_api.host
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("pump_batch_pack", pack_path)
    unpack = cli.load_module("pump_batch_unpack", unpack_path)
    tools = cli.load_module("pump_batch_negatives", ROOT / "Tools/ota/prepare_baud_assets.py")
    shared = previous.asset_api.shared
    receiver, bindings = old["target"], old["target_bindings"]
    before = Path(receiver["path"]).read_bytes()
    raw = bytearray(before)
    raw[0x400:0x460] = pack.build_fw_header(bytes(raw), "3.2.64-p34p", 1786320000)
    cli.require(before != raw and before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:],
                "header successor changed executable")
    target = s.raw(OUT / "measure.bin", bytes(raw))
    identity = shared.identity(bytes(raw), unpack)
    cli.require(identity["version_code"] == 30264, "wrong successor version")
    blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
    package = s.raw(OUT / "p34-pump-batch12-full.etu", blob)

    def native(tag, item, expected):
        return json.loads(host.command(s, OUT, "measure-" + tag,
            [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))

    decoded = native("positive", package, "ok")
    cli.require(all(decoded[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                "positive native decode failed")
    negatives = []
    for tag, broken, expected in tools.negatives(blob, 30263):
        item = s.raw(OUT / ("measure-" + tag + ".etu"), broken)
        checked = native(tag, item, expected)
        cli.require(checked["passed"] and checked["prepares"] == 0, "negative reached preparation")
        negatives.append(dict(name=tag, package=item, native=checked))
    target_bindings = copy.deepcopy(bindings)
    target_bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
    group = dict(specification=dict(receiver=30263, target_version=30264, version_name="3.2.64-p34p",
        served_name="p34-pump-batch12-full.etu", release_key="p34-pump-batch12-measure", kind="full",
        pauseScanDuringOta=True, androidHighPriority=True, dataBatchFrames=12,
        reuseRebootInfoLink=True, rebootProbeIntervalMs=500),
        receiver=receiver, receiver_bindings=bindings, target=target, target_identity=identity,
        target_bindings=target_bindings, package=package, package_kind="full", decoded=decoded, negatives=negatives)
    s.write(OUT / "result.json", dict(result="PUMP_BATCH_ASSETS_VERIFIED", hardware=False,
        groups=dict(measure=group), inputs=inputs, no_build=True,
        scope="One header-only successor; batch12 interaction, no repeated control/Boot/APK change"))
    print("PUMP_BATCH_ASSETS_VERIFIED", package["bytes"], package["sha256"], flush=True)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact mode required")
    s = cli.Store(ROOT)
    owner = cli.load_module("pump_batch_assets_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        s.checked(OUT)
        print(owner.owned.launch(s.checked(AREA / "runtime/assets-001"), Path(__file__), ["worker"], 900))
    else:
        cli.require(owner.owned.in_job(), "finite asset owner required")
        prepare(s)
