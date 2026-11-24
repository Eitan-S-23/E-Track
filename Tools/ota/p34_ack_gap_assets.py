"""Verified host-only ACK-gap package view for the existing OTA session runner."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_session as cli
import p34_patch_assets as shared

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = ".cache/p34ag/assets/session-assets.json"
BUILD_REPORT = ".cache/p34ag/build.json"
GROUP = "ack-gap-bootstrap"


def diagnostic_package():
    store = cli.Store(ROOT)
    assets = store.read(ROOT / ".cache/p34-target50/assets/result.json")
    session = ROOT / ".cache/p34-target50/session-serial-w1"
    result = store.read(session / "result.json")
    closure = store.read(session / "mcu/closure.json")
    owner = store.read(session / "owner/closed.json")
    package = assets["package"]
    cli.require(package["sha256"] == "422d216a4177230905330256a20e406f10247e22f61199288d30225396e9521f" and
                cli.record(store.checked(package["path"])) == package and
                result["result"] == "CAPACITY_SCREEN_VERIFIED" and result["no_install"] is True and
                closure["retained_verified"] is True and closure["reader_closed"] is True and
                owner["worker_exit"] == 0 and owner["forced_termination"] is False,
                "diagnostic staging origin unresolved")
    cli.require(closure["final_state"]["session"]["durable_off"] == 0 and
                closure["final_state"]["session"]["package_sha256"] == package["sha256"],
                "diagnostic journal is not the verified noncommitted package")
    return package


def load():
    store = cli.Store(ROOT)
    value = store.read(ROOT / RELATIVE)
    cli.require(value["result"] == "ACK_GAP_ASSETS_VERIFIED" and value["hardware"] is False,
                "ACK-gap assets not host-verified")
    for item in value["inputs"]:
        cli.require(cli.record(store.checked(item["path"])) == item, "ACK-gap input changed: " + item["path"])
    group = value["groups"]["bootstrap"]
    image = value["images"]["aa"]
    cli.require(group["package"] == value["package"] and group["target"] == image["image"] and
                image["identity"]["version_code"] == 30232 and image["identity"]["version_name"] == "3.2.32-p34g",
                "ACK-gap package identity differs")
    cli.require(value["build_review"]["errors"] == 0 and value["build_review"]["boot_built"] is False and
                value["source_delta"] == ["USER/HAL/HAL_Bluetooth.cpp", "USER/HAL/p34_ack_gap.h"],
                "ACK-gap build scope differs")
    source = store.read(value["source"]["path"])
    for item in source["files"]:
        cli.require(cli.record(store.checked(item["path"])) == item, "ACK-gap candidate source changed")
    y = dict(target_bindings=value["historical_receiver_bindings"])
    actual = shared.bindings(y, image["image"], image["identity"], value["artifacts"], value["constants"])
    cli.require(actual == image["bindings"], "ACK-gap image/MAP bindings differ")
    cli.require(all(group["native"][key] is True for key in
                ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                "ACK-gap native proof incomplete")
    cli.require({case["name"] for case in group["negatives"]} ==
                {"payload-crc", "truncated", "same-version"} and
                all(case["native"]["passed"] is True and case["native"]["prepares"] == 0
                    for case in group["negatives"]), "negative package proofs incomplete")
    return value


def load_for_context(c, specification):
    cli.require(specification == cli.ACK_GAP_GROUPS[GROUP], "not the admitted ACK-gap cell")
    value = load()
    cli.require(c.receiver_version == 30230 and c.bindings == value["historical_receiver_bindings"] and
                c.previous_assets["target"] == value["historical_receiver"], "ACK-gap predecessor differs")
    target, group = value["images"]["aa"], value["groups"]["bootstrap"]
    return dict(result=value["result"], specification=specification,
        receiver=value["historical_receiver"], receiver_bindings=c.bindings,
        target=target["image"], target_identity=target["identity"], target_bindings=target["bindings"],
        package=group["package"], package_kind="full", header=group["header"], decoded=group["native"],
        decoded_image=target["image"], negatives=group["negatives"], manifest=cli.record(ROOT / RELATIVE))
