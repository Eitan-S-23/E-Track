"""Named, opt-in inheritance of the accepted P3-4 candidate link settings.

These checks bind build intent and observed settings, not performance acceptance.
The profile does not change release defaults or remove receiver ACK validation.
"""
import hashlib
import json
import re
from urllib.parse import urlsplit

NAME = "p34-qualified-v1"
ENV = "TRACE_DEV_OTA_LINK_PROFILE"
CANDIDATE = "runtime-pipeline"
RUNTIME = {
    "schema": 10, "requestedBaud": 921600, "reuseGatt": True,
    "withoutResponse": True, "senderWindowSegments": 24,
    "transferMode": "full", "prefixBytes": 0, "dataBatchFrames": 12,
    "ackTimeoutMs": 2000, "pauseScanDuringOta": False,
    "androidHighPriority": False, "androidPhyPolicy": "off",
    "reuseRebootInfoLink": True, "rebootInfoTimeoutMs": 2000,
    "rebootProbeIntervalMs": 1500, "rebootInfoMaxAttempts": 3,
}
IDENTITY_FIELDS = {
    "runId", "target", "firmwareLatestUrl", "packageBytes", "packageSha256",
    "currentVersionCode", "currentImageSha256", "targetVersionCode", "targetImageSha256",
}


def selected(env):
    name = env.get(ENV, "").strip()
    if name in ("", "none"):
        return None
    if name != NAME:
        raise ValueError("Unknown " + ENV)
    if env.get("TRACE_DEV_OTA_LINK_CANDIDATE", "").strip() != CANDIDATE:
        raise ValueError(NAME + " requires runtime-pipeline; baseline/runtime are not the fast path")
    return NAME


def require_fields(actual, expected, label):
    for key, value in expected.items():
        if type(actual.get(key)) is not type(value) or actual[key] != value:
            raise ValueError(label + " mismatch: " + key)


def check_apk(metadata, *, target):
    require_fields(metadata, {"artifact_kind": "development-debug-apk", "release_signing": False}, "APK")
    require_fields(metadata.get("requested_ota_link_candidate", {}),
                   {"name": CANDIDATE, "runtime_config": True, "pipeline": True, "profile": NAME}, "APK profile")
    require_fields(metadata.get("device_observation", {}), {"enabled": True, "target": target}, "APK observation")
    if not re.fullmatch(r"[0-9a-f]{64}", metadata.get("sha256", "")):
        raise ValueError("APK hash missing")


def check_runtime(config):
    if set(config) != set(RUNTIME) | IDENTITY_FIELDS:
        raise ValueError("Runtime profile fields missing or unknown")
    require_fields(config, RUNTIME, "runtime profile")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", config["runId"]):
        raise ValueError("Invalid run identity")
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", config["target"]):
        raise ValueError("Exact BLE target required")
    uri = urlsplit(config["firmwareLatestUrl"])
    if (uri.scheme != "https" or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", uri.hostname or "")
            or uri.port not in (None, 443) or uri.username or uri.password
            or "?" in config["firmwareLatestUrl"] or "#" in config["firmwareLatestUrl"]
            or uri.path != "/api/public/firmware/latest"):
        raise ValueError("Credential-free HTTPS latest endpoint required")
    for key in ("packageSha256", "currentImageSha256", "targetImageSha256"):
        if not isinstance(config[key], str) or not re.fullmatch(r"[0-9a-f]{64}", config[key]):
            raise ValueError("Invalid identity: " + key)
    for key in ("currentVersionCode", "targetVersionCode", "packageBytes"):
        if type(config[key]) is not int or not 0 < config[key] <= 2100000000:
            raise ValueError("Invalid integer: " + key)
    if config["currentVersionCode"] >= config["targetVersionCode"] or config["packageBytes"] < 64:
        raise ValueError("A legal forward package is required")


def runtime_config(*, metadata, run_id, target, latest_url, package, base, target_image,
                   base_version, target_version):
    check_apk(metadata, target=target)
    config = dict(RUNTIME, runId=run_id, target=target, firmwareLatestUrl=latest_url,
                  packageBytes=package["bytes"], packageSha256=package["sha256"],
                  currentVersionCode=base_version, currentImageSha256=base["sha256"],
                  targetVersionCode=target_version, targetImageSha256=target_image["sha256"])
    check_runtime(config)
    return config


def runtime_bytes(config):
    check_runtime(config)
    return (json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def check_observation(statistics, config, *, experiments):
    """Consume the existing strict snapshot parser, never an unverified UI value."""
    check_runtime(config)
    if not isinstance(experiments, list) or not experiments:
        raise ValueError("Original runtime observations required")
    stamp = dict(schema=config["schema"], runId=config["runId"],
                 configSha256=hashlib.sha256(runtime_bytes(config)).hexdigest())
    for experiment in experiments:
        require_fields(experiment, stamp, "observed runtime")
    expected = {key: value for key, value in RUNTIME.items()
                if key not in ("schema", "transferMode", "prefixBytes")}
    expected.update(protocol=2, writeMode="without", requestedWindowSegments=24,
                    requestedDataBatchFrames=12)
    parameters = statistics.get("parameters", {})
    require_fields(parameters, expected, "negotiated profile")
    inputs = {key: config[key] for key in IDENTITY_FIELDS
              if key not in ("runId", "target", "firmwareLatestUrl")}
    inputs["deviceAddress"] = config["target"].lower()
    require_fields(parameters.get("input", {}), inputs, "observed identity")
    require_fields(statistics, {"success": True, "finalDurable": config["packageBytes"]}, "transfer")
    return {"profile": NAME, "settings_match": True, "performance_acceptance": "NOT_ADJUDICATED"}
