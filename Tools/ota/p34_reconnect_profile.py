"""Exact diagnostic APK and full-only post-reboot cadence binding."""
import json
from pathlib import Path

import p34_session as cli

ROOT = Path(__file__).resolve().parents[2]
APK_REPORT = ".cache/p34-signing/apk-g2/apk.json"
SHA = "0dd20fe72940ca26101c5d41f1b26cd039189a8a"
RUN = 36874130469
ARCHIVE_SHA = "2e54f3424869b68b19696b7af5e797385c5c017ea72723d6fa44f58d00baaac4"
CERTIFICATE = "9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579"
CADENCE = dict(rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500)


def apk():
    value = json.loads((ROOT / APK_REPORT).read_bytes())
    cli.require(value["sha"] == SHA and value["run"] == RUN and not value["independent_acceptance"],
                "reconnect APK provenance changed")
    item, meta = value["apk"], value["metadata"]
    cli.require(cli.record(item["path"]) == item and meta["sha256"] == item["sha256"] and
                meta["commit"] == SHA and meta["application_id"] == "com.wen.gaia.gaia.p34probe" and
                meta["development_signing"] == dict(fixed=True, certificate_sha256=CERTIFICATE) and
                meta["release_signing"] is False and
                meta["requested_ota_link_candidate"] == dict(name="runtime", runtime_config=True),
                "reconnect APK bytes/metadata changed")
    receipts = list((ROOT / ".cache/p34-signing/apk-g2").glob("download-recovery-*/artifacts/11168875966/receipt.json"))
    cli.require(len(receipts) == 1, "one exact verified APK archive required")
    receipt = json.loads(receipts[0].read_bytes())
    cli.require(receipt["id"] == 11168875966 and receipt["archive"]["sha256"] == ARCHIVE_SHA and
                cli.record(receipt["archive"]["path"]) == receipt["archive"] and item in receipt["files"],
                "APK original archive binding changed")
    cli.require(len(value["host_reports"]) == 2, "two original host reports required")
    hosts = set()
    for report in value["host_reports"]:
        cli.require(cli.record(report["path"]) == report, "original host report changed")
        data = json.loads(Path(report["path"]).read_bytes())
        cli.require(data["development_result"] == "PASS" and data["scope"] == "all" and
                    data["source_before"]["head"] == SHA and data["source_before"]["clean"],
                    "exact all-scope host check required")
        hosts.add(json.dumps(data["host"], sort_keys=True))
    cli.require(len(hosts) == 2, "duplicate host reports")
    return value


def config(value):
    cli.require(value["schema"] == 2 and value["transferMode"] == "full" and value["prefixBytes"] == 0 and
                value["currentVersionCode"] == 30242 and value["targetVersionCode"] == 30243 and
                value["requestedBaud"] == 921600 and value["senderWindowSegments"] == 28,
                "reconnect configuration axes changed")
    return dict(value, schema=3, **CADENCE)


def validate_cadence(value):
    cli.require(type(value.get("schema")) is int and value["schema"] == 3 and
                value.get("transferMode") == "full" and type(value.get("prefixBytes")) is int and
                value["prefixBytes"] == 0 and
                all(type(value.get(k)) is int and value[k] == v for k, v in CADENCE.items()),
                "unplanned reconnect cadence")
