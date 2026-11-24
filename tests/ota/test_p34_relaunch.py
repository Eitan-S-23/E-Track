"""Host-only tests for the exact unused-capture cleanup/relaunch boundary."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock
import types
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_relaunch as relaunch


class RelaunchTests(unittest.TestCase):
    def setUp(self):
        self.store = cli.Store(ROOT)
        self.out = self.store.checked(relaunch.AREA / "tests" / "fixtures" / uuid.uuid4().hex)

    def unused(self):
        health = dict(captureId=relaunch.CAPTURE, healthy=True, lost=0, error=None, outcome=None,
                      upgradeStarts=0, upgradeEnds=0)
        return dict(pid=None, pid_checked_before_after=True, remote=relaunch.REMOTE, safe_idle=True,
                    snapshots=[], config=dict(sha256="a" * 64), health=health)

    def test_only_stopped_exact_unused_capture_can_be_deleted(self):
        value = self.unused()
        relaunch.verify_unused(value, value["config"], b"events", b"events")
        for key, changed in (("pid", 123), ("pid_checked_before_after", False), ("remote", "wrong"),
                             ("safe_idle", False), ("snapshots", ["snapshot-1.jsonl"]), ("config", dict(sha256="b" * 64))):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                relaunch.verify_unused(dict(value, **{key: changed}), value["config"], b"events", b"events")
        for key, changed in (("captureId", "wrong"), ("lost", 1), ("error", "failure"),
                             ("healthy", False), ("upgradeStarts", 1), ("upgradeEnds", 1), ("outcome", "completed")):
            altered = copy.deepcopy(value)
            altered["health"][key] = changed
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                relaunch.verify_unused(altered, value["config"], b"events", b"events")
        with self.assertRaises(RuntimeError):
            relaunch.verify_unused(value, value["config"], b"changed", b"events")

    def test_real_closed_failure_and_authorization_admit_without_device_commands(self):
        store = cli.Store(ROOT)
        with mock.patch.object(store, "current", return_value=relaunch.RUN):
            plan, config = relaunch.admission(store)
        self.assertEqual(plan["group"], "receive-bootstrap")
        self.assertEqual(config["sha256"], "f7cd0463259467f6fb71cfd7333371ac81d879960cdb0496dad51ee02bdfda45")
        with mock.patch.object(store, "current", return_value="advanced"), self.assertRaises(RuntimeError):
            relaunch.admission(store)

    def test_prestart_protects_completed30228_and_requires_retired_config(self):
        previous = dict(report=dict(summary=dict(captureId="protected"), inputs=dict(snapshot=dict(sha256="b" * 64))))
        value = dict(pid=None, pid_checked_before_after=True, config=None, stable_completed=True,
                     capture_directories=7, remote="files/p34-observations/protected",
                     snapshot_records={"snapshot-1.jsonl": dict(sha256="b" * 64)})
        relaunch.verify_room(value, previous, list(range(7)))
        for key, changed in (("pid", 123), ("config", {}), ("stable_completed", False), ("capture_directories", 8),
                             ("remote", "wrong"), ("snapshot_records", {})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                relaunch.verify_room(dict(value, **{key: changed}), previous, list(range(7)))

    def test_deletion_is_exact_and_happens_only_after_archive_and_path_checks(self):
        c = types.SimpleNamespace(PKG="com.wen.gaia.gaia.p34probe", save=self.store.write, now=cli.now,
                                  envelope=types.SimpleNamespace(MAX_BYTES=1024))
        before = [relaunch.CAPTURE] + ["protected-" + str(i) for i in range(7)]
        archives = {name: self.store.raw(self.out / name, raw) for name, raw in
                    (("health.json", b"health"), ("events.jsonl", b"events"))}
        p = mock.Mock()
        def command(args, **kwargs):
            if "ls" in args:
                return "health.json\nevents.jsonl\n"
            return ""
        p.command.side_effect = command
        p.file_bytes.side_effect = lambda pkg, path, limit: Path(archives[path.rsplit("/", 1)[-1]]["path"]).read_bytes()
        api = types.SimpleNamespace(observation_names=lambda *args: before[1:])
        checker = types.SimpleNamespace(checked_phone_path=mock.Mock(return_value=relaunch.RESOLVED))
        with mock.patch.object(cli, "load_module", return_value=checker):
            remaining = relaunch.remove_exact(c, p, api, self.out / "pass", before, archives)
        self.assertEqual(remaining, before[1:])
        deletions = [call.args[0] for call in p.command.call_args_list if "rm" in call.args[0]]
        self.assertEqual(deletions, [["shell", "run-as", c.PKG, "rm", "-rf", relaunch.REMOTE]])
        p.command.reset_mock()
        checker.checked_phone_path.return_value = relaunch.RESOLVED + "-other"
        with mock.patch.object(cli, "load_module", return_value=checker), self.assertRaises(RuntimeError):
            relaunch.remove_exact(c, p, api, self.out / "wrong-path", before, archives)
        self.assertFalse(any("rm" in call.args[0] for call in p.command.call_args_list))
        checker.checked_phone_path.return_value = relaunch.RESOLVED
        p.file_bytes.side_effect = lambda *args: b"changed"
        with mock.patch.object(cli, "load_module", return_value=checker), self.assertRaises(RuntimeError):
            relaunch.remove_exact(c, p, api, self.out / "changed", before, archives)
        self.assertFalse(any("rm" in call.args[0] for call in p.command.call_args_list))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(relaunch.AREA / "tests")
    cli.require(not out.exists(), "preserve prior self-test output")
    for leaf in ("result.json", "unittest.log", "host"):
        store.checked(out / leaf)
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR"):
        path = store.checked(out / "host" / key.lower())
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    core = cli.verify_tests(store)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RelaunchTests))
    store.raw(out / "unittest.log", log.getvalue().encode())
    store.write(out / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
                errors=len(result.errors), failures=len(result.failures), device_operations=0, core_tests=core,
                sources=[cli.record(p) for p in (Path(__file__), relaunch.SELF)]))
    print(log.getvalue())
    raise SystemExit(not result.wasSuccessful())
