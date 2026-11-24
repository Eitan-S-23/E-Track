"""Contained host tests; no ADB, J-Link, tunnel, CI or firmware operations."""
from __future__ import annotations

import datetime as dt
import copy
from contextlib import nullcontext
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import time
import types
import unittest
from unittest import mock
import uuid
import zlib

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("p34_session", ROOT / "Tools/ota/p34_session.py")
cli = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cli
spec.loader.exec_module(cli)
backend = cli.load_module("p34_session_backend_test", ROOT / "Tools/ota/p34_session_backend.py")
observation_tests = cli.load_module("p34_observation_tests", ROOT / "tests/ota/test_p34_observation.py")
prefix_mcu = cli.load_module("p34_sampler_tests", ROOT / ".cache/p34-next/prefix_mcu.py")
flash_map = cli.load_module("p34_flash_map_tests", ROOT / ".cache/p34-next/qspi_clock_probe.py")
OUTPUT = Path(os.environ["P34_TEST_OUT"])
prefix_contract_tests = cli.load_module("p34_prefix_contract_tests", ROOT / ".cache/p34-next/test_prefix.py")
prefix_contract_tests.c.OUT = prefix_contract_tests.c.checked(OUTPUT / "prefix-contract-fixtures")
prefix_contract_tests.c.host.OUT = prefix_contract_tests.c.OUT
full_tests = cli.load_module("p34_full_tests", ROOT / "tests/ota/test_p34_full.py")
window8_tests = cli.load_module("p34_window8_tests", ROOT / "tests/ota/test_p34_window8.py")
repeat_tests = cli.load_module("p34_repeat_tests", ROOT / "tests/ota/test_p34_repeat.py")
install_tests = cli.load_module("p34_install_tests", ROOT / "tests/ota/test_p34_install.py")


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(OUTPUT / "fixtures" / uuid.uuid4().hex)
        self.out = self.store.run("fixture")

    def owner(self, label="network", *, at=100.0, age=0.0):
        path = self.out / "runtime" / label
        self.store.write(path / "config.json", dict(id="fixture", seconds=5480, root=str(ROOT), out=str(path)))
        self.store.write(path / "state.json", dict(session="fixture", time=dt.datetime.fromtimestamp(at-age, dt.timezone.utc).isoformat(),
            worker_alive=True, worker_pid=123, elapsed_seconds=10, forced_termination=False))
        return path

    def live(self, expires):
        self.store.write(self.out / "live-network.json", dict(expires=dt.datetime.fromtimestamp(expires, dt.timezone.utc).isoformat()))

    def test_cold_status_has_no_backend_or_writes(self):
        with mock.patch.object(cli, "backend", side_effect=AssertionError("backend imported")):
            self.assertEqual(cli.status(self.store)["result"], "NO_SESSION")
        self.assertFalse(self.store.base.exists())

    def test_host_timeout_preserves_partial_output_and_never_promotes_old_PASS(self):
        latest = self.store.base / "tests/latest.json"
        self.store.write(latest, dict(passed=True, tests=1, sources=[], original=True))
        original = cli.record(latest)
        timeout = cli.subprocess.TimeoutExpired(["fixture"], cli.HOST_TEST_SECONDS,
                                               output=b"partial stdout\n", stderr=b"partial stderr\n")
        with mock.patch.object(cli, "Store", return_value=self.store), \
                mock.patch.object(cli.subprocess, "run", side_effect=timeout) as run, \
                self.assertRaisesRegex(RuntimeError, "host tests timed out"):
            cli.main(["--root", str(ROOT), "test"])
        self.assertEqual(run.call_args.kwargs["timeout"], cli.HOST_TEST_SECONDS)
        self.assertLessEqual(cli.HOST_TEST_SECONDS, 900)
        self.assertEqual(run.call_args.kwargs["cwd"], ROOT)
        reports = list((self.store.base / "tests").glob("*/timeout.json"))
        self.assertEqual(len(reports), 1)
        value = self.store.read(reports[0])
        self.assertFalse(value["passed"])
        self.assertIsNone(value["tests"])
        self.assertEqual(Path(value["console"]["path"]).read_bytes(), b"partial stdout\npartial stderr\n")
        self.assertEqual(cli.record(latest), original)

    def test_host_timeout_binds_existing_incremental_test_log(self):
        def timeout(command, **kwargs):
            out = Path(kwargs["env"]["P34_TEST_OUT"])
            self.store.raw(out / "unittest.log", b"finished fixture ... ok\npending fixture ... ")
            raise cli.subprocess.TimeoutExpired(command, kwargs["timeout"])
        with mock.patch.object(cli, "Store", return_value=self.store), \
                mock.patch.object(cli.subprocess, "run", side_effect=timeout), \
                self.assertRaisesRegex(RuntimeError, "host tests timed out"):
            cli.main(["--root", str(ROOT), "test"])
        report = next((self.store.base / "tests").glob("*/timeout.json"))
        value = self.store.read(report)
        self.assertEqual(value["partial_tests"], cli.record(report.parent / "unittest.log"))
        self.assertFalse((self.store.base / "tests/latest.json").exists())

    def test_closed_receipt_overrides_old_alive_heartbeat(self):
        path = self.owner()
        self.store.write(path / "closed.json", dict(worker_exit=0, forced_termination=False))
        self.assertEqual(cli.owner_state(self.store, path, clock=100)["state"], "CLOSED")

    def test_expired_service_is_not_reported_as_available(self):
        self.owner()
        self.live(99)
        result = cli.status(self.store, "fixture", clock=100)
        self.assertEqual(result["result"], "SESSION_EXPIRED")
        self.assertEqual(result["network"]["service"], "EXPIRED")

    def test_live_service_and_waiting_app_are_distinct(self):
        self.owner()
        self.owner("s01")
        self.live(200)
        self.store.write(self.out / "cells/s01/status.json", dict(result="APP_LAUNCHED_CONNECT_AND_DOWNLOAD"))
        result = cli.status(self.store, "fixture", clock=100)
        self.assertEqual(result["network"]["service"], "VERIFIED")
        self.assertEqual(result["worker"]["state"], "LIVE")
        self.assertIn("do not start BLE", result["next_action"])

    def test_stale_ready_receipt_does_not_invite_another_transfer(self):
        path = self.owner("s01")
        self.owner()
        self.live(200)
        self.store.write(self.out / "cells/s01/status.json", dict(result="READY_FOR_32K_PREFIX_START"))
        self.store.write(path / "closed.json", dict(worker_exit=1, forced_termination=False))
        result = cli.status(self.store, "fixture", clock=100)
        self.assertEqual(result["result"], "CELL_CLOSED")
        self.assertNotIn("start the 32 KiB", result["next_action"])

    def test_active_or_finalizing_health_does_not_invite_another_transfer(self):
        self.owner("s01")
        self.owner()
        self.live(200)
        self.store.write(self.out / "cells/s01/status.json", dict(result="READY_FOR_32K_PREFIX_START"))
        self.store.write(self.out / "cells/s01/launch.json", dict(time=dt.datetime.fromtimestamp(90, dt.timezone.utc).isoformat()))
        for ends, expected in ((0, "TRANSFER_ACTIVE"), (1, "FINALIZING")):
            self.store.write(self.out / "cells/s01/health-live.json", dict(observed=dt.datetime.fromtimestamp(100, dt.timezone.utc).isoformat(),
                health=dict(upgradeStarts=1, upgradeEnds=ends)), replace=True)
            result = cli.status(self.store, "fixture", clock=100)
            self.assertEqual(result["result"], expected)
            self.assertIn("do not start another", result["next_action"])

    def test_service_expiry_does_not_hide_original_cell_failure(self):
        path = self.owner("s01")
        self.owner()
        self.live(99)
        self.store.write(path / "closed.json", dict(worker_exit=1, forced_termination=False))
        self.store.write(self.out / "cells/s01/status.json", dict(result="CELL_INCOMPLETE", error="original"))
        value = cli.status(self.store, "fixture", clock=100)
        self.assertEqual(value["result"], "CELL_INCOMPLETE")
        self.assertEqual(value["network"]["service"], "EXPIRED")

    def test_stale_or_wrong_owner_is_uncertain(self):
        path = self.owner(age=11)
        self.assertEqual(cli.owner_state(self.store, path, clock=100)["state"], "UNCERTAIN")
        config = self.store.read(path / "config.json")
        config["root"] = str(ROOT.parent)
        self.store.write(path / "config.json", config, replace=True)
        self.assertEqual(cli.owner_state(self.store, path, clock=90)["state"], "UNCERTAIN")

    def test_run_path_cannot_escape(self):
        for name in ("", "../outside", "x/y", "x\\y", "D:elsewhere", "x" * 65):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                self.store.run(name)

    def test_command_lock_releases_on_error_and_preserves_other_owner(self):
        with self.assertRaisesRegex(ValueError, "fixture"):
            with self.store.command_lock():
                with self.assertRaises(FileExistsError):
                    with self.store.command_lock():
                        self.fail("second owner admitted")
                raise ValueError("fixture")
        self.assertFalse((self.store.base / "command.lock").exists())

    def test_stop_rejects_an_active_transfer_without_writing_flags(self):
        self.owner("s01", at=time.time())
        self.store.write(self.out / "cells/s01/health-live.json", dict(observed=cli.now(),
            health=dict(healthy=True, lost=0, error=None, upgradeStarts=1, upgradeEnds=0)))
        with self.assertRaisesRegex(RuntimeError, "transfer is active"):
            cli.stop(self.store, "fixture", "s01")
        self.assertFalse((self.out / "network-stop.json").exists())
        self.assertFalse((self.out / "cells/s01/stop.json").exists())

    def test_stop_requires_fresh_health(self):
        self.owner("s01", at=time.time())
        with self.assertRaisesRegex(RuntimeError, "health missing"):
            cli.can_stop(self.store, self.out, "s01")
        self.store.write(self.out / "cells/s01/health-live.json", dict(observed="2000-01-01T00:00:00+00:00", health={}))
        with self.assertRaisesRegex(RuntimeError, "health is stale"):
            cli.can_stop(self.store, self.out, "s01")

    def test_bounded_wait_stops_without_an_extra_operation(self):
        clock, calls = [0.0], []
        def check():
            calls.append(clock[0])
            return False
        with self.assertRaisesRegex(RuntimeError, "bounded wait"):
            cli.wait_until(check, seconds=1, clock=lambda: clock[0], sleep=lambda delay: clock.__setitem__(0, clock[0] + delay))
        self.assertEqual(calls, [0, .25, .5, .75, 1])

    def test_repeated_start_returns_live_session_without_backend(self):
        self.owner("s01", at=time.time())
        self.owner(at=time.time())
        self.live(time.time() + 5000)
        self.store.write(self.store.base / "current.json", dict(run="fixture"))
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend") as factory:
            value = cli.start(self.store, self.store.base / "profile.json", "s01")
        self.assertEqual(value["worker"]["state"], "LIVE")
        factory.assert_not_called()
        self.assertEqual(len(list((self.store.base / "runs").iterdir())), 1)

    def test_cold_start_waits_for_service_without_spending_cell_or_weakening_timeout(self):
        self.assertEqual(cli.NETWORK_READY_WAIT_SECONDS, 900)
        self.assertGreater(cli.NETWORK_SECONDS - cli.NETWORK_READY_WAIT_SECONDS, cli.CELL_SECONDS)
        for outcome in ("ready", "timeout", "closed"):
            self.setUp()
            api, ctx = mock.Mock(), mock.Mock()
            api.context.return_value = ctx
            api.inspect.return_value = dict(result="APP_INSPECTED")
            api.prepare.side_effect = lambda c, out, phone, tests: self.store.write(out / "plan.json", dict(group="screen"))
            def wait(predicate, *, seconds):
                self.assertEqual(seconds, 900)
                self.assertEqual(ctx.supervisor.owned.launch.call_count, 1)
                out = self.store.run(self.store.current())
                self.assertFalse((out / "cells/s01").exists())
                self.assertFalse(predicate())
                if outcome == "timeout":
                    raise RuntimeError("bounded wait expired")
                if outcome == "closed":
                    self.store.write(out / "runtime/network/closed.json", dict(worker_exit=1))
                    predicate()
                self.store.write(out / "live-network.json", dict(expires=cli.now()))
                self.assertTrue(predicate())
            with self.subTest(outcome=outcome), mock.patch.object(cli, "verify_tests", return_value={}), \
                    mock.patch.object(cli, "backend", return_value=api), mock.patch.object(cli, "wait_until", side_effect=wait):
                if outcome == "ready":
                    cli.start(self.store, self.store.base / "profile.json", "s01")
                    self.assertEqual(ctx.supervisor.owned.launch.call_count, 2)
                    api.network_ready.assert_called_once()
                else:
                    with self.assertRaisesRegex(RuntimeError, "bounded wait|service setup failed"):
                        cli.start(self.store, self.store.base / "profile.json", "s01")
                    self.assertEqual(ctx.supervisor.owned.launch.call_count, 1)
                    api.network_ready.assert_not_called()
                    self.assertFalse((self.store.run(self.store.current()) / "cells/s01").exists())

    def test_invoked_closed_cell_is_not_replayed_after_host_error(self):
        path = self.owner("s01", at=time.time())
        self.store.write(path / "closed.json", dict(worker_exit=1))
        self.store.write(self.out / "cells/s01/health-live.json", dict(health=dict(upgradeStarts=1, upgradeEnds=1)))
        self.store.write(self.out / "cells/s01/status.json", dict(result="CELL_INCOMPLETE"))
        self.store.write(self.store.base / "current.json", dict(run="fixture"))
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend") as factory:
            result = cli.start(self.store, self.store.base / "profile.json", "s01")
        self.assertEqual(result["result"], "CELL_INCOMPLETE")
        factory.assert_not_called()

    def test_existing_unresolved_cell_prevents_new_service(self):
        self.owner("s02", at=100)
        self.store.write(self.store.base / "current.json", dict(run="fixture"))
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend") as factory:
            with self.assertRaisesRegex(RuntimeError, "uncertain cell"):
                cli.start(self.store, self.store.base / "profile.json", "s01")
        factory.assert_not_called()

    def test_idle_retirement_rejects_completed_or_uncertain_work(self):
        value = dict(health=dict(healthy=True, lost=0, error=None, upgradeStarts=0, upgradeEnds=0, outcome=None), snapshots=[])
        self.assertTrue(backend.idle_capture(value))
        for key, replacement in (("healthy", False), ("lost", 1), ("error", "lost"), ("upgradeStarts", 1),
                                  ("upgradeEnds", 1), ("outcome", "completed")):
            self.assertFalse(backend.idle_capture(dict(value, health=dict(value["health"], **{key: replacement}))))
        self.assertFalse(backend.idle_capture(dict(value, snapshots=["snapshot-1.jsonl"])))

    def test_only_known_configurations_can_be_replaced(self):
        raw = b"owned config"
        backend.require_owned_config(raw, {hashlib.sha256(raw).hexdigest()})
        backend.require_owned_config(None, set())
        with self.assertRaises(RuntimeError):
            backend.require_owned_config(b"someone else's config", set())

    def test_adapter_uses_correct_name_and_retirement_before_original_guard(self):
        calls = []
        api = object.__new__(backend.Backend)
        api.group = "screen"
        original_network = object()
        def raw_loader(name, path):
            return types.SimpleNamespace(FILENAME="old.etu", network=original_network,
                release_old=lambda *args: calls.append("original-guard"), browser_control=lambda *args: None,
                observe_app=lambda *args: None)
        api.legacy = {"named": {"raw_load": raw_loader}, "entry": {"live": {"retry": {"transient": lambda error: False}}},
                      "verify_http": lambda *args, **kwargs: {"verified": True}}
        api.retire_initial = lambda *args: calls.append("retire")
        api.profile = {}
        api.served_name = "prefix-screen-full.etu"
        c = types.SimpleNamespace(HERE=ROOT / ".cache/p34-next")
        consumer = api.phone(c, "fixture")
        producer = api.phone(c, "producer", producer=True)
        self.assertEqual(consumer.FILENAME, "prefix-screen-full.etu")
        self.assertEqual(producer.FILENAME, consumer.FILENAME)
        self.assertIs(producer.network, original_network)
        consumer.release_old(c, None, self.out)
        self.assertEqual(calls, ["retire", "original-guard"])
        # The served name is never inlined: a comparison group must reach the adapter.
        api.served_name = "prefix-n03probe-full.etu"
        self.assertEqual(api.phone(c, "fixture").FILENAME, "prefix-n03probe-full.etu")

    def group_plan(self, group="n03-b"):
        return dict(root=str(ROOT), profile={}, sources=[], bindings={},
            cells={key: list(value) for key, value in cli.CELLS.items()},
            native_authority={}, group=group, served={"sha256": "a" * 64}, served_name="prefix-n03probe-full.etu",
            receiver_version=30215, target_version=30216)

    def group_context(self, api, plan):
        # The context always reports the *currently selected* group; drift is injected into
        # the archived plan, which is what validate() compares against.
        return types.SimpleNamespace(read=lambda path: plan, sources=lambda: [], bindings={},
            native_authority=lambda: {}, group=api.group, screen=api.served,
            receiver_version=api.receiver_version, target_version=api.target_version)

    def test_validate_binds_the_comparison_group_and_its_served_package(self):
        api = object.__new__(backend.Backend)
        api.root = ROOT
        api.profile_path = self.store.base / "profile.json"
        api.preflight = lambda *args: None
        api.group, api.served_name, api.receiver_version, api.target_version = "n03-b", "prefix-n03probe-full.etu", 30215, 30216
        api.served, api.profile = {"sha256": "a" * 64}, {}
        plan = self.group_plan()
        self.store.write(api.profile_path, {})
        plan["profile"] = cli.record(api.profile_path)
        self.assertIsNone(api.validate(self.group_context(api, plan), self.out))
        for key, value in (("group", "n03-a"), ("served", {"sha256": "b" * 64}), ("served_name", "other.etu"),
                           ("receiver_version", 30214), ("target_version", 30215)):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "comparison group or served package changed"):
                api.validate(self.group_context(api, dict(plan, **{key: value})), self.out)
        # A plan written before comparison groups existed can only be the retained group.
        legacy = dict(plan, served_name="prefix-screen-full.etu", receiver_version=30214, target_version=30215)
        legacy.pop("group")
        api.group, api.served_name, api.receiver_version, api.target_version = "screen", "prefix-screen-full.etu", 30214, 30215
        self.assertIsNone(api.validate(self.group_context(api, legacy), self.out))

    def served_context(self, *, group, name, version, target_sha, package, actions=None):
        api = object.__new__(backend.Backend)
        api.group, api.served_name, api.target_version = group, name, version
        api.served = {"sha256": hashlib.sha256(package).hexdigest(), "bytes": len(package)}
        c = types.SimpleNamespace(service=types.SimpleNamespace(DEVICE_MODEL="e-track-at32f435",
                LATEST_PATH="/api/public/firmware/latest"), target_version=version,
            target={"sha256": target_sha}, screen=api.served, screen_bytes=package, HERE=ROOT,
            action=lambda *args, **values: actions.append((args, values)))
        return api, c

    def served_metadata(self, c, *, version, name, target_sha, package, origin, asset=None):
        return dict(schemaVersion=2, updateAvailable=True, errorCode=None, appId="trace",
            deviceModel=c.service.DEVICE_MODEL, channel="stable", transport="ble", versionCode=version,
            targetImageSha256=target_sha, requestId="req", releaseId="rel", releaseTag="tag", versionName="1.0",
            targetHardware="e-track-at32f435", minAppVersionCode=0,
            asset=asset if asset is not None else dict(assetId="asset", kind="full", fileName=name,
                sha256=hashlib.sha256(package).hexdigest(), sizeBytes=len(package), baseVersionCode=0,
                baseImageSha256=None, expiresAt=1, downloadUrl=origin + "/download/" + name))

    def test_served_metadata_checks_follow_the_group_not_the_screen_literals(self):
        probe, screen = b"probe", b"screen"
        fixtures = dict(screen=("prefix-screen-full.etu", 30215, "1" * 64, screen),
            **{"n03-%s" % arm: ("prefix-n03probe-full.etu", 30216, "2" * 64, probe) for arm in ("a", "b")})
        origin = "https://fixture.trycloudflare.com"
        for group, (name, version, target_sha, package) in fixtures.items():
            other_name, other_version, other_sha, other_package = fixtures["screen" if group != "screen" else "n03-a"]
            api, c = self.served_context(group=group, name=name, version=version, target_sha=target_sha,
                package=package)
            metadata = self.served_metadata(c, version=version, name=name, target_sha=target_sha,
                package=package, origin=origin)
            with self.subTest(group=group):
                self.assertIsNone(api.validate_served(c, metadata, origin))
            changes = dict(version=dict(versionCode=other_version), target=dict(targetImageSha256=other_sha),
                name=dict(asset=dict(metadata["asset"], fileName=other_name)),
                package=dict(asset=dict(metadata["asset"], sha256=hashlib.sha256(other_package).hexdigest(),
                                         sizeBytes=len(other_package))),
                origin=dict(asset=dict(metadata["asset"], downloadUrl="https://other.trycloudflare.com/x-full.etu")),
                gate=dict(updateAvailable=False), base=dict(asset=dict(metadata["asset"], baseVersionCode=1)),
                variant=dict(asset=dict(metadata["asset"], kind="delta")))
            for label, change in changes.items():
                with self.subTest(group=group, change=label), \
                        self.assertRaisesRegex(RuntimeError, "release metadata drift|filename does not match|full asset metadata drift|origin/security differs|App version gate drift|update"):
                    api.validate_served(c, dict(metadata, **change), origin)

    def test_readiness_keeps_the_frozen_dns_window_and_the_group_bound_strict_half(self):
        package, origin = b"probe-package", "https://fixture.trycloudflare.com"
        calls, actions = [], []
        api, c = self.served_context(group="n03-a", name="prefix-n03probe-full.etu", version=30216,
            target_sha="2" * 64, package=package, actions=actions)
        metadata = self.served_metadata(c, version=30216, name=api.served_name, target_sha="2" * 64,
            package=package, origin=origin)
        class Response:
            def __init__(self, data): self.data = data
            def read(self, limit): return self.data[:limit]
            def __enter__(self): return self
            def __exit__(self, *args): return False
        class Opener:
            def open(self, url, timeout=None):
                calls.append(url)
                body = json.dumps(metadata).encode() if c.service.LATEST_PATH in url else package
                return Response(body)
        api.legacy = dict(resolve=lambda c, host: ["192.0.2.1"],
            wait_dns=lambda check, record: (check(), record(dict(result="RESOLVED", addresses=["192.0.2.1"]))),
            named=dict(raw_load=lambda name, path: types.SimpleNamespace(latest_query=lambda c: dict(appId="trace"))))
        with mock.patch.object(backend.urllib.request, "build_opener", lambda *args: Opener()):
            value = api.verify_served(c, origin)
        self.assertEqual([entry[0][0] for entry in actions], ["dns-readiness"])
        self.assertEqual(value["bytes"], len(package))
        self.assertEqual(value["sha256"], hashlib.sha256(package).hexdigest())
        self.assertEqual(value["file_name"], "prefix-n03probe-full.etu")
        self.assertEqual(calls, [origin + c.service.LATEST_PATH + "?appId=trace", origin + "/download/" + api.served_name])
        # The DNS window is before any fetch, and an unbound origin never reaches either half.
        calls.clear()
        with self.assertRaisesRegex(RuntimeError, "unbound HTTPS origin"):
            api.verify_served(c, "http://127.0.0.1:8080")
        self.assertEqual(calls, [])
        # Byte drift of the served package is still refused after the metadata checks pass.
        class Truncated(Opener):
            def open(self, url, timeout=None):
                calls.append(url)
                return Response(package[:-1] if c.service.LATEST_PATH not in url else json.dumps(metadata).encode())
        with mock.patch.object(backend.urllib.request, "build_opener", lambda *args: Truncated()), \
                self.assertRaisesRegex(RuntimeError, "HTTPS package bytes differ"):
            api.verify_served(c, origin)

    def test_phone_binds_the_group_bound_readiness_check(self):
        api = object.__new__(backend.Backend)
        api.group, api.served_name, api.target_version = "n03-a", "prefix-n03probe-full.etu", 30216
        verified, actions = [], []
        api.verify_served = lambda c, origin, **options: verified.append((origin, options)) or {"bytes": 1}
        phone = types.SimpleNamespace(FILENAME="", experiment=None)
        api.legacy = dict(named=dict(raw_load=lambda name, path: phone), entry=dict(live=dict(
            retry=dict(transient=lambda error: False))))
        c = types.SimpleNamespace(HERE=ROOT, envelope={}, action=lambda *args, **values: actions.append((args, values)))
        bound = api.phone(c, "fixture", producer=True)
        self.assertEqual(bound.FILENAME, "prefix-n03probe-full.etu")
        self.assertIs(bound.verify_http.__kwdefaults__["proxy"], False)
        self.assertEqual(bound.verify_http(c, "https://fixture.trycloudflare.com"), {"bytes": 1})
        self.assertEqual([(args, values["attempt"], values["result"]) for args, values in actions],
                         [(("https-readiness", "verified"), 1, "VERIFIED")])
        self.assertEqual(verified, [("https://fixture.trycloudflare.com", {"proxy": False})])

    def readiness(self, outcomes, transient=lambda error: False):
        clock, records, sleeps = [0.0], [], []
        def check():
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds
        try:
            return backend.wait_ready(check, records.append, transient, clock=lambda: clock[0], sleep=sleep), records, sleeps
        except Exception as error:
            return error, records, sleeps

    def http_error(self, status):
        return backend.urllib.error.HTTPError("https://fixture.trycloudflare.com", status, "fixture", None, None)

    def test_readiness_retries_tunnel_530_inside_the_frozen_offsets(self):
        value, records, sleeps = self.readiness([self.http_error(530), self.http_error(530), {"bytes": 1}])
        self.assertEqual(value, {"bytes": 1})
        self.assertEqual([(item["attempt"], item["result"], item.get("http_status")) for item in records],
                         [(1, "FAILED", 530), (2, "FAILED", 530), (3, "VERIFIED", None)])
        self.assertEqual(sleeps, [0, 15, 30])

    def test_readiness_retries_socket_read_timeout_but_remains_bounded(self):
        value, records, sleeps = self.readiness([TimeoutError("read timed out"), {"bytes": 1}])
        self.assertEqual(value, {"bytes": 1})
        self.assertEqual(sleeps, [0, 15])
        self.assertEqual(records[0]["error"], "TimeoutError")
        failure = TimeoutError("still timed out")
        error, records, _ = self.readiness([failure] * 4)
        self.assertIs(error, failure)
        self.assertEqual(len(records), 4)

    def test_readiness_is_bounded_and_reraises_the_last_transient_failure(self):
        error, records, sleeps = self.readiness([self.http_error(530)] * 4)
        self.assertIsInstance(error, backend.urllib.error.HTTPError)
        self.assertEqual(len(records), len(backend.READY_OFFSETS))
        self.assertEqual(sum(sleeps), backend.READY_OFFSETS[-1])

    def test_readiness_does_not_retry_strict_or_unclassified_failures(self):
        for failure in (RuntimeError("HTTPS package bytes differ"), self.http_error(404), self.http_error(500)):
            error, records, _ = self.readiness([failure, {"bytes": 1}])
            self.assertIs(error, failure)
            self.assertEqual(len(records), 1)
        # The frozen classifier still owns the other transient statuses and TLS resets.
        value, records, _ = self.readiness([self.http_error(503), {"bytes": 1}],
                                           transient=lambda error: getattr(error, "code", None) == 503)
        self.assertEqual((value, len(records)), ({"bytes": 1}, 2))

    def test_phone_capture_reports_the_read_only_store_count(self):
        api = object.__new__(backend.Backend)
        api.root, api.profile = ROOT, {}
        names = ["1790408469659%02d-6159b74cb295b6c55e83818d" % index for index in range(7)]
        health = json.dumps(dict(schema=1, captureId=names[-1].split("-")[1], records=10, bytes=100,
            producerLines=9, upgradeStarts=1, upgradeEnds=1, outcome="not-completed", lost=0, error=None,
            healthy=True)).encode()
        p = types.SimpleNamespace(command=lambda args, check=True: "\n".join(names) + "\n" if args[-1].endswith("p34-observations") else "",
            file_bytes=lambda pkg, path, limit: health)
        phone = types.SimpleNamespace(exists=lambda p, pkg, path: True)
        saved = {}
        c = types.SimpleNamespace(PKG="fixture.pkg", TARGET="02:00:00:00:00:01", OUT=self.out, now=lambda: "now",
            raw=lambda path, data: dict(path=str(path), bytes=len(data), sha256="0" * 64),
            save=lambda path, value: saved.update(value), envelope=types.SimpleNamespace(MAX_BYTES=1 << 20))
        value = api.capture(c, p, phone, self.out / "app")
        self.assertEqual((value["result"], value["pid"], value["capture_directories"]), ("APP_INSPECTED", None, 7))
        self.assertEqual(value["snapshots"], [])
        self.assertFalse(value["safe_idle"] or backend.idle_capture(value))
        self.assertEqual(saved["capture_directories"], 7)

    def capture_health(self, *, starts=1, ends=1, outcome="not-completed", records=10):
        return json.dumps(dict(schema=1, captureId="fixture", time="2026-01-01T00:00:00Z", records=records,
            bytes=100, producerLines=9, upgradeStarts=starts, upgradeEnds=ends, outcome=outcome,
            lost=0, error=None, healthy=True)).encode()

    def fake_observation_store(self, entries, *, pid=""):
        """Fake App observation store; only the calls the report/apply path makes."""
        class Fake:
            def __init__(self):
                self.entries, self.pid, self.commands = entries, pid, []
            def command(self, args, check=True):
                self.commands.append(list(args))
                if args[1] == "pidof":
                    return (self.pid + "\n") if self.pid else ""
                path = args[-1]
                if args[3] == "readlink":
                    return "/data/user/0/fixture.pkg" + ("" if path == "." else "/" + path)
                if path == "files/p34-observations":
                    return "\n".join(sorted(self.entries)) + "\n"
                name, _, leaf = path[len("files/p34-observations/"):].partition("/")
                if args[3] == "rm":
                    self.entries.pop(name)
                    return ""
                return "\n".join(["health.json"] + sorted(self.entries[name]["payloads"])) + "\n"
            def file_bytes(self, pkg, path, limit):
                name, _, leaf = path[len("files/p34-observations/"):].partition("/")
                return self.entries[name]["health"] if leaf == "health.json" else self.entries[name]["payloads"][leaf]
        return Fake()

    def store_context(self):
        return types.SimpleNamespace(PKG="fixture.pkg", envelope=types.SimpleNamespace(MAX_BYTES=1 << 20),
            now=lambda: "now", checked=self.store.checked, raw=self.store.raw, save=self.store.write,
            load=lambda name, path: types.SimpleNamespace(device_lock=nullcontext))

    def store_api(self, fake):
        api = object.__new__(backend.Backend)
        api.root, api.store, api.profile, api.profile_path = ROOT, self.store, {}, self.store.base / "profile.json"
        api.phone = lambda c, name, producer=False: types.SimpleNamespace(usb=lambda c, out: nullcontext(fake))
        return api

    def preserve_payload(self, label, data):
        """Host copy under one of the evidence leaves the preservation check actually globs."""
        run = "20260101T000000-" + uuid.uuid4().hex[:8]
        self.store.raw(self.store.base / "runs" / run / "prestart-phone" / "app" / label, data)

    def test_store_report_only_offers_preserved_terminal_captures(self):
        idle, kept, free = ["1790403650899715-" + "1" * 24, "1790406048523862-" + "2" * 24,
                            "1790408469659690-" + "3" * 24]
        entries = {idle: dict(health=self.capture_health(starts=0, ends=0, outcome=None, records=16),
                              payloads={"events.jsonl": b"idle\n"}),
                   kept: dict(health=self.capture_health(),
                              payloads={"events.jsonl": b"kept\n", "snapshot-1.jsonl": b"snap-kept\n"}),
                   free: dict(health=self.capture_health(),
                              payloads={"events.jsonl": b"free\n", "snapshot-1.jsonl": b"snap-free\n"})}
        self.preserve_payload("events.jsonl", b"idle\n")
        self.preserve_payload("events.jsonl", b"kept\n")
        self.preserve_payload("snapshot-1.jsonl", b"snap-kept\n")
        fake = self.fake_observation_store(entries)
        report = self.store_api(fake).store_report(self.store_context(), fake, self.out / "prune")
        self.assertEqual((report["result"], report["capture_directories"], report["store_limit"]), ("STORE_INSPECTED", 3, 8))
        self.assertEqual([item["name"] for item in report["directories"] if item["eligible"]], [kept])
        states = {item["name"]: item for item in report["directories"]}
        self.assertEqual(states[idle]["state"], "idle")
        self.assertEqual(states[kept]["state"], "terminal-not-completed")
        self.assertEqual(states[free]["reasons"], ["no host copy of events.jsonl", "no host copy of snapshot-1.jsonl"])
        self.assertEqual(states[idle]["reasons"], ["capture is not a terminal not-completed transfer"])

    def test_prune_deletes_only_the_named_preserved_terminal_captures(self):
        idle, first, second = ["1790403650899715-" + "1" * 24, "1790406048523862-" + "2" * 24,
                               "1790408469659690-" + "3" * 24]
        payloads = {first: {"events.jsonl": b"first\n", "snapshot-1.jsonl": b"snap-first\n"},
                    second: {"events.jsonl": b"second\n", "snapshot-1.jsonl": b"snap-second\n"}}
        for name, items in payloads.items():
            for label, data in items.items():
                self.preserve_payload(label, data)
        entries = {idle: dict(health=self.capture_health(starts=0, ends=0, outcome=None, records=16),
                              payloads={"events.jsonl": b"idle\n"}),
                   **{name: dict(health=self.capture_health(), payloads=data) for name, data in payloads.items()}}
        fake = self.fake_observation_store(entries)
        api = self.store_api(fake)
        with mock.patch.object(cli, "verify_tests", return_value={}):
            result = api.prune(self.store_context(), self.out / "prune", [first, second])
        self.assertEqual((result["result"], result["device_operations"], result["removed"]), ("PRUNED", 2, [first, second]))
        self.assertEqual(result["remaining"], [idle])
        self.assertEqual(result["remaining_state"], "idle")
        self.assertEqual([args[-1] for args in fake.commands if len(args) > 3 and args[3] == "rm"],
                         ["files/p34-observations/" + first, "files/p34-observations/" + second])
        self.assertEqual(self.store.read(self.out / "prune/prune-intent.json")["eligible"], [first, second])

    def test_prune_without_names_only_reports_the_store(self):
        idle, first = ["1790403650899715-" + "1" * 24, "1790406048523862-" + "2" * 24]
        entries = {idle: dict(health=self.capture_health(starts=0, ends=0, outcome=None, records=16),
                              payloads={"events.jsonl": b"idle\n"}),
                   first: dict(health=self.capture_health(), payloads={"events.jsonl": b"first\n"})}
        fake = self.fake_observation_store(entries)
        with mock.patch.object(cli, "verify_tests", return_value={}):
            result = self.store_api(fake).prune(self.store_context(), self.out / "report", [])
        self.assertEqual((result["result"], result["device_operations"], result["eligible"]), ("STORE_REPORTED", 0, []))
        self.assertEqual((result["before"], result["remaining"], result["remaining_state"]), ([idle, first], [idle, first], "terminal-not-completed"))
        self.assertEqual([args for args in fake.commands if len(args) > 3 and args[3] == "rm"], [])
        self.assertTrue((self.out / "report/store-report.json").exists())

    def test_prune_refuses_unsafe_unpreserved_or_invalid_requests(self):
        idle, first, second = ["1790403650899715-" + "1" * 24, "1790406048523862-" + "2" * 24,
                               "1790408469659690-" + "3" * 24]
        entries = {idle: dict(health=self.capture_health(starts=0, ends=0, outcome=None, records=16),
                              payloads={"events.jsonl": b"idle\n"}),
                   first: dict(health=self.capture_health(), payloads={"events.jsonl": b"first\n"}),
                   second: dict(health=self.capture_health(), payloads={"events.jsonl": b"second\n"})}
        self.preserve_payload("events.jsonl", b"first\n")
        cases = (
            ([idle], "", "requested directories are not all terminal captures preserved host-side"),
            ([second], "", "requested directories are not all terminal captures preserved host-side"),
            ([first, "1799999999999999-" + "9" * 24], "", "requested directories are not all terminal captures preserved host-side"),
            ([first], "1234", "stop the App before freeing observation directories"),
            (["../p34-observations"], "", "invalid capture directory name"),
        )
        for index, (requested, pid, message) in enumerate(cases):
            with self.subTest(requested=requested), self.assertRaisesRegex(RuntimeError, message):
                api = self.store_api(self.fake_observation_store(copy.deepcopy(entries), pid=pid))
                with mock.patch.object(cli, "verify_tests", return_value={}):
                    api.prune(self.store_context(), self.out / ("prune-%d" % index), requested)
        all_eligible = {name: dict(health=self.capture_health(), payloads={"events.jsonl": name.encode()})
                        for name in (idle, first, second)}
        for entry in all_eligible.values():
            self.preserve_payload("events.jsonl", entry["payloads"]["events.jsonl"])
        with self.subTest(requested="everything"), self.assertRaisesRegex(RuntimeError, "needs at least one capture directory"):
            api = self.store_api(self.fake_observation_store(all_eligible))
            with mock.patch.object(cli, "verify_tests", return_value={}):
                api.prune(self.store_context(), self.out / "prune-all", [idle, first, second])

    def test_prune_flag_belongs_to_the_prune_command(self):
        name = "1790408469659690-" + "3" * 24
        with self.assertRaisesRegex(RuntimeError, "--delete is only valid for prune"):
            cli.main(["--root", str(ROOT), "--delete", name, "status"])
        with self.assertRaisesRegex(RuntimeError, "--group selects a new session"):
            cli.main(["--root", str(ROOT), "--group", "n03-b", "prune"])

    def test_group_flag_is_only_accepted_for_new_session_commands(self):
        for command in ("status", "collect", "stop", "test", "doctor"):
            with self.subTest(command=command), self.assertRaisesRegex(RuntimeError, "--group selects a new session"):
                cli.main(["--root", str(ROOT), "--group", "n03-b", command])
        with mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            cli.main(["--root", str(ROOT), "--group", "n03-c", "identity"])

    def test_backend_passes_the_selected_group_with_the_profile(self):
        seen = {}
        module = types.SimpleNamespace(Backend=lambda store, path, profile, group: seen.update(
            store=store, path=path, profile=profile, group=group))
        bootstrap = ROOT / ".cache/p34-next/prefix_dns_window.py"
        profile_path = self.store.base / "profile.json"
        self.store.write(profile_path, dict(schema=1, bootstrap=cli.record(bootstrap)))
        with mock.patch.object(cli, "load_module", return_value=module):
            cli.backend(self.store, profile_path, "n03-a")
        self.assertEqual((seen["group"], seen["path"]), ("n03-a", profile_path))

    def test_identity_checkpoint_only_reads_and_fails_closed(self):
        def context_module(name, path):
            return (types.SimpleNamespace(device_lock=nullcontext) if path.name == "repeat_cycle.py"
                    else types.SimpleNamespace(Mcu=mock.Mock(return_value=fake)))
        fake, seen = mock.Mock(), {}
        fake.open.side_effect = RuntimeError("unexpected App/Boot image")
        fake.close.return_value = dict(retained_verified=False)
        context = types.SimpleNamespace(receiver_image_sha="c" * 64, environment=lambda: {},
            HERE=ROOT / ".cache/p34-next", load=context_module)
        impl = types.SimpleNamespace(receiver_version=30215, target_version=30216, context=lambda out: context)
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend", return_value=impl):
            result = cli.identity(self.store, self.store.base / "profile.json", "n03-b")
        self.assertEqual(result["result"], "IDENTITY_FAILED")
        self.assertEqual(result["error"], "RuntimeError")
        self.assertEqual(result["expected_image_sha"], "c" * 64)
        self.assertTrue(result["no_reset"] and result["no_halt"] and result["no_flash"] and
                        result["no_tuning"] and result["no_transfer"])
        fake.close.assert_called_once_with(restore=False)
        fake.tune_rate.assert_not_called()
        self.assertEqual(self.store.read(Path(result["evidence"]) / "result.json")["result"], "IDENTITY_FAILED")

    def test_identity_checkpoint_verifies_a_matching_receiver(self):
        fake = mock.Mock()
        fake.open.return_value = dict()
        fake.result = dict(initial_identity={"app": {"sha256": "c" * 64}}, initial_status=dict(baud=460800))
        fake.sample.return_value = {"time": "now"}
        fake.close.return_value = dict(retained_verified=True)
        def context_module(name, path):
            return (types.SimpleNamespace(device_lock=nullcontext) if path.name == "repeat_cycle.py"
                    else types.SimpleNamespace(Mcu=mock.Mock(return_value=fake)))
        context = types.SimpleNamespace(receiver_image_sha="c" * 64, environment=lambda: {},
            HERE=ROOT / ".cache/p34-next", load=context_module)
        impl = types.SimpleNamespace(receiver_version=30215, target_version=30216, context=lambda out: context)
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend", return_value=impl):
            result = cli.identity(self.store, self.store.base / "profile.json", "n03-b")
        self.assertEqual(result["result"], "IDENTITY_VERIFIED")
        self.assertEqual(result["controller"]["baud"], 460800)
        self.assertEqual(result["state"], {"time": "now"})

    def test_refresh_recognizes_prior_provisioned_config_not_arbitrary_files(self):
        api = object.__new__(backend.Backend)
        api.store, api.root, api.profile = self.store, ROOT, {}
        api.profile_path = self.store.base / "profile.json"
        self.store.write(api.profile_path, {"schema": 1, "fixture": True})
        context = types.SimpleNamespace(OUT=self.store.run("next"), bindings={"fixture": True})
        self.store.write(self.out / "plan.json", dict(root=str(ROOT), profile=cli.record(api.profile_path), bindings=context.bindings))
        path = self.out / "cells/s01/runtime-config.json"
        actual = self.store.raw(path, b"owned previous endpoint")
        self.assertNotIn(actual["sha256"], api.known_configs(context))
        self.store.write(path.parent / "provision.json", {"config": actual})
        self.assertIn(actual["sha256"], api.known_configs(context))
        changed = dict(actual, sha256="0" * 64)
        self.store.write(path.parent / "provision.json", {"config": changed}, replace=True)
        with self.assertRaisesRegex(RuntimeError, "receipt changed"):
            api.known_configs(context)

    def test_runtime_binding_checks_every_repeated_stamp(self):
        messages = [row["message"] for row in observation_tests.prefix_rows() if row.get("kind") == "line"]
        original = observation_tests.m.experiment_record(messages)
        expected = {key: value for key, value in original.items() if key not in ("configSha256", "endpointHost", "deviceAddress")}
        expected.update(target=observation_tests.TARGET, firmwareLatestUrl="https://fixture.example/latest")
        repeated = "\n".join(messages + ["OTA_EXPERIMENT " + json.dumps(original)])
        self.assertEqual(backend.verify_experiment(observation_tests.m, repeated, expected, "e" * 64), original)
        with self.assertRaisesRegex(RuntimeError, "runtime config differs"):
            backend.verify_experiment(observation_tests.m, repeated, expected, "f" * 64)
        with self.assertRaisesRegex(RuntimeError, "runtime config differs"):
            backend.verify_experiment(observation_tests.m, repeated, dict(expected, requestedBaud=921600), "e" * 64)

    def test_offline_collection_does_not_inspect_or_connect(self):
        api = object.__new__(backend.Backend)
        api.group = "screen"
        api.analyze = mock.Mock(return_value={"result": "APP_PREFIX_VERIFIED"})
        api.inspect = mock.Mock(side_effect=AssertionError("device inspection"))
        result = api.collect(None, self.out, "s01", offline=True)
        self.assertEqual(result["result"], "APP_PREFIX_VERIFIED")
        api.analyze.assert_called_once_with(None, self.out, "s01")

    def terminal(self):
        keys = ("state", "session_id", "next_session_id", "expected_seq", "total_len", "package_sha256",
                "target_vcode", "pkg_kind", "durable_off", "segment_bitmap", "resumed", "complete",
                "last_ack_cmd", "last_ack_seq", "receiver", "isr_active", "parser_bad_frames")
        return dict(session=dict.fromkeys(keys, 0), profile_raw=dict(sha256="a" * 64), tick=100)

    def test_readback_requires_the_same_terminal_generation(self):
        previous = self.terminal()
        live = dict(previous, tick=101)
        backend.same_terminal(live, previous)
        for key in ("next_session_id", "durable_off", "last_ack_seq", "state"):
            changed = copy.deepcopy(live)
            changed["session"][key] += 1
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "terminal changed"):
                backend.same_terminal(changed, previous)
        for changed in (dict(live, tick=100), dict(live, tick=99), dict(live, profile_raw=dict(sha256="b" * 64))):
            with self.assertRaisesRegex(RuntimeError, "terminal changed"):
                backend.same_terminal(changed, previous)

    def test_readback_worker_only_reads_and_closes_without_tuning(self):
        api = object.__new__(backend.Backend)
        api.store, api.root = self.store, ROOT
        name = "1790000000000000000"
        destination = self.out / "analysis" / name
        previous = self.terminal()
        live = dict(previous, tick=101)
        closure_path = self.out / "cells/s01/mcu/closure.json"
        self.store.write(closure_path, dict(final_state=previous))
        self.store.write(destination / "result.json", dict(cell="s01", mcu_closure=cli.record(closure_path), prefix=dict(prefixBytes=32768)))
        self.store.write(destination / "readback-plan.json", dict(sources=[], bindings={}, analysis=cli.record(destination / "result.json")))
        fake = mock.Mock()
        fake.sample.return_value = fake.journal.return_value = live
        fake.close.return_value = dict(retained_verified=True)
        self.store.raw(destination / "readback/reconciled-journal.bin", b"journal fixture")
        self.store.raw(destination / "readback/reconciled-prefix.bin", b"prefix fixture")
        helper = types.SimpleNamespace(Mcu=mock.Mock(return_value=fake))
        def module(name, path):
            return types.SimpleNamespace(device_lock=nullcontext) if path.name == "repeat_cycle.py" else helper
        c = types.SimpleNamespace(read=self.store.read, save=self.store.write, now=cli.now, bindings={}, sources=lambda: [],
            HERE=ROOT / ".cache/p34-next", host=types.SimpleNamespace(), environment=lambda: {}, load=module, screen={})
        self.assertEqual(api.readback_worker(c, self.out, "s01", name), 0)
        fake.journal.assert_called_once_with("reconciled", {}, 32768)
        fake.close.assert_called_once_with(restore=False)
        fake.tune_rate.assert_not_called()
        self.assertEqual(self.store.read(destination / "readback-result.json")["result"], "PREFIX_READBACK_VERIFIED")

    def test_completed_app_requires_exact_snapshot_and_readback_proof(self):
        api = object.__new__(backend.Backend)
        api.store, api.root = self.store, ROOT
        api.profile_path = self.store.base / "profile.json"
        self.store.write(api.profile_path, dict(schema=1))
        self.store.write(self.out / "plan.json", dict(profile=cli.record(api.profile_path), bindings={}))
        runtime = self.owner("s01")
        self.store.write(runtime / "closed.json", dict(worker_exit=1))
        report = self.out / "analysis/1700000000000000000/result.json"
        readback = report.parent / "readback-result.json"
        self.store.write(report, dict(inputs=dict(config=dict(sha256="a" * 64)),
            summary=dict(rawSha256="b" * 64, pid=123, captureId="fixture")))
        self.store.write(readback, dict(result="PREFIX_READBACK_VERIFIED", closure=dict(retained_verified=True)))
        self.store.write(self.out / "analysis/latest.json", dict(cell="s01", result="PREFIX_RECONCILED",
            report=cli.record(report), readback=cli.record(readback)))
        observed = dict(stable_terminal=True, snapshots=["snapshot-1.jsonl"], config=dict(sha256="a" * 64), pid=123,
            health=dict(captureId="fixture"), snapshot_records={"snapshot-1.jsonl":dict(sha256="b" * 64)})
        c = types.SimpleNamespace(bindings={})
        self.assertIsNotNone(api.completed_capture(c, observed))
        for changed in (dict(observed, pid=124), dict(observed, stable_terminal=False),
                        dict(observed, snapshot_records={"snapshot-1.jsonl":dict(sha256="c" * 64)})):
            self.assertIsNone(api.completed_capture(c, changed))

    def completed_pair(self):
        for name in ("s01", "network"):
            self.store.write(self.out / "runtime" / name / "closed.json", dict(worker_exit=0, forced_termination=False))
        self.store.write(self.store.base / "current.json", dict(run=self.out.name))
        self.store.write(self.out / "cells/s01/health-live.json", dict(health=dict(upgradeStarts=1, upgradeEnds=1)))
        package = dict(sha256="b" * 64, bytes=290856)
        self.store.write(self.out / "plan.json", dict(group="n03-a", receiver_version=30214, target_version=30216,
            served=package, prefix_bytes=32768))
        image = self.store.raw(self.out / "image.bin", b"bound image fixture")
        closure = dict(retained_verified=True, initial_identity=dict(app=image, boot=image),
                       final_identity=dict(app=image, boot=image))
        self.store.write(self.out / "cells/s01/mcu/closure.json", closure)
        journal = self.store.raw(self.out / "journal.bin", b"bound journal fixture")
        prefix = self.store.raw(self.out / "prefix.bin", b"bound prefix fixture")
        inputs = dict(plan=cli.record(self.out / "plan.json"),
            config=self.store.raw(self.out / "runtime-config.json", b"bound config"),
            snapshot=self.store.raw(self.out / "snapshot.jsonl", b"bound snapshot"))
        report = dict(cell="s01", result="APP_PREFIX_VERIFIED", inputs=inputs, retained_verified=True,
            mcu_staging_readback="VERIFIED", profile=dict(clean_counters=True),
            prefix=dict(prefixBytes=32768, sentTotalBytes=32768), journal=journal, staging_prefix=prefix,
            mcu_closure=cli.record(self.out / "cells/s01/mcu/closure.json"),
            summary=dict(rawSha256=inputs["snapshot"]["sha256"], pid=123, captureId="fixture"))
        readback = dict(result="PREFIX_READBACK_VERIFIED", journal=journal, prefix=prefix, closure=closure)
        self.store.write(self.out / "analysis/123/result.json", report)
        self.store.write(self.out / "analysis/123/readback-result.json", readback)
        descriptor = dict(run=self.out.name, cell="s01", plan=inputs["plan"],
            report=cli.record(self.out / "analysis/123/result.json"),
            readback=cli.record(self.out / "analysis/123/readback-result.json"))
        self.store.write(self.out / "analysis/latest.json", dict(result="PREFIX_RECONCILED", cell="s01",
            report=descriptor["report"], readback=descriptor["readback"]))
        profile = dict(schema=1, predecessor=descriptor)
        path = self.store.base / "profile-b.json"
        self.store.write(path, profile)
        return path, profile, package

    def test_paired_predecessor_checks_originals_and_closed_owners(self):
        _, profile, _ = self.completed_pair()
        descriptor = profile["predecessor"]
        value = cli.paired_predecessor(self.store, descriptor)
        self.assertEqual(value["out"], self.out)
        for changed in (None, {}, dict(descriptor, cell="s02"), dict(descriptor, run="other"),
                        dict(descriptor, report=dict(descriptor["report"], sha256="e" * 64))):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                cli.paired_predecessor(self.store, changed)
        image = Path(value["readback"]["closure"]["initial_identity"]["app"]["path"])
        image.write_bytes(b"changed fixture")
        with self.assertRaisesRegex(RuntimeError, "original bytes changed"):
            cli.paired_predecessor(self.store, descriptor)

    def test_pair_transition_never_advances_with_an_unclosed_owner(self):
        _, profile, _ = self.completed_pair()
        self.store.checked(self.out / "runtime/network/closed.json").unlink()
        self.owner(at=time.time())
        with self.assertRaisesRegex(RuntimeError, "owners must be closed"):
            cli.paired_predecessor(self.store, profile["predecessor"])

    def test_pair_transition_rejects_dirty_or_incomplete_measurement(self):
        _, profile, _ = self.completed_pair()
        descriptor = profile["predecessor"]
        path = Path(descriptor["report"]["path"])
        original = self.store.read(path)
        for key in ("result", "retained_verified", "mcu_staging_readback", "profile", "prefix"):
            value = copy.deepcopy(original)
            if key == "profile": value[key]["clean_counters"] = False
            elif key == "prefix": value[key]["sentTotalBytes"] += 128
            elif key == "retained_verified": value[key] = False
            else: value[key] = "NOT_VERIFIED"
            self.store.write(path, value, replace=True)
            changed = dict(descriptor, report=cli.record(path))
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "not a clean, reconciled"):
                cli.paired_predecessor(self.store, changed)

    def test_closed_a_can_advance_to_b_but_not_replay_a_or_change_cell(self):
        path, _, _ = self.completed_pair()
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend") as factory:
            value = cli.start(self.store, path, "s01", "n03-a")
            self.assertEqual(value["result"], "PREFIX_RECONCILED")
            factory.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "same cell"):
                cli.start(self.store, path, "s02", "n03-b")
            factory.assert_not_called()
            factory.side_effect = RuntimeError("B preparation boundary")
            with self.assertRaisesRegex(RuntimeError, "B preparation boundary"):
                cli.start(self.store, path, "s01", "n03-b")
            factory.assert_called_once_with(self.store, path, "n03-b")
        self.assertEqual(self.store.current(), self.out.name)
        self.assertFalse((self.store.base / "command.lock").exists())

    def test_b_only_retires_the_explicit_a_snapshot_and_same_package(self):
        path, profile, package = self.completed_pair()
        api = object.__new__(backend.Backend)
        api.store, api.root, api.profile_path, api.profile, api.group = self.store, ROOT, path, profile, "n03-b"
        c = types.SimpleNamespace(screen=package, receiver_version=30215, target_version=30216, bindings={})
        report = self.store.read(profile["predecessor"]["report"]["path"])
        observed = dict(stable_terminal=True, snapshots=["snapshot-1.jsonl"], config=report["inputs"]["config"],
            snapshot_records={"snapshot-1.jsonl":report["inputs"]["snapshot"]}, pid=123, health=dict(captureId="fixture"))
        self.assertEqual(api.completed_capture(c, observed), profile["predecessor"]["report"])
        self.assertEqual(api.completed_capture(c, dict(observed, pid=None, pid_checked_before_after=True)),
                         profile["predecessor"]["report"])
        self.assertIsNone(api.completed_capture(c, dict(observed, pid=None)))
        for change in (dict(pid=124), dict(health=dict(captureId="other")), dict(stable_terminal=False),
                       dict(config=dict(sha256="e" * 64))):
            with self.subTest(change=change):
                self.assertIsNone(api.completed_capture(c, dict(observed, **change)))
        c.screen = dict(package, sha256="e" * 64)
        with self.assertRaisesRegex(RuntimeError, "identical T package"):
            api.completed_capture(c, observed)

    def sampler(self, size, raw=None):
        value = object.__new__(prefix_mcu.Mcu)
        value.out = self.out / ("sampler-%d" % size)
        value.profile = dict(prefix=b"image".hex(), symbols=dict(profile=1, tick=2, sd_ready=3))
        value.receiver = dict(version=30215 if size == 336 else 30214)
        value.layout = dict(session=4, members=dict(size=8), bcb_state=5, confirm_done=6, state_snapped=7)
        value.instrumentation = dict(size=size, phases=tuple(range((size - 96) // 24)))
        value.initial_nvic = None
        value.result = dict(samples={})
        value.link = types.SimpleNamespace(read=lambda address, count: b"image")
        headers = tuple("field%d" % n for n in range(24))
        value.m = types.SimpleNamespace(c=types.SimpleNamespace(APP=0x08010000), HEADERS=headers,
            ERTC_DT20=8, u32=lambda data: struct.unpack("<I", data)[0])
        frozen = raw if raw is not None else struct.pack("<%dI" % (size // 4), *range(size // 4))
        values = {1: frozen, 2: struct.pack("<I", 123), 3: b"\1", 4: b"session!", 5: b"\4",
                  6: b"\1", 7: b"\1", 8: struct.pack("<I", 921600), prefix_mcu.NVIC: bytes(128)}
        value.read = lambda address, count: values[address]
        value.c = types.SimpleNamespace(require=cli.require, now=cli.now, raw=self.store.raw, save=self.store.write,
            record=cli.record, decode_session=lambda raw, layout: dict(raw=raw.hex()))
        return value, frozen, headers

    def test_actual_sampler_uses_the_receivers_bound_profile_size(self):
        for size in (288, 336):
            with self.subTest(size=size):
                sampler, raw, headers = self.sampler(size)
                value = sampler.sample("sample")
                self.assertEqual(value["profile"], dict(zip(headers, range(24))))
                self.assertEqual(value["profile_raw"]["bytes"], size)
                self.assertEqual(Path(value["profile_raw"]["path"]).read_bytes(), raw)
                self.assertEqual(value["tick"], 123)
                self.assertEqual(sampler.result["samples"]["sample"],
                                 cli.record(sampler.out / "samples/sample/state.json"))

    def test_actual_sampler_rejects_a_truncated_or_wrong_profile(self):
        for size, actual in ((288, 336), (336, 288), (336, 332)):
            with self.subTest(size=size, actual=actual):
                sampler, _, _ = self.sampler(size, bytes(actual))
                with self.assertRaises((RuntimeError, struct.error)):
                    sampler.sample("bad")

    def old_journal(self, sha="a" * 64, total=290773):
        raw = bytearray(b"\xff" * 4096)
        etrj = b"ETRJ" + bytes.fromhex(sha) + struct.pack("<I", total)
        raw[0x40:0x6c] = etrj + struct.pack("<I", zlib.crc32(etrj))
        return bytes(raw)

    def fresh_fixture(self, group="n03-a", size=288):
        api = object.__new__(backend.Backend)
        api.store, api.root, api.group = self.store, ROOT, group
        out = self.out / group / "cells/s01"
        old = dict(sha256="a" * 64, bytes=290773)
        headers = ("run", *("field%d" % n for n in range(1, 24)))
        profile = dict(zip(headers, (4, *([0] * 23))))
        profile_raw = struct.pack("<24I", *profile.values()) + bytes(size - 96)
        states = []
        for tag, tick in (("before", 100), ("current", 101)):
            state = self.terminal()
            state["session"].update(durable_off=32768, package_sha256=old["sha256"], total_len=old["bytes"])
            state.update(tick=tick, profile=profile, sd_ready=1, confirm_done=1, state_snapped=1, bcb_state=4,
                profile_raw=self.store.raw(out / tag / "profile.bin", profile_raw),
                session_raw=self.store.raw(out / tag / "session.bin", json.dumps(state["session"]).encode()))
            states.append(state)
        c = types.SimpleNamespace(HERE=ROOT / ".cache/p34-next", load=lambda *args: prefix_mcu,
            screen=dict(sha256="b" * 64, bytes=290856), assets=dict(groups=dict(screen=dict(package=old),
                **{"reset-control":dict(package=dict(sha256="c" * 64, bytes=30000))})),
            n03=dict(groups=dict(receiver=dict(package=dict(sha256="d" * 64, bytes=290996)))),
            raw=self.store.raw, read=self.store.read, save=self.store.write,
            m=types.SimpleNamespace(HEADERS=headers), instrumentation=dict(size=size),
            bindings=dict(layout=dict(members={})), decode_session=lambda raw, layout: json.loads(raw))
        mcu = mock.Mock()
        mcu.sample.side_effect = states
        mcu.read.return_value = self.old_journal()
        return api, c, mcu, out, states

    def test_distinct_journal_requires_known_valid_different_identity(self):
        target = dict(sha256="b" * 64, bytes=290856)
        known = [dict(sha256="a" * 64, bytes=290773)]
        self.assertEqual(backend.distinct_journal(self.old_journal(), target, known), known[0])
        # An installed package's marker is irrelevant to this proof: no old
        # payload or bitmap is reused when the new BEGIN identity differs.
        committed = bytearray(self.old_journal())
        committed[28:32] = struct.pack("<I", 0x434f4d54)
        self.assertEqual(backend.distinct_journal(bytes(committed), target, known), known[0])
        corrupt = bytearray(self.old_journal())
        corrupt[0x68] ^= 1
        for raw in (bytes(corrupt), self.old_journal()[:-1], self.old_journal("b" * 64),
                    self.old_journal("e" * 64), self.old_journal(total=0), self.old_journal(total=290774)):
            with self.subTest(sha=raw[0x44:0x48]), self.assertRaises(RuntimeError):
                backend.distinct_journal(raw, target, known)

    def test_paired_fresh_begin_only_reads_and_preserves_real_nonzero_baseline(self):
        for group, size in (("n03-a", 288), ("n03-b", 336)):
            with self.subTest(group=group):
                api, c, mcu, out, states = self.fresh_fixture(group, size)
                value = api.fresh_begin(c, mcu, out)
                self.assertEqual(value, states[1])
                self.assertEqual(value["session"]["durable_off"], 32768)
                proof = self.store.read(out / "fresh-begin.json")
                self.assertEqual(proof["result"], "DIFFERENT_PACKAGE_BEGIN_REQUIRED")
                self.assertFalse(proof["native_zero_sample"])
                self.assertFalse(proof["new_begin"])
                self.assertFalse(proof["new_abort"])
                self.assertEqual(mcu.method_calls, [mock.call.sample("fresh-begin-before"),
                    mock.call.read(0x90300000, 4096), mock.call.read(0x90300000, 4096),
                    mock.call.sample("fresh-begin-after")])

    def test_fresh_begin_stops_if_journal_changes_without_claiming_readiness(self):
        api, c, mcu, out, _ = self.fresh_fixture()
        mcu.read.side_effect = [self.old_journal(), bytes(4096)]
        with self.assertRaisesRegex(RuntimeError, "journal changed"):
            api.fresh_begin(c, mcu, out)
        self.assertFalse((out / "fresh-begin.json").exists())
        self.assertTrue((out / "mcu/fresh-before-journal.bin").exists())

    def test_fresh_begin_proof_rechecks_original_bytes_and_generation(self):
        api, c, mcu, out, _ = self.fresh_fixture()
        api.fresh_begin(c, mcu, out)
        path = out / "fresh-begin.json"
        original = self.store.read(path)
        for change in ("group", "package", "zero", "run", "tick", "journal"):
            proof = copy.deepcopy(original)
            if change == "group": proof["group"] = "n03-b"
            elif change == "package": proof["package"]["sha256"] = "e" * 64
            elif change == "zero": proof["native_zero_sample"] = True
            elif change == "run": proof["current"]["profile"]["run"] += 1
            elif change == "tick": proof["current"]["tick"] = proof["before"]["tick"]
            else: proof["journal"]["sha256"] = "e" * 64
            self.store.write(path, proof, replace=True)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                api.initial_sample(c, out)
        self.store.write(path, original, replace=True)
        self.assertEqual(api.initial_sample(c, out), original["current"])

    def test_original_browser_or_reused_baseline_still_loads_unchanged(self):
        api = object.__new__(backend.Backend)
        c = types.SimpleNamespace(read=self.store.read)
        self.store.write(self.out / "control/result.json", dict(after={"legacy": 1}))
        self.assertEqual(api.initial_sample(c, self.out), {"legacy": 1})
        self.store.write(self.out / "control-reused.json", dict(current={"legacy": 2}))
        self.assertEqual(api.initial_sample(c, self.out), {"legacy": 2})

    def test_zero_durable_is_original_and_must_precede_any_data(self):
        zero = "OTA_LINK_SAMPLE label=prefix-probe kind=durable us=10 off=0"
        later = "OTA_LINK_SAMPLE label=prefix-probe kind=durable us=20 off=4096"
        data = "OTA_LINK_SAMPLE label=prefix-probe kind=segment_first_send us=15 off=0 len=128"
        self.assertFalse(backend.zero_before_data("\n".join((zero, data, later)))["native_zero_sample"])
        for lines in ((data, zero, later), (later, zero, data), (zero, data, zero), (data, later), (zero,), ()):
            with self.subTest(lines=lines), self.assertRaises(RuntimeError):
                backend.zero_before_data("\n".join(lines))

    def test_paired_adapter_never_falls_back_to_browser_control(self):
        for group in ("screen", "n03-a", "n03-b"):
            with self.subTest(group=group):
                api = object.__new__(backend.Backend)
                api.group, api.served_name, api.profile = group, "prefix-n03probe-full.etu", {}
                api.fresh_begin = mock.Mock(return_value={"new": 1})
                browser = mock.Mock(return_value={"old": 1})
                phone = types.SimpleNamespace(release_old=lambda *args: None, browser_control=browser,
                    observe_app=lambda *args: None)
                api.legacy = dict(named=dict(raw_load=lambda *args: phone))
                c = types.SimpleNamespace(HERE=ROOT)
                bound = api.phone(c, "fixture")
                value = bound.browser_control(c, None, None, self.out, "s01")
                if group == "screen":
                    self.assertEqual(value, {"old": 1})
                    browser.assert_called_once()
                    api.fresh_begin.assert_not_called()
                else:
                    self.assertEqual(value, {"new": 1})
                    browser.assert_not_called()
                    api.fresh_begin.side_effect = RuntimeError("same package")
                    with self.assertRaisesRegex(RuntimeError, "same package"):
                        bound.browser_control(c, None, None, self.out, "s01")
                    browser.assert_not_called()

    def test_paired_observer_rejects_retries_or_error_counters(self):
        api = object.__new__(backend.Backend)
        api.group, api.served_name, api.profile = "n03-a", "prefix-n03probe-full.etu", {}
        api.initial_sample = mock.Mock()
        clean = dict(result="PREFIX_OBSERVED", app=dict(prefix=dict(prefixBytes=32768, sentTotalBytes=32768)),
                     profile=dict(clean_counters=True))
        original = mock.Mock()
        phone = types.SimpleNamespace(release_old=lambda *args: None, browser_control=lambda *args: None,
                                      observe_app=original)
        api.legacy = dict(named=dict(raw_load=lambda *args: phone))
        c = types.SimpleNamespace(HERE=ROOT)
        self.store.write(self.out / "fresh-begin.json", {})
        self.store.raw(self.out / "finished/parsed/observations.log",
            b"OTA_LINK_SAMPLE label=prefix-probe kind=durable us=10 off=0\n"
            b"OTA_LINK_SAMPLE label=prefix-probe kind=segment_first_send us=15 off=0 len=128\n")
        bound = api.phone(c, "fixture")
        original.return_value = copy.deepcopy(clean)
        self.assertIn("initial_state_evidence", bound.observe_app(c, None, None, self.out, 1, {}, {}))
        for retry in (True, False):
            value = copy.deepcopy(clean)
            if retry: value["app"]["prefix"]["sentTotalBytes"] += 128
            else: value["profile"]["clean_counters"] = False
            original.return_value = value
            with self.subTest(retry=retry), self.assertRaisesRegex(RuntimeError, "retransmissions or MCU errors"):
                bound.observe_app(c, None, None, self.out, 1, {}, {})

    def full_fixture(self):
        expected = dict(schema=2, runId="s04", requestedBaud=921600, reuseGatt=True, withoutResponse=True,
            senderWindowSegments=4, transferMode="full", prefixBytes=0, target=observation_tests.TARGET,
            firmwareLatestUrl="https://fixture.trycloudflare.com/api/firmware/latest",
            **{k:v for k,v in observation_tests.INPUT.items() if k not in ("deviceAddress", "appLifecycle")})
        stamp = {k:v for k,v in expected.items() if k not in ("target", "firmwareLatestUrl")}
        stamp.update(configSha256="e" * 64, deviceAddress=expected["target"], endpointHost="fixture.trycloudflare.com")
        rows = observation_tests.rows()
        rows.insert(2, dict(kind="line", message="OTA_EXPERIMENT " + json.dumps(stamp)))
        return expected, [dict(row, seq=i) for i,row in enumerate(rows, 1)]

    def test_full_snapshot_requires_completion_identity_config_and_pid(self):
        expected, rows = self.full_fixture()
        raw = observation_tests.encoded(rows)
        args = ("e" * 64, 12345, observation_tests.SENTINEL)
        value, _, stamp = backend.verify_full_snapshot(observation_tests.m, raw, expected, *args)
        self.assertEqual(value["outcome"], "completed")
        self.assertEqual(stamp["transferMode"], "full")
        for changed in (dict(expected, transferMode="prefix"), dict(expected, prefixBytes=32768),
                        dict(expected, targetImageSha256="d" * 64)):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                backend.verify_full_snapshot(observation_tests.m, raw, changed, *args)
        for wrong in (("f" * 64, 12345, observation_tests.SENTINEL), ("e" * 64, 12346, observation_tests.SENTINEL)):
            with self.subTest(wrong=wrong), self.assertRaises(RuntimeError):
                backend.verify_full_snapshot(observation_tests.m, raw, expected, *wrong)
        for fragment in ("MONO_END_ACK_OK", "MONO_REBOOT_VERIFIED", '"post-reboot"'):
            changed = [row for row in rows if fragment not in row.get("message", "")]
            changed = [dict(row, seq=i) for i,row in enumerate(changed, 1)]
            with self.subTest(fragment=fragment), self.assertRaises(observation_tests.m.CaptureError):
                backend.verify_full_snapshot(observation_tests.m, observation_tests.encoded(changed), expected, *args)

    def test_prefix_or_not_completed_capture_cannot_prove_installation(self):
        expected, rows = self.full_fixture()
        rows[-1]["outcome"] = "not-completed"
        for raw in (observation_tests.encoded(rows), observation_tests.encoded(observation_tests.prefix_rows())):
            with self.assertRaises((RuntimeError, observation_tests.m.CaptureError)):
                backend.verify_full_snapshot(observation_tests.m, raw, expected, "e" * 64, 12345, observation_tests.SENTINEL)

    def test_installation_adapter_sets_full_mode_and_truthful_release_notes(self):
        api = object.__new__(backend.Backend)
        api.group, api.served_name = "n03-install", "prefix-n03recv-full.etu"
        raw = cli.load_module("p34_install_phone_fixture", ROOT / ".cache/p34-next/prefix_phone.py")
        api.legacy = dict(named=dict(raw_load=lambda *args: raw))
        phone = api.phone(types.SimpleNamespace(HERE=ROOT), "fixture", producer=True)
        c = types.SimpleNamespace(CELLS=cli.CELLS, TARGET=observation_tests.TARGET,
            service=types.SimpleNamespace(LATEST_PATH="/api/firmware/latest", DEVICE_MODEL="fixture"),
            screen=dict(bytes=290996, sha256="a" * 64, path="fixture"), receiver_version=30214,
            receiver_image_sha="b" * 64, target_version=30215, target=dict(sha256="c" * 64),
            target_identity=dict(version_name="fixture", version_code=30215), release_key="fixture")
        value = phone.config(c, "s04", 921600, 4, "https://fixture.trycloudflare.com")
        self.assertEqual((value["transferMode"], value["prefixBytes"]), ("full", 0))
        self.assertEqual(value["targetVersionCode"], 30215)
        with self.assertRaises(RuntimeError):
            phone.config(c, "s01", 460800, 4, "https://fixture.trycloudflare.com")
        notes = phone.service_config(c, "https://fixture.trycloudflare.com")["releases"]["fixture"]["releaseNotes"]
        self.assertIn("normal full BLE OTA", notes)
        self.assertNotIn("No END", notes)

    def completed_installation(self):
        _, profile, probe = self.completed_pair()
        previous = cli.paired_predecessor(self.store, profile["predecessor"])
        out = self.store.run("installation")
        boot = self.store.raw(out / "boot.bin", b"unchanged boot")
        bindings, closures = {}, {}
        for name, image in (("before", b"old receiver"), ("after", b"N03 receiver")):
            item = self.store.raw(out / name / "app.bin", image)
            bindings[name] = dict(profile=dict(image=item,
                map=self.store.raw(out / name / "image.map", ("map fixture " + name).encode())), whole_boot=boot)
            state = dict(bcb_state=4, confirm_done=1, state_snapped=1, sd_ready=1,
                session_raw=self.store.raw(out / name / "session.bin", b"session"),
                profile_raw=self.store.raw(out / name / "profile.bin", b"profile"))
            closure = dict(retained_verified=True, reader_closed=True, final_state=state,
                initial_identity=dict(app=item, boot=boot), final_identity=dict(app=item, boot=boot))
            self.store.write(out / name / "closure.json", closure)
            closures[name] = cli.record(out / name / "closure.json")
        package = dict(sha256="d" * 64, bytes=290996)
        plan = dict(group="n03-install", receiver_version=30214, target_version=30215, prefix_bytes=0,
            no_end=False, no_firmware_install=False, predecessor=profile["predecessor"], served=package,
            bindings=bindings["before"], target_bindings=bindings["after"])
        self.store.write(out / "plan.json", plan)
        config = self.store.raw(out / "config.json", b"full fixture config")
        snapshot = self.store.raw(out / "snapshot.jsonl", b"full fixture snapshot")
        self.store.write(out / "after/flash-admission.json", dict(disabled=0, jedec=0xEF4018))
        self.store.write(out / "after/receiver-admission.json", dict(result="BOUND_RECEIVER_ADMITTED", receiver_version=30215,
            image_sha256=bindings["after"]["profile"]["image"]["sha256"], map=bindings["after"]["profile"]["map"],
            flash_gate=cli.record(out / "after/flash-admission.json")))
        report = dict(result="FULL_INSTALL_VERIFIED", cell="s04", start_inputs_verified_before=True,
            inputs=dict(plan=cli.record(out / "plan.json"), config=config, snapshot=snapshot),
            flash_admission=cli.record(out / "after/receiver-admission.json"),
            summary=dict(outcome="completed", rawSha256=snapshot["sha256"], pid=456, captureId="full-fixture"), **closures)
        self.store.write(out / "analysis/1/result.json", report)
        descriptor = dict(run=out.name, cell="s04", plan=cli.record(out / "plan.json"),
                          report=cli.record(out / "analysis/1/result.json"))
        self.store.write(out / "analysis/latest.json", dict(cell="s04", result="FULL_INSTALL_VERIFIED", report=descriptor["report"]))
        for name in ("s04", "network"):
            self.store.write(out / "runtime" / name / "closed.json", dict(worker_exit=0, forced_termination=False))
        self.store.write(self.store.base / "current.json", dict(run=out.name), replace=True)
        profile = dict(profile, installation=descriptor)
        path = self.store.base / "profile-b-ota.json"
        self.store.write(path, profile)
        return path, profile, previous, out, package, bindings["after"], probe

    def test_installation_bridge_preserves_both_a_and_original_installed_images(self):
        _, profile, previous, out, _, _, _ = self.completed_installation()
        value = cli.installed_predecessor(self.store, profile["installation"], previous)
        self.assertEqual(value["out"], out)
        self.store.checked(out / "after/app.bin").write_bytes(b"tampered N03")
        with self.assertRaisesRegex(RuntimeError, "original bytes changed"):
            cli.installed_predecessor(self.store, profile["installation"], previous)

    def test_installation_bridge_rejects_unconfirmed_state_and_unclosed_owner(self):
        _, profile, previous, out, _, _, _ = self.completed_installation()
        closed = out / "runtime/network/closed.json"
        self.store.checked(closed).unlink()
        with self.assertRaisesRegex(RuntimeError, "owners must be closed"):
            cli.installed_predecessor(self.store, profile["installation"], previous)
        self.store.write(closed, dict(worker_exit=0))
        report = self.store.read(profile["installation"]["report"]["path"])
        closure = self.store.read(report["after"]["path"])
        closure["final_state"]["confirm_done"] = 0
        self.store.write(report["after"]["path"], closure, replace=True)
        report["after"] = cli.record(report["after"]["path"])
        self.store.write(profile["installation"]["report"]["path"], report, replace=True)
        descriptor = dict(profile["installation"], report=cli.record(profile["installation"]["report"]["path"]))
        with self.assertRaisesRegex(RuntimeError, "not idle/CONFIRMED"):
            cli.installed_predecessor(self.store, descriptor, previous)

    def test_attempted_installation_returns_status_never_launches_it_again(self):
        path, _, _, out, _, _, _ = self.completed_installation()
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend") as factory:
            value = cli.start(self.store, path, "s04", "n03-install")
            self.assertEqual((value["run"], value["cell"], value["result"]), (out.name, "s04", "FULL_INSTALL_VERIFIED"))
            factory.assert_not_called()
            self.store.checked(out / "analysis/latest.json").unlink()
            self.store.write(out / "cells/s04/status.json", dict(result="FULL_INSTALL_INCOMPLETE"))
            self.assertEqual(cli.start(self.store, path, "s04", "n03-install")["result"], "FULL_INSTALL_INCOMPLETE")
            factory.assert_not_called()

    def test_a_installation_b_transitions_require_the_exact_owners(self):
        path, profile, _, _, _, _, _ = self.completed_installation()
        with mock.patch.object(cli, "verify_tests", return_value={}), \
                mock.patch.object(cli, "backend", side_effect=RuntimeError("B preparation boundary")) as factory:
            with self.assertRaisesRegex(RuntimeError, "B preparation boundary"):
                cli.start(self.store, path, "s01", "n03-b")
            factory.assert_called_once_with(self.store, path, "n03-b")
            with self.assertRaisesRegex(RuntimeError, "same cell"):
                cli.start(self.store, path, "s02", "n03-b")
            profile.pop("installation")
            self.store.write(path, profile, replace=True)
            with self.assertRaisesRegex(RuntimeError, "explicit completed R installation"):
                cli.start(self.store, path, "s01", "n03-b")

    def test_b_retires_only_its_verified_full_installation_capture(self):
        path, profile, _, _, package, bindings, probe = self.completed_installation()
        api = object.__new__(backend.Backend)
        api.store, api.root, api.profile_path, api.profile, api.group = self.store, ROOT, path, profile, "n03-b"
        c = types.SimpleNamespace(screen=probe, receiver_version=30215, target_version=30216, bindings=bindings,
            n03=dict(groups=dict(receiver=dict(package=package))))
        report = self.store.read(profile["installation"]["report"]["path"])
        observed = dict(stable_completed=True, snapshots=["snapshot-1.jsonl"], config=report["inputs"]["config"],
            snapshot_records={"snapshot-1.jsonl":report["inputs"]["snapshot"]}, pid=456, health=dict(captureId="full-fixture"))
        self.assertEqual(api.completed_capture(c, observed), profile["installation"]["report"])
        self.assertEqual(api.completed_capture(c, dict(observed, pid=None, pid_checked_before_after=True)),
                         profile["installation"]["report"])
        self.assertIsNone(api.completed_capture(c, dict(observed, pid=None)))
        for change in (dict(pid=123), dict(health=dict(captureId="fixture")), dict(stable_completed=False)):
            with self.subTest(change=change):
                self.assertIsNone(api.completed_capture(c, dict(observed, **change)))

    def test_full_ready_is_visible_only_with_a_live_owner(self):
        path = self.owner("s04")
        self.owner()
        self.live(200)
        self.store.write(self.out / "cells/s04/status.json", dict(result="READY_FOR_FULL_INSTALL_START"))
        self.store.write(self.out / "cells/s04/launch.json", dict(time=dt.datetime.fromtimestamp(90, dt.timezone.utc).isoformat()))
        self.store.write(self.out / "cells/s04/health-live.json", dict(observed=dt.datetime.fromtimestamp(100, dt.timezone.utc).isoformat(),
            health=dict(upgradeStarts=0, upgradeEnds=0, healthy=True, lost=0, error=None)))
        self.assertIn("bound full upgrade once", cli.status(self.store, "fixture", "s04", clock=100)["next_action"])
        self.store.write(path / "closed.json", dict(worker_exit=1))
        value = cli.status(self.store, "fixture", "s04", clock=100)
        self.assertEqual(value["result"], "CELL_CLOSED")
        self.assertNotIn("upgrade once", value["next_action"])

    def test_install_checkpoint_never_tunes_resets_or_keeps_old_reader_open(self):
        api = object.__new__(backend.Backend)
        api.fresh_begin = mock.Mock()
        mcu = mock.Mock(original_baud=921600)
        mcu.close.side_effect = lambda **kwargs: self.store.write(self.out / "mcu/closure.json", {})
        c = types.SimpleNamespace(HERE=ROOT, checked=self.store.checked,
            load=lambda *args: types.SimpleNamespace(Mcu=lambda *args: mcu))
        api.install_checkpoint(c, self.out, before=True)
        self.assertEqual(mcu.method_calls, [mock.call.open(), mock.call.close(restore=False)])
        api.fresh_begin.assert_called_once_with(c, mcu, self.out)

    def test_install_worker_serializes_old_close_app_ota_and_new_identity(self):
        api = object.__new__(backend.Backend)
        api.root, api.group = ROOT, "n03-install"
        events = []
        phone = types.SimpleNamespace(usb=lambda *args: nullcontext("usb"), network=lambda *args: nullcontext("https://fixture"),
            release_old=lambda *args: events.append("retire A"), config=lambda *args: {},
            provision=lambda *args: events.append("launch App") or 123)
        api.phone = lambda *args: phone
        api.install_checkpoint = lambda c, out, before=False: events.append("old closed" if before else "R verified") or dict(path="fixture")
        api.verify_install_checkpoint = lambda *args: None
        api.observe_install = lambda *args, **kwargs: events.append("normal OTA and snapshot") or {}
        api.installed_context = lambda *args: "R context"
        api.analyze_install = lambda *args: dict(result="FULL_INSTALL_VERIFIED")
        c = types.SimpleNamespace(load=lambda *args: types.SimpleNamespace(device_lock=lambda: nullcontext()),
            action=lambda *args, **kwargs: None, save=self.store.write, now=cli.now)
        with mock.patch("builtins.print"):
            self.assertEqual(api.install_worker(c, self.out, "s04"), 0)
        self.assertEqual(events, ["retire A", "old closed", "launch App", "normal OTA and snapshot", "R verified"])

    def test_full_observer_checks_download_before_ready_and_rejects_premature_start(self):
        for premature in (False, True):
            with self.subTest(premature=premature):
                api = object.__new__(backend.Backend)
                api.group = "n03-install"
                api.served_name = "prefix-n03recv-full.etu"
                expected, rows = self.full_fixture()
                out = self.out / str(premature)
                self.store.write(out / "runtime-config.json", expected)
                sha = cli.record(out / "runtime-config.json")["sha256"]
                stamp = json.loads(rows[2]["message"].removeprefix("OTA_EXPERIMENT "))
                stamp["configSha256"] = sha
                healthy = dict(healthy=True, lost=0, error=None, captureId=observation_tests.CAPTURE,
                               upgradeStarts=0, upgradeEnds=0, outcome=None)
                terminal = dict(healthy, upgradeStarts=1, upgradeEnds=1, outcome="completed")
                health_bytes = json.dumps(healthy).encode()
                p = mock.Mock()
                p.command.return_value = str(len(b"R package")) + "\n"
                p.file_bytes.side_effect = [health_bytes, b"events", health_bytes, b"R package",
                    json.dumps(dict(healthy, upgradeStarts=1) if premature else healthy).encode(), json.dumps(terminal).encode()]
                p.query.validate.return_value = (dict(successfulQueries=1), b"checkpoint",
                                                "OTA_EXPERIMENT " + json.dumps(stamp) + "\n")
                phone = types.SimpleNamespace(exists=lambda *args: True,
                    location=lambda *args: (12345, "files/p34-observations/" + observation_tests.CAPTURE))
                c = types.SimpleNamespace(save=self.store.write, raw=self.store.raw, now=cli.now, cell="s04", PKG="fixture",
                    TARGET=observation_tests.TARGET, target_version=30215, screen_bytes=b"R package", envelope=observation_tests.m,
                    apk=dict(metadata=dict(device_observation=dict(sentinel=observation_tests.SENTINEL))))
                api.finish_install_snapshot = mock.Mock(return_value=dict(outcome="completed"))
                api.launched_capture = lambda *args: "files/p34-observations/" + observation_tests.CAPTURE
                with mock.patch.object(backend.time, "sleep"):
                    if premature:
                        with self.assertRaisesRegex(RuntimeError, "before downloaded-input admission"):
                            api.observe_install(c, p, phone, out, 12345, expected)
                        self.assertFalse((out / "queries/result.json").exists())
                    else:
                        self.assertEqual(api.observe_install(c, p, phone, out, 12345, expected)["outcome"], "completed")
                        self.assertEqual(self.store.read(out / "status.json")["result"], "READY_FOR_FULL_INSTALL_START")
                        self.assertEqual((out / "queries/package.etu").read_bytes(), b"R package")
                api.finish_install_snapshot.assert_called_once()

    def test_install_offline_and_original_readback_reuse_never_contact_devices(self):
        api = object.__new__(backend.Backend)
        api.group, api.store = "n03-install", self.store
        api.analyze_install = mock.Mock(return_value=dict(result="FULL_INSTALL_VERIFIED"))
        api.inspect = mock.Mock(side_effect=AssertionError("device contact"))
        self.store.write(self.out / "runtime/s04/closed.json", dict(worker_exit=0))
        self.assertEqual(api.collect(None, self.out, "s04", offline=True)["result"], "FULL_INSTALL_VERIFIED")
        self.assertEqual(api.collect(None, self.out, "s04", verify_mcu=True)["result"], "FULL_INSTALL_VERIFIED")
        self.assertEqual(api.analyze_install.call_count, 2)
        api.inspect.assert_not_called()

    def test_install_retrieval_uses_original_capture_not_the_newest_app(self):
        api = object.__new__(backend.Backend)
        remote = "files/p34-observations/" + observation_tests.CAPTURE
        self.store.write(self.out / "cells/s04/queries/result.json", dict(remote=remote))
        p = mock.Mock()
        p.command.return_value = "health.json\nevents.jsonl\nsnapshot-1.jsonl\n"
        p.file_bytes.side_effect = lambda pkg, source, limit: source.encode()
        c = types.SimpleNamespace(read=self.store.read, save=self.store.write, raw=self.store.raw, PKG="fixture",
            envelope=types.SimpleNamespace(MAX_BYTES=67108864))
        destination = self.out / "collections/original"
        value = api.collect_install_capture(c, p, self.out, destination, "s04")
        self.assertEqual(value["remote"], remote)
        self.assertEqual((destination / "app/snapshot-1.jsonl").read_bytes(), (remote + "/snapshot-1.jsonl").encode())
        p.command.assert_called_once_with(["exec-out", "run-as", "fixture", "ls", "-1", remote])
        self.store.write(self.out / "cells/s04/queries/result.json", dict(remote=remote + "/../other"), replace=True)
        with self.assertRaisesRegex(RuntimeError, "invalid planned App capture"):
            api.collect_install_capture(c, p, self.out, self.out / "collections/rejected", "s04")
        self.assertEqual(p.command.call_count, 1)

    def test_started_or_finished_capture_never_reverts_to_ready_when_health_is_old(self):
        self.owner("s04")
        self.owner()
        self.live(200)
        self.store.write(self.out / "cells/s04/status.json", dict(result="READY_FOR_FULL_INSTALL_START"))
        self.store.write(self.out / "cells/s04/launch.json", dict(time=dt.datetime.fromtimestamp(50, dt.timezone.utc).isoformat()))
        self.store.write(self.out / "cells/s04/queries/result.json", dict(query=dict(captureId="current")))
        for ends, expected in ((0, "TRANSFER_ACTIVE"), (1, "FINALIZING")):
            self.store.write(self.out / "cells/s04/health-live.json", dict(observed=dt.datetime.fromtimestamp(60, dt.timezone.utc).isoformat(),
                health=dict(upgradeStarts=1, upgradeEnds=ends, captureId="current")), replace=True)
            state = cli.status(self.store, "fixture", "s04", clock=100)
            self.assertEqual(state["result"], expected)
            self.assertNotIn("upgrade once", state["next_action"])
        self.store.write(self.out / "cells/s04/health-live.json", dict(observed=dt.datetime.fromtimestamp(100, dt.timezone.utc).isoformat(),
            health=dict(upgradeStarts=0, upgradeEnds=0, captureId="other")), replace=True)
        self.assertEqual(cli.status(self.store, "fixture", "s04", clock=100)["result"], "CAPTURE_CHANGED")

    def test_prelaunch_terminal_health_is_not_the_new_transfer(self):
        self.owner("s04")
        self.owner()
        self.live(200)
        self.store.write(self.out / "cells/s04/health-live.json", dict(observed=dt.datetime.fromtimestamp(100, dt.timezone.utc).isoformat(),
            health=dict(upgradeStarts=1, upgradeEnds=1)))
        self.assertEqual(cli.status(self.store, "fixture", "s04", clock=100)["result"], "PREPARING")

    def test_owner_clock_is_sampled_after_reading_the_heartbeat(self):
        path = self.owner()
        clock, read = [99.0], self.store.read
        def observed(path):
            value = read(path)
            if path.name == "state.json":
                clock[0] = 101.0
            return value
        with mock.patch.object(self.store, "read", side_effect=observed), mock.patch.object(cli.time, "time", side_effect=lambda: clock[0]):
            self.assertEqual(cli.owner_state(self.store, path)["state"], "LIVE")

    def test_flash_gate_addresses_come_from_the_receivers_bound_map(self):
        results = []
        for delta in (0, 48):
            text = (f" .data._ZL19g_qspi_ota_disabled\n 0x{0x20000100 + delta:x} 0x1 dir/HAL_W25Q128.cpp.obj\n"
                    f" .bss._ZL15g_qspi_jedec_id\n 0x{0x20020000 + delta:x} 0x4 dir/HAL_W25Q128.cpp.obj\n"
                    f" .bss._ZL14s_p34_clock_ok\n 0x{0x20030000 + delta:x} 0x4 dir/HAL_Bluetooth.cpp.obj\n")
            profile = dict(map=self.store.raw(self.out / (str(delta) + ".map"), text.encode()))
            results.append(backend.bind_flash_gate(profile, flash_map.symbol))
            self.assertEqual(results[-1]["jedec"], 0x20020000 + delta)
            with self.assertRaisesRegex(RuntimeError, "MAP bytes changed"):
                backend.bind_flash_gate(dict(map=dict(profile["map"], sha256="f" * 64)), flash_map.symbol)
        self.assertNotEqual(results[0], results[1])
        bad = self.store.raw(self.out / "duplicate.map", (text + text).encode())
        with self.assertRaisesRegex(RuntimeError, "size/owner mismatch"):
            backend.bind_flash_gate(dict(map=bad), flash_map.symbol)

    def test_actual_candidate_context_does_not_inherit_old_flash_gate_addresses(self):
        profile = ROOT / ".cache/p34-session/profile-n03-install.json"
        api = cli.backend(self.store, profile, "n03-install")
        retained = api.context(self.out)
        candidate = api.installed_context(self.out)
        self.assertNotEqual(candidate.flash_addresses, retained.flash_addresses)
        self.assertEqual(candidate.flash_addresses, backend.bind_flash_gate(candidate.bindings["profile"], flash_map.symbol))
        self.assertEqual(candidate.receiver_version, 30215)

    def test_readback_needs_successful_gate_bound_to_this_receiver_map(self):
        api = object.__new__(backend.Backend)
        c = types.SimpleNamespace(read=self.store.read, checked=self.store.checked, receiver_version=30215,
            receiver_image_sha="a" * 64, bindings=dict(profile=dict(map={"fixture":1})), flash_addresses=dict(jedec=0x20000010))
        self.assertIsNone(api.verify_receiver_admission(c, self.out))
        self.store.write(self.out / "flash-admission.json", dict(disabled=0, jedec=0xEF4018))
        proof = dict(result="BOUND_RECEIVER_ADMITTED", receiver_version=30215, image_sha256="a" * 64,
            map=c.bindings["profile"]["map"], addresses=c.flash_addresses, flash_gate=cli.record(self.out / "flash-admission.json"))
        self.store.write(self.out / "receiver-admission.json", proof)
        self.assertEqual(api.verify_receiver_admission(c, self.out), cli.record(self.out / "receiver-admission.json"))
        self.store.write(self.out / "receiver-admission.json", dict(proof, addresses=dict(jedec=0x20000020)), replace=True)
        with self.assertRaisesRegex(RuntimeError, "different image/MAP addresses"):
            api.verify_receiver_admission(c, self.out)

    def test_terminal_schema_is_exactly_bound_to_the_compiled_phase_layout(self):
        model = prefix_contract_tests.c.m
        header = ROOT / ".cache/p34-next/n03/fw/USER/HAL/BtBaudExperiment/p34_link_profile.h"
        self.assertIn("#define P34_PROFILE_SCHEMA 2u", header.read_text())
        for schema, phases in ((1, model.PHASES), (2, model.PHASES + ("payload_verify", "journal_verify"))):
            size = 96 + 24 * len(phases)
            words = [0] * (size // 4)
            values = dict(magic=0x50334250, schema=schema, size=size, ready=1, active=0, terminal=1,
                run=1, clock_hz=288000000, clock_ok=1, retained_baud=460800, uart_baud_actual=460063, total_len=290856)
            for key, value in values.items():
                words[model.HEADERS.index(key)] = value
            def decode(current, names=phases):
                return prefix_mcu.decode_terminal(model, struct.pack("<%dI" % len(current), *current),
                    run=1, baud=460800, total=290856, layout=dict(size=size, phases=names))
            self.assertEqual(decode(words)["schema"], schema)
            for other in (0, 3, 2 if schema == 1 else 1):
                bad = words.copy()
                bad[model.HEADERS.index("schema")] = other
                with self.subTest(schema=schema, other=other):
                    with self.assertRaisesRegex(RuntimeError, "profile: schema"):
                        decode(bad)
            with self.assertRaisesRegex(RuntimeError, "unsupported bound profile"):
                decode(words, phases[::-1])


if __name__ == "__main__":
    store = cli.Store(ROOT)
    store.checked(OUTPUT)
    log = store.checked(OUTPUT / "unittest.log")
    patch_tests = cli.load_module("p34_patch_session_tests", ROOT / "tests/ota/test_p34_patch_session.py")
    suite = unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(SessionTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(observation_tests.CaptureTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(full_tests.FullTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(window8_tests.Window8Tests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(repeat_tests.RepeatTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(install_tests.InstallTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(install_tests.Window16Tests),
                               unittest.TestSuite(prefix_contract_tests.RouteTests(name) for name in (
                                   "test_terminal_is_abort_not_end_and_preserves_counter_failures",
                                   "test_receiver_layout_comes_from_the_binding_and_fails_closed",
                                   "test_terminal_layout_is_bound_to_the_receiver_not_the_byte_count"))))
    for test_class in patch_tests.TEST_CLASSES:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    android_tests = cli.load_module("p34_android_tests", ROOT / "tests/ota/test_p34_android_trace.py")
    for test_class in android_tests.TEST_CLASSES:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    speed_tests = cli.load_module("p34_speed16_tests", ROOT / "tests/ota/test_p34_speed16.py")
    for test_class in speed_tests.TEST_CLASSES:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    speed32_tests = cli.load_module("p34_speed32_tests", ROOT / "tests/ota/test_p34_speed32.py")
    for test_class in speed32_tests.TEST_CLASSES:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    patch32_tests = cli.load_module("p34_patch32_tests", ROOT / "tests/ota/test_p34_patch32.py")
    for test_class in patch32_tests.TEST_CLASSES:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    receive_tests = cli.load_module("p34_receive_tests", ROOT / "tests/ota/test_p34_receive.py")
    for test_class in receive_tests.TEST_CLASSES:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    cached_tests = cli.load_module("p34_cached_resume_suite", ROOT / "tests/ota/test_p34_cached_resume.py")
    for test_class in cached_tests.TEST_CLASSES:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    gap_tests = cli.load_module("p34_ack_gap_suite", ROOT / "tests/ota/test_p34_ack_gap_assets.py")
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(gap_tests.Tests))
    batch_tests = cli.load_module("p34_ack_batch_suite", ROOT / "tests/ota/test_p34_ack_batch_assets.py")
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(batch_tests.Tests))
    boot_tests = cli.load_module("p34_boot_copy_suite", ROOT / "tests/ota/test_p34_boot_ota.py")
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(boot_tests.Tests))
    cost_tests = cli.load_module("p34_cost_suite", ROOT / "tests/ota/test_p34_cost_assets.py")
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cost_tests.Tests))
    erase_tests = cli.load_module("p34_erase_suite", ROOT / "tests/ota/test_p34_erase_assets.py")
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(erase_tests.Tests))
    reconnect_tests = cli.load_module("p34_reconnect_suite", ROOT / "tests/ota/test_p34_reconnect.py")
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(reconnect_tests.Tests))
    historical_tests = cli.load_module("p34_historical_suite", ROOT / "tests/ota/test_p34_historical_inputs.py")
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(historical_tests.Tests))
    with log.open("x", encoding="utf-8", newline="\n", buffering=1) as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    print(log.read_text(encoding="utf-8"), end="")
    value = dict(passed=result.wasSuccessful(), tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), device_operations=0, sources=[cli.record(ROOT / name) for name in (
            "p34.bat", "Tools/ota/p34_session.py", "Tools/ota/p34_session_backend.py", "Tools/ota/p34_observation.py",
            "tests/ota/test_p34_session.py", "tests/ota/test_p34_observation.py", "tests/ota/test_p34_full.py",
            "Tools/ota/p34_full_assets.py", "Tools/ota/p34_full_trace.py",
            "Tools/ota/p34_window8_assets.py", "tests/ota/test_p34_window8.py",
            "Tools/ota/p34_successor_assets.py", "tests/ota/test_p34_repeat.py",
            "Tools/ota/p34_install_assets.py", "Tools/ota/p34_install_candidate.py", "tests/ota/test_p34_install.py",
            "Tools/ota/p34_patch_assets.py", "Tools/ota/p34_patch_preparation.py", "tests/ota/test_p34_patch_session.py",
            "Tools/ota/p34_android_trace.py", "tests/ota/test_p34_android_trace.py",
            "tests/ota/test_p34_speed16.py",
            "tests/ota/test_p34_speed32.py",
            "Tools/ota/p34_retirement_recovery.py",
            "Tools/ota/p34_patch32_assets.py", "Tools/ota/p34_patch32_recovery.py", "tests/ota/test_p34_patch32.py",
            "Tools/ota/p34_receive_assets.py", "tests/ota/test_p34_receive.py",
            "Tools/ota/p34_cached_resume.py", "tests/ota/test_p34_cached_resume.py",
            "Tools/ota/p34_ack_gap_assets.py", "tests/ota/test_p34_ack_gap_assets.py",
            "Tools/ota/p34_ack_gap.h", "tests/ota/test_p34_ack_gap.cpp",
            "Tools/ota/p34_ack_batch_assets.py", "tests/ota/test_p34_ack_batch_assets.py",
            "Tools/ota/p34_ack_batch.h", "tests/ota/test_p34_ack_batch.cpp",
            "Tools/ota/p34_boot_ota_assets.py", "tests/ota/test_p34_boot_ota.py",
            "Tools/ota/p34_boot_device.py",
            "Tools/ota/p34_cost_assets.py", "tests/ota/test_p34_cost_assets.py", "Tools/ota/p34_install_cost.py",
            "Tools/ota/p34_erase_assets.py", "tests/ota/test_p34_erase_assets.py", "Tools/ota/p34_erase_candidate.py",
            "Tools/ota/p34_reconnect_assets.py", "Tools/ota/p34_reconnect_profile.py", "tests/ota/test_p34_reconnect.py",
            "Tools/ota/p34_cost_archive.py",
            "Tools/ota/p34_historical_inputs.py", "tests/ota/test_p34_historical_inputs.py",
            "USER/HAL/HAL_OTA_Package.cpp", "USER/HAL/ota_install_cost.h",
            "tests/ota/test_qspi_install_restore.py", "tests/ota/test_ota_install_cost.cpp",
            ".agents/skills/e-track-flutter-debug/scripts/host_io.py", ".cache/p34-next/prefix_mcu.py",
            ".cache/p34-next/prefix.py", ".cache/p34-next/prefix_phone.py",
            ".cache/p34-next/qspi_clock_probe.py", ".cache/p34-next/prefix_restored.py",
            ".cache/p34-next/test_prefix.py", ".cache/p34-next/n03/fw/USER/HAL/BtBaudExperiment/p34_link_profile.h")])
    store.write(OUTPUT / "result.json", value)
    raise SystemExit(not result.wasSuccessful())
