"""One same-signer PHY APK update after CI, retaining the completed 30266 capture."""
import argparse
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace, FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_batch_install as original
import p34_batch_review as review

cli = original.cli
AREA = ROOT / ".cache/p34-phy"
OUT = AREA / "install-001"
PRIOR = ROOT / ".cache/p34-half-erase/trials/measure"
TEST = ROOT / "tests/ota/test_p34_phy_install.py"
HOST = AREA / "install-tests-001"
SHA = "41d147a94294911929fba08478ab0b5337ed1107"
PKG = "com.wen.gaia.gaia.p34probe"
OLD_SHA = "a48549082f74a234d5acf0affdfa0d4120f2099fffefa8a40dc0302cac444387"
CERT = "9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579"
IMAGE = "ddc9c8b60a04ce36134e8418c927532a5f680b735056752f338a6dbc6d58893b"


def validate_retained(value):
    cli.require(value["result"] == "FULL_INSTALL_VERIFIED" and
        value["summary"]["input"]["targetVersionCode"] == 30266 and
        value["summary"]["input"]["targetImageSha256"] == IMAGE, "wrong retained firmware")


def validate_apk(value, hosts, natives):
    cli.require(value["sha"] == SHA and value["metadata"]["application_id"] == PKG and
        value["certificate_sha256"] == CERT and value["metadata"]["release_signing"] is False,
        "wrong candidate APK identity")
    cli.require(len(hosts) == 2 and len({h["host"] for h in hosts}) == 2 and
        all(h["development_result"] == "PASS" and h["scope"] == "all" and
            h["source_before"]["head"] == SHA and h["source_before"]["clean"] for h in hosts),
        "both exact clean CI hosts required")
    cli.require(len(natives) == 2 and all(n["passed"] is True for n in natives),
        "both native lifecycle regressions required")


def inputs(s):
    _, completed = review.load_report(s, PRIOR)
    validate_retained(completed)
    report = s.read(AREA / "apk-g1/apk.json")
    for item in [report["apk"], *report["host_reports"], *report["native_reports"]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "candidate or original CI bytes changed")
    validate_apk(report, [s.read(h["path"]) for h in report["host_reports"]],
                 [s.read(h["path"]) for h in report["native_reports"]])
    certificate = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))["apk_certificate"]
    cli.require(certificate(Path(report["apk"]["path"]).read_bytes()) == CERT, "actual APK signer differs")
    return report, completed


def worker(s, *, input_reader=inputs, runtime_loader=runpy):
    operation = FunctionType(original.worker.__code__, dict(original.worker.__globals__,
        inputs=input_reader, OUT=OUT, prior=SimpleNamespace(PKG=PKG, OLD_SHA=OLD_SHA),
        runpy=runtime_loader), original.worker.__name__)
    operation(s)


def sources():
    return [cli.record(path) for path in (Path(__file__), TEST, Path(original.__file__),
        Path(review.__file__), ROOT / "Tools/ota/p34_signing_migration.py",
        ROOT / ".cache/p34-next/device.py", ROOT / ".cache/p3-4-screening-20260922/phone.py")]


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated project root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    test = s.read(HOST / "result.json")
    cli.require(test["result"] == "PASS" and test["sources"] == sources(), "current installer self-tests required")
    report, completed = inputs(s)
    owner = cli.load_module("phy_install_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "check":
        cli.require(not OUT.exists(), "preserve prior install attempt")
        print("PHY_INSTALL_INPUTS_VERIFIED", report["apk"]["sha256"])
    elif args.mode == "launch":
        cli.require(not OUT.exists(), "preserve prior install attempt; no blind reinstall")
        for name in ("intent.json", "result.json", "power.txt", "stop-intent.json", "install-intent.json",
                     "runtime-config.json", "capture", "host", "usb"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), sources=sources(), apk=report["apk"],
            retained=completed["summary"]["input"], no_ota=True, no_uninstall=True, no_data_clear=True,
            purpose="required new native PHY readback bridge; retain config/permissions/completed snapshot"))
        print(owner.owned.launch(s.checked(AREA / "runtime/install-001"), Path(__file__), ["worker"], 600))
    else:
        cli.require(owner.owned.in_job() and s.read(OUT / "intent.json")["sources"] == sources(),
                    "finite source-pinned installation owner required")
        worker(s)


if __name__ == "__main__":
    main()
