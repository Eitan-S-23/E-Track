"""Prepare the 32KiB erase bootstrap and executable-identical measurement packages."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_half_erase_candidate as build
import p34_pump_batch_trial as previous
import p34_batch_review as review

cli, batch, ui = previous.cli, previous.batch, previous.ui
host, shared = build.host, previous.previous.asset_api.shared
AREA, OUT = build.AREA, build.AREA / "assets"
PRIOR, ORDER = previous.TRIALS / "measure", ("bootstrap", "measure")


def prepare(s):
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    anchor, report = review.load_report(s, PRIOR)
    current = previous.assets(s, "measure")
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30264 and
                report["summary"]["input"]["targetImageSha256"] == current["target"]["sha256"], "wrong predecessor")
    built = s.read(AREA / "build/result.json")
    owner = s.read(AREA / "runtime/build-001/closed.json")
    cli.require(built["result"] == "HALF_ERASE_APP_BUILT" and not built["new_warnings"] and
                built["errors"] == 0 and not built["boot_built"] and owner["worker_exit"] == 0 and
                not owner["forced_termination"], "verified App-only build required")
    artifacts = {Path(x["path"]).suffix: x for x in built["artifacts"]}
    inputs = [anchor, cli.record(AREA / "build/result.json"), built["source"], built["tests"], *built["artifacts"],
              cli.record(__file__), cli.record(previous.asset_api.OUT / "result.json"),
              cli.record(ROOT / "Tools/ota/p34_half_erase.patch")]
    for item in inputs:
        cli.require(cli.record(s.checked(item["path"])) == item, "input changed")
    for item in s.read(built["source"]["path"])["files"]:
        cli.require(cli.record(s.checked(item["path"])) == item, "built source changed")
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("half_erase_pack", AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("half_erase_unpack", AREA / "f/Tools/etu_unpack.py")
    tools = cli.load_module("half_erase_negatives", ROOT / "Tools/ota/prepare_baud_assets.py")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    cli.require(cli.record(s.checked(decoder["path"])) == decoder, "decoder changed")
    constants = s.read(ROOT / ".cache/p34ab/assets/session-assets.json")["constants"]
    receiver, bindings, groups = current["target"], current["target_bindings"], {}
    for name, version in zip(ORDER, (30265, 30266)):
        raw = bytearray(Path(artifacts[".bin"]["path"]).read_bytes())
        label = f"3.2.{version-30200}-p34p"
        raw[0x400:0x460] = pack.build_fw_header(bytes(raw), label, 1786320000)
        target = s.raw(OUT / (name + ".bin"), bytes(raw))
        identity = shared.identity(bytes(raw), unpack)
        cli.require(identity["version_code"] == version, "wrong target version")
        before = Path(receiver["path"]).read_bytes()
        blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
        served = "p34-half-erase-" + name + "-full.etu"
        package = s.raw(OUT / served, blob)
        def native(tag, item, expected):
            return json.loads(host.command(s, OUT, name + "-" + tag,
                [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
        decoded = native("positive", package, "ok")
        cli.require(all(decoded[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                    "positive native decode failed")
        negatives = []
        for tag, broken, expected in tools.negatives(blob, version-1):
            item = s.raw(OUT / (name + "-" + tag + ".etu"), broken)
            result = native(tag, item, expected)
            cli.require(result["passed"] and result["prepares"] == 0, "negative reached preparation")
            negatives.append(dict(name=tag, package=item, native=result))
        target_bindings = shared.bindings(dict(target_bindings=bindings), target, identity, artifacts, constants)
        cli.require(target_bindings["whole_boot"] == current["target_bindings"]["whole_boot"], "Boot changed")
        groups[name] = dict(specification=dict(receiver=version-1, target_version=version, version_name=label,
            served_name=served, release_key="p34-half-erase-" + name, kind="full", pauseScanDuringOta=True,
            androidHighPriority=True, dataBatchFrames=12, reuseRebootInfoLink=True, rebootProbeIntervalMs=500),
            receiver=receiver, receiver_bindings=bindings, target=target, target_identity=identity,
            target_bindings=target_bindings, package=package, package_kind="full", decoded=decoded, negatives=negatives)
        receiver, bindings = target, copy.deepcopy(target_bindings)
    a, b = [Path(groups[k]["target"]["path"]).read_bytes() for k in ORDER]
    cli.require(a[:0x400] + a[0x460:] == b[:0x400] + b[0x460:], "measurement executable changed")
    s.write(OUT / "result.json", dict(result="HALF_ERASE_ASSETS_VERIFIED", groups=groups, inputs=inputs+[decoder],
        hardware=False, scope="bootstrap installs optional32KiB payload erase; successor measures installation"))
    print("HALF_ERASE_ASSETS_VERIFIED", {k: v["package"]["bytes"] for k, v in groups.items()})


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact asset mode required")
    s = cli.Store(ROOT)
    owner = cli.load_module("half_erase_asset_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        s.checked(OUT)
        print(owner.owned.launch(s.checked(AREA / "runtime/assets-001"), Path(__file__), ["worker"], 900))
    else:
        cli.require(owner.owned.in_job(), "finite asset owner required")
        prepare(s)
