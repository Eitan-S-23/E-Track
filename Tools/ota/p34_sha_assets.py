"""Prepare two legal SHA candidate successors using the verified native decoder."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_sha_candidate as build
import p34_timed_ack_trial as previous
import p34_patch_assets as shared

cli, host, AREA = build.cli, build.host, build.AREA
OUT, PRIOR, ORDER = AREA / "assets", previous.TRIALS / "measure", ("bootstrap", "measure")


def prepare(s):
    cli.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    for name in ORDER:
        for leaf in (name + ".bin", "p34-sha-" + name + "-full.etu"):
            s.checked(OUT / leaf)
        for tag in ("positive", "payload-crc", "truncated", "same-version", "wrong-flags"):
            for suffix in (".etu", ".log", ".json"): s.checked(OUT / (name + "-" + tag + suffix))
    s.checked(OUT / "result.json")
    anchor, report = previous.old.old.review.load_report(s, PRIOR)
    current = previous.assets(s, "measure")
    cli.require(report["summary"]["input"]["targetVersionCode"] == 30273 and
                report["summary"]["input"]["targetImageSha256"] == current["target"]["sha256"],
                "confirmed30273 predecessor required")
    build.verify(s)
    built, receipt = s.read(AREA / "build/result.json"), s.read(AREA / "build/build.json")
    cli.require(built["result"] == "SHA_APP_CANDIDATE_BUILT" and not built["new_warnings"] and
                built["errors"] == 0 and not built["boot_built"] and receipt["exit"] == 0,
                "successful App-only build required")
    artifacts = {Path(x["path"]).suffix: x for x in built["artifacts"]}
    inputs = [anchor, cli.record(AREA / "build/result.json"), built["source"], *built["artifacts"],
              cli.record(__file__), cli.record(build.__file__),
              cli.record(ROOT / ".cache/p34-sha-screen/r1/result.json"),
              cli.record(previous.AREA / "assets/result.json")]
    for item in inputs + s.read(built["source"]["path"])["files"]:
        cli.require(cli.record(s.checked(item["path"])) == item, "built input changed")
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("sha_candidate_pack", AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("sha_candidate_unpack", AREA / "f/Tools/etu_unpack.py")
    tools = cli.load_module("sha_candidate_negatives", ROOT / "Tools/ota/prepare_baud_assets.py")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    cli.require(cli.record(s.checked(decoder["path"])) == decoder, "decoder changed")
    constants = s.read(ROOT / ".cache/p34ab/assets/session-assets.json")["constants"]
    receiver, bindings, groups = current["target"], current["target_bindings"], {}
    for name, version in zip(ORDER, (30274, 30275)):
        raw = bytearray(Path(artifacts[".bin"]["path"]).read_bytes())
        label = "3.2.%d-p34p" % (version - 30200)
        raw[0x400:0x460] = pack.build_fw_header(bytes(raw), label, 1786320000)
        target = s.raw(OUT / (name + ".bin"), bytes(raw))
        identity = shared.identity(bytes(raw), unpack)
        cli.require(identity["version_code"] == version, "wrong target version")
        before = Path(receiver["path"]).read_bytes()
        blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind="full")
        served = "p34-sha-" + name + "-full.etu"
        package = s.raw(OUT / served, blob)
        def native(tag, item, expected):
            return json.loads(host.command(s, OUT, name + "-" + tag,
                [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
        decoded = native("positive", package, "ok")
        cli.require(all(decoded[k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                    "native decode failed")
        negatives = []
        for tag, broken, expected in tools.negatives(blob, version - 1):
            item = s.raw(OUT / (name + "-" + tag + ".etu"), broken)
            result = native(tag, item, expected)
            cli.require(result["passed"] and result["prepares"] == 0, "negative reached preparation")
            negatives.append(dict(name=tag, package=item, native=result))
        target_bindings = shared.bindings(dict(target_bindings=bindings), target, identity, artifacts, constants)
        cli.require(target_bindings["whole_boot"] == current["target_bindings"]["whole_boot"], "Boot changed")
        groups[name] = dict(specification=dict(current["specification"], receiver=version - 1,
            target_version=version, version_name=label, served_name=served, release_key="p34-sha-" + name),
            receiver=receiver, receiver_bindings=bindings, target=target, target_identity=identity,
            target_bindings=target_bindings, package=package, package_kind="full", decoded=decoded, negatives=negatives)
        receiver, bindings = target, copy.deepcopy(target_bindings)
    a, b = [Path(groups[k]["target"]["path"]).read_bytes() for k in ORDER]
    cli.require(a[:0x400] + a[0x460:] == b[:0x400] + b[0x460:], "measurement executable changed")
    s.write(OUT / "result.json", dict(result="SHA_ASSETS_VERIFIED", groups=groups,
        inputs=inputs + [decoder], hardware=False,
        scope="App SHA compiler optimization only; bootstrap then same-executable successor; no speed claim"))
    print("SHA_ASSETS_VERIFIED", {k: v["package"]["bytes"] for k, v in groups.items()})


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit isolated root required")
    prepare(cli.Store(ROOT))
