"""Legal 30228 -> 30229 -> 30230 receive-restore screening assets."""
import argparse
import json
from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_session as cli

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-receive-screen"
RELATIVE = ".cache/p34-receive-screen/assets/result.json"
BUILD_REPORT = ".cache/p34sr/evidence/build.json"
ADMISSION = AREA / "input-admission.json"
RECEIVER = AREA / "receiver.json"


def verified_build(*, sources=False):
    store = cli.Store(ROOT)
    build = store.read(ROOT / BUILD_REPORT)
    cli.require(build["result"] == "RECEIVE_APP_BUILD_PASS" and build["errors"] == 0 and
                build["qe_reuse"] is True and build["boot_built"] is False and
                build["finalized"] is False and build["staging_context_bytes"] == 16,
                "verified receive-restore candidate required")
    records = [build["source"], *build["artifacts"], *build["commands"]]
    source = store.read(build["source"]["path"])
    cli.require(source["overlay"] == ["USER/HAL/HAL_OTA_Staging.cpp"] and
                Path(source["fw"]) == ROOT / ".cache/p34sr/f", "candidate source scope differs")
    if sources:
        records += source["inputs"] + source["originals"] + source["files"]
    for item in records:
        cli.require(cli.record(store.checked(item["path"])) == {key: item[key] for key in
                    ("path", "bytes", "sha256")}, "candidate input changed: " + item["path"])
    return source


def verify_admission(store):
    value = store.read(ADMISSION)
    cli.require(value["result"] == "RECEIVE_INPUTS_ADMITTED" and
                value["versions"] == [30229, 30230] and value["receiver_version"] == 30228,
                "receive preparation admission changed")
    previous = cli.completed_full_predecessor(store, value["predecessor"], group="patch32-pressure")
    for key in ("receiver", "old_assets", "build"):
        cli.require(cli.record(store.checked(value[key]["path"])) == value[key], "receive admission input changed")
    receiver = store.read(RECEIVER)
    old = store.read(value["old_assets"]["path"])["images"]["ab"]
    cli.require(receiver == dict(target=old["image"], target_identity=old["identity"],
                                target_bindings=old["bindings"]) and
                previous["plan"]["target_bindings"] == receiver["target_bindings"],
                "receive candidate does not follow the actual verified30228")
    verified_build()
    return value


def engine():
    api = cli.load_module("p34_receive_asset_engine", ROOT / "Tools/ota/p34_patch_assets.py")
    api.prep = types.SimpleNamespace(**dict(vars(api.prep), AA=30229, AB=30230,
        AA_NAME="3.2.29-p34r", AB_NAME="3.2.30-p34r", Y_ASSETS=RECEIVER,
        FW=ROOT / ".cache/p34sr/f", verify_source=lambda: verified_build(sources=True)))
    api.OUT = AREA / "assets"
    api.FIRMWARE = ROOT / ".cache/p34sr/evidence"
    api.RELATIVE, api.BUILD_REPORT = RELATIVE, BUILD_REPORT
    api.EXPECTED_BUILD_RESULT, api.EXPECTED_BUILD_FEATURE = "RECEIVE_APP_BUILD_PASS", "qe_reuse"
    api.SEARCH_BUDGET = 512
    api.EXTRA_INPUTS = (Path(__file__), ADMISSION)
    return api


def load():
    verify_admission(cli.Store(ROOT))
    return engine().load()


def load_for_context(c, specification):
    cli.require(specification in cli.RECEIVE_GROUPS.values(), "not an explicit receive-restore cell")
    verify_admission(cli.Store(ROOT))
    return engine().load_for_context(c, specification)


def prepare(store):
    with store.command_lock():
        if (ROOT / RELATIVE).exists():
            return dict(result=load()["result"], reused=True, device_operations=0)
        cli.require(not ADMISSION.exists() and not RECEIVER.exists() and not (AREA / "assets").exists(),
                    "preserve partial receive assets and nonces")
        source = verified_build(sources=True)
        run = store.current()
        cli.require(run, "actual completed30228 required")
        previous = cli.completed_full_predecessor(store, cli.current_full_descriptor(store, run), group="patch32-pressure")
        old_path = ROOT / ".cache/p34-patch32/assets/result.json"
        old = cli.patch_assets_api(store, "patch32-pressure").load()["images"]["ab"]
        cli.require(old["identity"]["version_code"] == 30228 and
                    previous["plan"]["target_bindings"] == old["bindings"], "retained receiver differs")
        for path in (ADMISSION, RECEIVER, AREA / "assets", AREA / "assets/host"):
            store.checked(path)
        store.write(RECEIVER, dict(target=old["image"], target_identity=old["identity"], target_bindings=old["bindings"]))
        store.write(ADMISSION, dict(result="RECEIVE_INPUTS_ADMITTED", time=cli.now(),
            predecessor=previous["descriptor"], receiver=cli.record(RECEIVER), old_assets=cli.record(old_path),
            build=cli.record(ROOT / BUILD_REPORT), receiver_version=30228, versions=[30229, 30230],
            device_operations=0, unchanged_boot=True, formal_reference_admitted=False))
        result = engine().prepare()
        load()
        return dict(result, manifest=cli.record(ROOT / RELATIVE), device_operations=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    cli.require(args.root == ROOT == Path.cwd() and sys.flags.isolated and
                sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit project root required")
    print(json.dumps(prepare(cli.Store(ROOT)) if args.action == "prepare" else
                     dict(result=load()["result"], verified=True)), flush=True)
