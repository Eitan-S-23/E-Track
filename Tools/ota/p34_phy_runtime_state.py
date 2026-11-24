"""Read only existing Dart diagnostics/OTA getters through a scoped USB forward."""
import json
from pathlib import Path
import re
import socket
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_inspect as inspect

cli, AREA = inspect.cli, inspect.AREA
OUT = AREA / "runtime-state-001"
PORT = 6129


def worker(s):
    observed = s.read(inspect.OUT / "result.json")
    cli.require(observed["result"] == "CURRENT_APP_INSPECTED_NO_MUTATION" and observed["usb_closed"], "inspection unresolved")
    pid = observed["pid"]
    text = (inspect.OUT / "logcat.log").read_text(encoding="utf-8")
    matches = re.findall(r"The Dart VM service is listening on http://127\.0\.0\.1:(\d+)(/[A-Za-z0-9_=-]+/)", text)
    cli.require(len(matches) == 1 and pid == "20656", "original VM endpoint ambiguous")
    remote_port, auth_path = matches[0]
    b, d, p, lock = inspect.trial.install.runtime()
    value = dict(result="RUNTIME_STATE_INCOMPLETE", no_ota=True, no_app_restart=True,
                 getters_only=True, pid=pid)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def rpc(method, **params):
        # The VM token remains in memory, never in command logs or receipts.
        uri = "http://127.0.0.1:" + str(PORT) + auth_path + method
        if params: uri += "?" + urllib.parse.urlencode(params)
        with opener.open(uri, timeout=15) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        cli.require(len(raw) <= 2 * 1024 * 1024, "VM response too large")
        reply = json.loads(raw)
        cli.require("error" not in reply and "result" in reply, "read-only VM request rejected: " + method)
        return reply["result"]
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, inspect.trial.install.TARGET_SHA) is not None, "repaired APK differs")
            cli.require(p.command(["shell", "pidof", inspect.trial.install.PKG], check=False).strip() == pid, "App process changed")
            with socket.socket() as sock: sock.bind(("127.0.0.1", PORT))
            p.command(["forward", "--no-rebind", "tcp:" + str(PORT), "tcp:" + remote_port])
            try:
                vm = rpc("getVM")
                isolates = [i for i in vm["isolates"] if i.get("name") == "main"]
                cli.require(len(isolates) == 1, "one main isolate required")
                iid = isolates[0]["id"]
                isolate = rpc("getIsolate", isolateId=iid)
                def library(suffix):
                    found = [i for i in isolate["libraries"] if i["uri"].endswith(suffix)]
                    cli.require(len(found) == 1, "expected App library missing")
                    return found[0]
                diagnostic = library("/ota/ota_diagnostics.dart")
                def evaluate(target, expression):
                    result = rpc("evaluate", isolateId=iid, targetId=target, expression=expression)
                    cli.require(result.get("type") == "@Instance" and "valueAsString" in result, "getter did not return a primitive")
                    return result["valueAsString"]
                value["diagnostics"] = {key: evaluate(diagnostic["id"], expression) for key, expression in {
                    "enabled": "OtaDiagnostics.current.enabled",
                    "ready": "OtaDiagnostics.current.status.value.ready",
                    "error": "OtaDiagnostics.current.status.value.error.toString()",
                    "logMissing": "OtaDiagnostics.current._log == null",
                }.items()}
                service = rpc("getObject", isolateId=iid, objectId=library("/services/ota_service.dart")["id"])
                classes = [i for i in service["classes"] if i["name"] == "OtaService"]
                cli.require(len(classes) == 1, "OTA service class missing")
                found = rpc("getInstances", isolateId=iid, classId=classes[0]["id"], limit=8)
                cli.require(found["totalCount"] == len(found["instances"]) <= 8, "too many OTA service instances")
                value["services"] = [dict(isUpgrading=evaluate(i["id"], "isUpgrading"),
                    phase=evaluate(i["id"], "phase.toString()")) for i in found["instances"]]
                cli.require(value["diagnostics"] == dict(enabled="true", ready="false", error="capture-initialization", logMissing="true") and
                    all(i["isUpgrading"] == "false" for i in value["services"]), "App is not recorder-blocked idle")
                cli.require(p.command(["shell", "pidof", inspect.trial.install.PKG], check=False).strip() == pid, "process changed during read")
                value["result"] = "RECORDER_BLOCKED_IDLE_RUNTIME_VERIFIED"
            finally:
                p.command(["forward", "--remove", "tcp:" + str(PORT)])
        value["usb_closed"] = True
    except Exception as error:
        # URLError may contain the auth-bearing URL, so retain only its type.
        value["error"] = type(error).__name__
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "runtime read unavailable; no App stop was performed")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact mode required")
    s = cli.Store(ROOT)
    closed = s.read(AREA / "runtime/startup-inspect-001/closed.json")
    cli.require(closed["worker_exit"] == 0 and not closed["forced_termination"], "inspection owner unresolved")
    owner = cli.load_module("phy_vm_read_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        cli.require(not OUT.exists(), "preserve runtime read")
        for name in ("intent.json", "result.json", "host", "usb"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), source=cli.record(__file__), getters_only=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/runtime-state-001"), Path(__file__), ["worker"], 600))
    else:
        cli.require(owner.owned.in_job() and s.read(OUT / "intent.json")["source"] == cli.record(__file__), "source-pinned read owner required")
        worker(s)
