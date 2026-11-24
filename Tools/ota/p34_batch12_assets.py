"""Two legal header-only successors; batch3 control then batch12 on one APK."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_probe_cadence as prior

cli, ui = prior.cli, prior.ui
AREA = ROOT / ".cache/p34-batch12"
OUT = AREA / "assets"
PRIOR = prior.AREA / "trial-dns"
MATRIX = (("control", 30258, 3), ("batch12", 30259, 12))


def prepare(s):
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    report = ui.archival.proof(s, PRIOR)
    old = prior.assets(s)
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30257 and
                report["summary"]["input"]["targetImageSha256"] == old["target"]["sha256"], "wrong predecessor")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    inputs = [cli.record(PRIOR / "analysis/latest.json"), report["after"],
              cli.record(prior.ASSETS / "result.json"), cli.record(__file__), decoder,
              old["target"], old["target_bindings"]["whole_boot"]]
    for item in inputs:
        cli.require(cli.record(s.checked(item["path"])) == item, "asset input changed")
    host = ui.screen.host
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("batch12_pack", ui.AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("batch12_unpack", ui.AREA / "f/Tools/etu_unpack.py")
    tools = cli.load_module("batch12_negatives", ROOT / "Tools/ota/prepare_baud_assets.py")
    shared = prior.previous.profile.assets_api.ui.shared
    receiver, bindings, groups = old["target"], old["target_bindings"], {}
    for name, version, frames in MATRIX:
        before = Path(receiver["path"]).read_bytes()
        raw = bytearray(before)
        label = f"3.2.{version-30200}-p34p"
        raw[0x400:0x460] = pack.build_fw_header(bytes(raw), label, 1786320000)
        cli.require(before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:], "executable changed")
        target = s.raw(OUT / (name + ".bin"), bytes(raw))
        identity = shared.identity(bytes(raw), unpack)
        cli.require(identity["version_code"] == version, "target version differs")
        blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
        served = "p34-batch12-" + name + "-full.etu"
        package = s.raw(OUT / served, blob)
        def native(label, item, expected):
            return json.loads(host.command(s, OUT, name + "-" + label,
                [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
        decoded = native("positive", package, "ok")
        cli.require(all(decoded[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                    "native positive failed")
        negatives = []
        for negative, broken, expected in tools.negatives(blob, version - 1):
            item = s.raw(OUT / (name + "-" + negative + ".etu"), broken)
            checked = native(negative, item, expected)
            cli.require(checked["passed"] and checked["prepares"] == 0, "negative reached preparation")
            negatives.append(dict(name=negative, package=item, native=checked))
        target_bindings = copy.deepcopy(bindings)
        target_bindings["profile"].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
        groups[name] = dict(specification=dict(receiver=version-1, target_version=version,
            version_name=label, served_name=served, release_key="p34-batch12-" + name, kind="full",
            pauseScanDuringOta=True, androidHighPriority=True, dataBatchFrames=frames,
            reuseRebootInfoLink=True, rebootProbeIntervalMs=500),
            receiver=receiver, receiver_bindings=bindings, target=target, target_identity=identity,
            target_bindings=target_bindings, package=package, package_kind="full", decoded=decoded, negatives=negatives)
        receiver, bindings = target, target_bindings
    s.write(OUT / "result.json", dict(result="BATCH12_ASSETS_VERIFIED", hardware=False,
        groups=groups, inputs=inputs, scope="two sequential header-only FULL cells; same APK; not identical-package A/B"))
    print("BATCH12_ASSETS_VERIFIED", {k: v["package"]["bytes"] for k, v in groups.items()}, flush=True)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact mode required")
    s = cli.Store(ROOT)
    owner = cli.load_module("batch12_assets_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        s.checked(OUT)
        print(owner.owned.launch(s.checked(AREA / "runtime/assets-001"), Path(__file__), ["worker"], 900))
    else:
        cli.require(owner.owned.in_job(), "finite asset owner required")
        prepare(s)
