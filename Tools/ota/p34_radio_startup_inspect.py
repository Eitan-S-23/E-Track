"""Read-only reconciliation of the changed App process; no install/restart/OTA."""
from pathlib import Path
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_followup as f
cli = f.cli
OUT = f.AREA / "startup-inspect-001"


def worker(s):
    b,d,p,lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    pkg = f.recovery.install.previous.PKG
    value = dict(result="READ_ONLY_INSPECTION_INCOMPLETE", no_phone_mutation=True)
    try:
        with lock.device_lock(), d["usb"](b,p,OUT):
            p.phone_identity()
            value["installed"] = d["installed"](b,p,s.read(f.AREA / "apk-g1/apk.json")["apk"]["sha256"])
            pid = p.command(["shell","pidof",pkg],check=False).strip()
            cli.require(not pid or pid.isdigit(), "ambiguous App process")
            value["pid"] = pid
            s.raw(OUT / "logcat.log",p.command(["logcat","-d","-v","threadtime",*(["--pid="+pid] if pid else [])],timeout=45,binary=True))
            config = p.file_bytes(pkg,"files/p34-experiment.json",8192)
            value["config"] = s.raw(OUT / "runtime-config.json",config)
            names = p.command(["exec-out","run-as",pkg,"ls","-1","files/p34-observations"]).splitlines()
            cli.require(0 < len(names) <= 16 and all(f.radio.backend.CAPTURE_NAME.fullmatch(n) for n in names), "unknown capture names")
            value["names"],value["captures"] = names,[]
            for name in sorted(names)[-2:]:
                remote = "files/p34-observations/"+name
                files = p.command(["exec-out","run-as",pkg,"ls","-1",remote]).splitlines()
                raw = p.file_bytes(pkg,remote+"/health.json",8192)
                events = p.file_bytes(pkg,remote+"/events.jsonl",16*1024*1024)
                value["captures"].append(dict(name=name,files=files,health=json.loads(raw),
                    health_file=s.raw(OUT/name/"health.json",raw),events=s.raw(OUT/name/"events.jsonl",events)))
            cli.require(p.command(["shell","pidof",pkg],check=False).strip()==pid,"process changed during read")
            value["result"]="CURRENT_APP_INSPECTED_NO_MUTATION"
        value["usb_closed"]=True
    except Exception as e:
        value.update(error=type(e).__name__,detail=str(e))
    s.write(OUT/"result.json",dict(time=cli.now(),**value))
    print(json.dumps(value),flush=True)
    cli.require("error" not in value,"read-only reconciliation failed")


if __name__ == "__main__":
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,"isolated root required")
    s=cli.Store(ROOT)
    supervisor=cli.load_module("startup_inspect_owner",ROOT/".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1:] == ["launch"]:
        cli.require(not OUT.exists(),"preserve inspection")
        for name in ("intent.json","result.json","logcat.log","runtime-config.json","usb","host"):
            s.checked(OUT/name)
        s.write(OUT/"intent.json",dict(source=cli.record(__file__),no_phone_mutation=True))
        print(supervisor.owned.launch(f.radio.AREA/"runtime/startup-inspect-001",Path(__file__),["worker"],600),flush=True)
    else:
        cli.require(sys.argv[1:]==["worker"] and supervisor.owned.in_job(),"finite inspection owner required")
        worker(s)
