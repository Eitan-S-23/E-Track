"""Offline regression for PID/capacity readiness and just-in-time safe archival."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_runtime_doctor as d

OUT = ROOT / ".cache/p34-runtime-doctor/tests"
NAME = "1790999999999999-aaaaaaaaaaaaaaaaaaaaaaaa"
SENTINEL = "OTAOBS0123456789abcdef01234567"
TARGET = "AA:BB:CC:DD:EE:FF"
SHA = "a" * 64


def query():
    rows = [dict(seq=1, kind="open", captureId=NAME, sentinel=SENTINEL, target=TARGET, pid=10),
            dict(seq=2, kind="line", message="OTA_EXPERIMENT " + json.dumps(dict(configSha256=SHA, deviceAddress=TARGET)))]
    raw = b"".join((json.dumps(row) + "\n").encode() for row in rows)
    health = dict(captureId=NAME, healthy=True, lost=0, error=None, upgradeStarts=0, upgradeEnds=0,
                  outcome=None, records=2, producerLines=1, bytes=len(raw))
    return raw, health


class Phone:
    def __init__(self, *, eligible=True, count=8):
        self.dirs = {"files/p34-observations/" + str(1790000000000000+i) + "-" + "b"*24:
                     {"snapshot-1.jsonl": b"protected"} for i in range(count-1)}
        raw,h = query()
        self.dirs["files/p34-observations/"+NAME] = {"events.jsonl":raw, "health.json":json.dumps(h).encode()}
        if not eligible:
            self.dirs["files/p34-observations/"+NAME]["snapshot-1.jsonl"] = b"protected"
        self.moves = []

    def command(self,args,*,binary=False,check=True):
        if args[:2] == ["shell","pidof"]:
            return ""
        self_test = args[:2] == ["exec-out","run-as"]
        if not self_test:
            raise AssertionError(args)
        op = args[3:]
        if op[:2] == ["ls","-d"]:
            path=op[2]
            return path if path in self.dirs or path=="files/p34-archived-observations" else ""
        if op[:2] == ["ls","-1"]:
            path=op[2]
            if path=="files/p34-observations":
                return "\n".join(sorted(p.split("/")[-1] for p in self.dirs if p.startswith(path+"/")))
            return "\n".join(sorted(self.dirs[path]))
        if op[:2] == ["head","-c"]:
            path,name=op[3].rsplit("/",1)
            raw=self.dirs[path][name][:int(op[2])]
            return raw if binary else raw.decode()
        if op[:2] == ["mv","-n"]:
            source,target=op[2:]
            if target in self.dirs:
                raise AssertionError("overwrite")
            self.dirs[target]=self.dirs.pop(source)
            self.moves.append((source,target))
            return ""
        raise AssertionError(args)


class Tests(unittest.TestCase):
    def test_classification_distinguishes_current_writer_from_old_evidence(self):
        _,health=query()
        base=dict(installed_sha=SHA,expected_sha=SHA,pid="10",expected_pid=10,config_matches=True,
                  network_live=True,captures=[dict(header=dict(pid=10),health=health)])
        self.assertEqual(d.classify(base),"RECORDER_READY_PACKAGE_ADMISSION_STILL_REQUIRED")
        old=copy.deepcopy(base)
        old["captures"]=[dict(header=dict(pid=9),health=health) for _ in range(8)]
        self.assertEqual(d.classify(old),"NO_CURRENT_CAPTURE_STORE_FULL")
        old["captures"]=old["captures"][:7]
        self.assertEqual(d.classify(old),"CURRENT_CAPTURE_MISSING")
        for key,value,expected in [("installed_sha","wrong","APK_MISMATCH"),("pid","","APP_NOT_RUNNING"),
                                   ("expected_pid",11,"HOST_PID_CHANGED"),("config_matches",False,"CONFIG_MISMATCH"),
                                   ("network_live",False,"DOWNLOAD_SERVICE_CLOSED")]:
            self.assertEqual(d.classify(dict(base,**{key:value})),expected)

    def test_active_or_failed_capture_never_ready(self):
        _,health=query()
        base=dict(installed_sha=SHA,expected_sha=SHA,pid="10",expected_pid=10,config_matches=True,network_live=True)
        for changes,expected in [(dict(upgradeStarts=1),"TRANSFER_ACTIVE_OR_UNRESOLVED"),
                                 (dict(error="invalid-record"),"RECORDER_FAILED"),
                                 (dict(upgradeStarts=1,upgradeEnds=1),"CAPTURE_ALREADY_USED")]:
            self.assertEqual(d.classify(dict(base,captures=[dict(header=dict(pid=10),health=dict(health,**changes))])),expected)

    def test_query_gate_rejects_used_unknown_or_corrupt_capture(self):
        raw,h=query()
        d.capacity.validate_query(raw,json.dumps(h),NAME,{SHA},SENTINEL,TARGET)
        for changes in [dict(upgradeStarts=1),dict(lost=1),dict(bytes=0),dict(records=3),dict(outcome="completed")]:
            with self.assertRaises(RuntimeError):
                d.capacity.validate_query(raw,json.dumps(dict(h,**changes)),NAME,{SHA},SENTINEL,TARGET)
        with self.assertRaises(RuntimeError):
            d.capacity.validate_query(raw,json.dumps(h),NAME,{"b"*64},SENTINEL,TARGET)

    def gate(self,phone,name):
        with mock.patch.object(d.capacity.backend,"checked_phone_path",side_effect=lambda c,p,path,**kw:"/data/user/0/test/"+path):
            d.capacity.ensure_capacity(d.cli.Store(ROOT),phone,OUT/name,package="test",sentinel=SENTINEL,
                                       target=TARGET,known_configs={SHA})

    def test_slot_consumed_after_early_preflight_is_safely_recovered(self):
        phone=Phone()
        original=copy.deepcopy(phone.dirs)
        self.gate(phone,"race")
        self.assertEqual(len(phone.moves),1)
        source,target=phone.moves[0]
        self.assertEqual(phone.dirs[target],original[source])
        for path,files in original.items():
            if path!=source:self.assertEqual(phone.dirs[path],files)
        self.assertEqual(json.loads((OUT/"race/result.json").read_bytes())["count"],7)

    def test_no_capacity_mutation_when_slot_exists(self):
        phone=Phone(count=7)
        self.gate(phone,"free")
        self.assertEqual(phone.moves,[])

    def test_no_eligible_capture_fails_without_moving_anything(self):
        phone=Phone(eligible=False)
        before=copy.deepcopy(phone.dirs)
        with self.assertRaises(RuntimeError):self.gate(phone,"protected")
        self.assertEqual(phone.moves,[])
        self.assertEqual(phone.dirs,before)


if __name__ == "__main__":
    d.cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,"isolated root required")
    s=d.cli.Store(ROOT)
    s.checked(OUT)
    d.cli.require(not OUT.exists(),"preserve tests")
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    log=s.raw(OUT/"tests.log",stream.getvalue().encode())
    s.write(OUT/"result.json",dict(result="PASS" if result.wasSuccessful() else "FAIL",tests=result.testsRun,
        log=log,source=d.cli.record(d.__file__),capacity=d.cli.record(d.capacity.__file__),test=d.cli.record(__file__),hardware=False))
    print(stream.getvalue(),flush=True)
    sys.exit(not result.wasSuccessful())
