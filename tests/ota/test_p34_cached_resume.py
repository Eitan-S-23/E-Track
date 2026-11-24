"""Unused-App cache recovery guards and modeled observation lifecycle."""
import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[2]
cli = sys.modules["p34_session"]
resume = cli.load_module("p34_cached_resume_tests", ROOT / "Tools/ota/p34_cached_resume.py")
backend = cli.load_module("p34_cached_backend_tests", ROOT / "Tools/ota/p34_session_backend.py")


class CachedResumeTests(unittest.TestCase):
    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(Path(os.environ["P34_TEST_OUT"]) / "cached-fixtures" / uuid.uuid4().hex)

    def unused(self):
        prior = dict(pid=8312, config=dict(sha256="a" * 64), capture_id="123-abc", remote="files/p34-observations/123-abc")
        health = dict(captureId="123-abc", healthy=True, lost=0, error=None, upgradeStarts=0, upgradeEnds=0, outcome=None)
        observed = dict(pid=8312, safe_idle=True, pid_checked_before_after=True, snapshots=[],
                        config=prior["config"], remote=prior["remote"], health=health)
        return observed, prior

    def test_unused_capture_requires_exact_pid_config_identity_and_zero_starts(self):
        observed, prior = self.unused()
        resume.verify_phone(observed, prior)
        for key, value in (("pid", 8313), ("safe_idle", False), ("pid_checked_before_after", False),
                           ("snapshots", ["snapshot-1.jsonl"]), ("remote", "different"),
                           ("config", dict(sha256="b" * 64))):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "same unused App"):
                resume.verify_phone(dict(observed, **{key: value}), prior)
        for key, value in (("captureId", "different"), ("healthy", False), ("lost", 1), ("error", "failed"),
                           ("upgradeStarts", 1), ("upgradeEnds", 1), ("outcome", "completed")):
            changed = copy.deepcopy(observed)
            changed["health"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "same unused App"):
                resume.verify_phone(changed, prior)

    def test_recovery_is_only_for_original_unadmitted_stale_cache_failure(self):
        plan = dict(group="receive-bootstrap")
        result = dict(result="FULL_INSTALL_INCOMPLETE", error="RuntimeError: App file size bound")
        worker, network = dict(worker_exit=1, forced_termination=False), dict(worker_exit=0, forced_termination=False)
        resume.verify_failure(plan, result, worker, network, admitted=False)
        cases = [(dict(group="receive-pressure"), result, worker, network, False),
                 (dict(plan, cached_resume={"prior": 1}), result, worker, network, False),
                 (plan, dict(result, error="different"), worker, network, False),
                 (plan, dict(result, summary={}), worker, network, False),
                 (plan, dict(result, after={}), worker, network, False),
                 (plan, result, worker, network, True),
                 (plan, result, dict(worker, worker_exit=0), network, False),
                 (plan, result, worker, dict(network, forced_termination=True), False)]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(RuntimeError):
                resume.verify_failure(*args[:4], admitted=args[4])

    def test_actual_original_failure_is_read_only_and_current_owner_bound(self):
        store = cli.Store(ROOT)
        run = "20260929T110708-41800"
        original = cli.record(store.run(run) / "cells/s04/result.json")
        plan = store.read(store.run(run) / "plan.json")
        original_record = cli.record
        drift = {item["path"]: item for item in plan["sources"]
                 if (Path(item["path"]).relative_to(ROOT).as_posix()
                     if Path(item["path"]).is_relative_to(ROOT) else None) not in resume.CHANGED_SOURCES
                 and original_record(item["path"]) != item}
        with mock.patch.object(store, "current", return_value=run):
            if drift:
                with self.assertRaisesRegex(RuntimeError, "unrelated original source/input changed"):
                    resume.admission(store, run)
            # Model only original source identity for the historical positive
            # case. Current-source rejection above remains a real check.
            def historical_source(path):
                return drift.get(str(path)) or original_record(path)
            with mock.patch.object(cli, "record", side_effect=historical_source):
                value = resume.admission(store, run)
        self.assertEqual(value["pid"], 8312)
        self.assertEqual(value["config"]["sha256"], "f7cd0463259467f6fb71cfd7333371ac81d879960cdb0496dad51ee02bdfda45")
        self.assertEqual(cli.record(original["path"]), original)
        with mock.patch.object(store, "current", return_value="advanced"), self.assertRaisesRegex(RuntimeError, "actual current"):
            resume.admission(store, run)

    def test_modeled_worker_observes_existing_app_and_closes_before_readback(self):
        store = self.store
        out = store.run("cached")
        cell = out / "cells/s04"
        observed, prior = self.unused()
        for key in ("plan", "result", "config", "launch", "original_network"):
            value = dict(time=cli.now(), pid=8312) if key == "launch" else {}
            path = store.write(store.base / "old" / (key + ".json"), value)
            prior[key] = cli.record(path)
        observed["config"] = prior["config"]
        store.write(store.base / "current.json", dict(run=out.name))
        intent = store.write(out / "resume-intent.json", dict(prior=prior, source=cli.record(resume.SELF), tests={}))
        store.write(out / "plan.json", dict(cached_resume=cli.record(intent), profile=dict(path="fixture")))
        store.write(cell / "runtime-config.json", {})
        store.raw(cell / "resume-phone/observations.log", b"fixture")
        events = []
        @contextmanager
        def owned(name, value=None):
            events.append(name + " open")
            try:
                yield value
            finally:
                events.append(name + " closed")
        p = mock.Mock()
        p.file_bytes.return_value = json.dumps(observed["health"]).encode()
        phone = mock.Mock()
        phone.usb.side_effect = lambda *args: owned("usb", p)
        reader = mock.Mock()
        trace = mock.Mock()
        reader.Trace.return_value = trace
        trace.start.side_effect = lambda: events.append("trace open")
        trace.stop.side_effect = lambda: events.append("trace closed") or {}
        lock = types.SimpleNamespace(device_lock=lambda: owned("lock"))
        c = types.SimpleNamespace(p=p, save=store.write, read=store.read, environment=lambda: {}, now=cli.now,
            load=lambda name, path: lock if path.name == "repeat_cycle.py" else reader,
            supervisor=types.SimpleNamespace(owned=types.SimpleNamespace(in_job=lambda: True)),
            screen_bytes=b"current", envelope=object())
        api = mock.Mock()
        api.context.return_value = c
        api.phone.return_value = phone
        api.capture.return_value = observed
        api.downloaded_package.return_value = b"current"
        api.initial_sample.return_value = dict(profile=dict(run=0))
        api.installed_context.return_value = c
        def checkpoint(context, dest, before=False):
            events.append("before" if before else "after")
            return dict(path="modeled")
        api.install_checkpoint.side_effect = checkpoint
        def observe(*args, **kwargs):
            events.append("observe")
            self.assertFalse(store.read(cell / "launch.json")["app_restarted"])
            p.file_bytes("fixture", "capture/health.json", 8192)
            return dict(completed=True)
        api.observe_install.side_effect = observe
        api.analyze_install.side_effect = lambda *args: events.append("analysis") or dict(result="FULL_INSTALL_VERIFIED")
        contract = types.SimpleNamespace(verify_experiment=mock.Mock())
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend", return_value=api), \
                mock.patch.object(cli, "load_module", return_value=contract):
            self.assertEqual(resume.worker(store, out.name), 0)
        self.assertLess(events.index("trace closed"), events.index("after"))
        self.assertLess(events.index("usb closed"), events.index("analysis"))
        self.assertEqual(store.read(cell / "health-live.json")["health"]["upgradeStarts"], 0)
        phone.provision.assert_not_called()
        phone.network.assert_not_called()
        phone.release_old.assert_not_called()
        self.assertEqual(api.observe_install.call_count, 1)

    def test_observer_window_is_renewed_without_forging_app_launch_time(self):
        out = self.store.run("cached")
        clock = 2000
        old = cli.dt.datetime.fromtimestamp(1, cli.dt.timezone.utc).isoformat()
        resumed = cli.dt.datetime.fromtimestamp(clock, cli.dt.timezone.utc).isoformat()
        self.store.write(out / "cells/s04/launch.json", dict(time=old, observation_resumed_at=resumed, app_restarted=False))
        self.store.write(out / "cells/s04/status.json", dict(result="APP_LAUNCHED_CONNECT_AND_DOWNLOAD"))
        def state(store, path, **kwargs):
            return dict(state="LIVE" if path.name == "s04" else "NOT_STARTED")
        with mock.patch.object(cli, "owner_state", side_effect=state):
            result = cli.status(self.store, out.name, "s04", clock=clock)
        self.assertEqual(result["worker"]["remaining_app_start_seconds"], cli.APP_START_SECONDS)
        self.assertEqual(self.store.read(out / "cells/s04/launch.json")["time"], old)


TEST_CLASSES = (CachedResumeTests,)
