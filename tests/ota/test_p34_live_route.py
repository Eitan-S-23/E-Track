"""Finite live-adapter host tests. Synthetic device bytes are never hardware PASS."""
import hashlib
from contextlib import contextmanager, ExitStack
import io
import json
import os
from pathlib import Path
import struct
import ssl
import sys
import tempfile
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zlib
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "Tools/ota/p34-acceptance"), str(ROOT / "tests/ota")]
import live
import live_host as h
import live_mcu as m
import live_phone as p
import test_p34_acceptance_stats as stats_fixture
import test_p34_service_patch as service_fixture
import test_ota_link_metrics as metrics_fixture


class LiveRouteTests(unittest.TestCase):
    def setUp(self):
        parent = h.checked(Path(os.environ.get("P34_HOST_TEST_OUT", ROOT / ".cache/p34-live-tests")))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def file(self, name, raw):
        path = self.out / name
        h.raw(path, raw)
        return h.record(path)

    def phone(self):
        plan = dict(adb_key=self.file("adbkey", b"synthetic, never used by adb"),
            tools=dict(adb=dict(path=sys.executable, bytes=Path(sys.executable).stat().st_size,
                                sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest())),
            adb_port=5062, phone_serial="fixture", app_id="test.p34", phone_model="fixture",
            apk=dict(sha256="f" * 64), owned_configs=[])
        return p.Phone(plan, self.out / "phone", 900)

    @staticmethod
    def health_bytes(capture, **changes):
        value = dict(schema=1, captureId=capture, time="2026-10-12T09:55:15.933207Z",
            records=3, bytes=640, producerLines=2, upgradeStarts=0, upgradeEnds=0,
            outcome=None, lost=0, error=None, healthy=True)
        value.update(changes)
        return (json.dumps(value) + "\n").encode()

    @contextmanager
    def app_files(self, phone, files, *, listing=None):
        """Mock only remote commands; execute the actual guards/readers/parsers."""
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            if args[-3:] == ["readlink", "-f", "."]:
                return ("/data/user/0/" + phone.pkg + "\n").encode()
            if args[3:5] == ["sh", "-c"]:
                self.assertTrue(args[-1].startswith("test ! -L "), args)
                return b""
            remote, mode = args[-1], args[3]
            if mode == "ls":
                names = listing() if listing else sorted(path.rsplit("/", 1)[-1]
                    for path in files if path.rsplit("/", 1)[0] == remote)
                return ("\n".join(names) + "\n").encode()
            self.assertIn(mode, ("head", "cat", "stat"), args)
            raw = files[remote](mode) if callable(files[remote]) else files[remote]
            if mode == "stat":
                return str(len(raw)).encode()
            return raw[:int(args[-2])] if mode == "head" else raw
        with patch.object(phone, "cmd", side_effect=command):
            yield calls

    def snapshot_files(self, phone, raw):
        remote = "files/p34-observations/" + phone.capture
        footer = json.loads(raw.splitlines()[-1])
        health = {key: footer[key] for key in p.HEALTH_FIELDS - {"time"}}
        return {remote + "/health.json": self.health_bytes(phone.capture, **health),
                remote + "/snapshot-1.jsonl": raw}

    def test_standard_process_binary_streams_exit_and_timeout_are_preserved(self):
        env = h.environment(self.out)
        result = h.command(self.out, "binary", [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
            "import sys;sys.stdout.buffer.write(b'\\x00\\xff');sys.stderr.write('diagnostic')"], env, seconds=10)
        self.assertEqual(result, b"\x00\xff")
        payload = b"runtime\x00\xff\n"
        copied = h.command(self.out, "stdin", [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
            "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"], env, seconds=10, stdin=payload)
        self.assertEqual(copied, payload)
        self.assertEqual((self.out / "binary.stderr").read_bytes(), b"diagnostic")
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            h.command(self.out, "binary", [sys.executable], env, seconds=1)
        with self.assertRaisesRegex(RuntimeError, "standard tool failed"):
            h.command(self.out, "nonzero", [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", "raise SystemExit(7)"], env, seconds=10)
        self.assertEqual(h.read_json(self.out / "nonzero.closed.json")["exit_code"], 7)
        with self.assertRaisesRegex(RuntimeError, "timeout"):
            h.command(self.out, "timeout", [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", "import time;time.sleep(30)"], env, seconds=.2)
        receipt = h.read_json(self.out / "timeout.closed.json")
        self.assertEqual(receipt["reason"], "timeout_outcome_unknown")
        self.assertTrue(receipt["stopped_while_running"])

    def test_isolated_real_cli_imports_without_cwd_on_sys_path(self):
        text = h.command(self.out, "help", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
            ROOT / "Tools/ota/p34-acceptance/live.py", "--help"], h.environment(self.out), seconds=15)
        self.assertIn(b"--previous-cell", text)
        self.assertIn(b"--contract", text)

    def test_real_readonly_child_yields_to_terminal_and_is_reaped(self):
        env = h.environment(self.out)
        def terminal():
            output = self.out / "yielding.stdout"
            return output.is_file() and b"HEALTH_READ_ENTERED" in output.read_bytes()
        with self.assertRaises(h.ObservationReady):
            h.command(self.out, "yielding", [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                "import time;print('HEALTH_READ_ENTERED',flush=True);time.sleep(30)"],
                env, seconds=15, read_ready=terminal)
        receipt = h.read_json(self.out / "yielding.closed.json")
        self.assertEqual(receipt["reason"], "readonly_query_yielded_to_terminal")
        self.assertTrue(receipt["stopped_while_running"])
        self.assertIsInstance(receipt["exit_code"], int)
        self.assertIn(b"HEALTH_READ_ENTERED", (self.out / "yielding.stdout").read_bytes())

    def test_readonly_watch_cannot_refresh_timeout_or_swallow_probe_errors(self):
        env = h.environment(self.out)
        command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", "import time;time.sleep(30)"]
        with self.assertRaisesRegex(RuntimeError, "timeout"):
            h.command(self.out, "watch-timeout", command, env, seconds=.2, read_ready=lambda: False)
        self.assertEqual(h.read_json(self.out / "watch-timeout.closed.json")["reason"], "timeout_outcome_unknown")
        def failed_probe():
            raise ValueError("damaged terminal marker")
        with self.assertRaisesRegex(ValueError, "damaged terminal"):
            h.command(self.out, "probe-error", command, env, seconds=15, read_ready=failed_probe)
        self.assertEqual(h.read_json(self.out / "probe-error.closed.json")["reason"], "caller_failed")

    def test_terminal_readiness_cannot_mask_an_observed_nonzero_exit(self):
        for exited_before_poll in (True, False):
            with self.subTest(exited_before_poll=exited_before_poll):
                owned = h.Process.__new__(h.Process)
                owned.argv = ["synthetic-read-only"]
                owned.process = Mock()
                owned.process.poll.return_value = 7 if exited_before_poll else None
                owned.process.wait.return_value = 7
                owned.close = Mock()
                ready = Mock(return_value=True) if exited_before_poll else Mock(side_effect=[False, True])
                with self.assertRaisesRegex(RuntimeError, "standard tool failed") as caught:
                    owned.wait(10, read_ready=ready)
                self.assertNotIsInstance(caught.exception, h.ObservationReady)
                if exited_before_poll:
                    ready.assert_not_called()
                    owned.process.wait.assert_not_called()
                else:
                    self.assertEqual(ready.call_count, 1)
                    owned.process.wait.assert_called_once()

    def test_health_priority_hook_is_cleared_before_other_commands(self):
        phone = self.phone()
        phone.server = Mock()
        capture = "1700000000000000-" + "a" * 24
        ready = lambda: True
        def read(out, label, argv, env, **kwargs):
            self.assertIs(kwargs["read_ready"], ready)
            raise h.ObservationReady("terminal ready")
        with patch.object(h, "listening", return_value=True), patch.object(h, "command", side_effect=read):
            with self.assertRaises(h.ObservationReady):
                phone.health(capture, terminal_ready=ready)
        self.assertIsNone(phone.read_ready)
        with patch.object(h, "listening", return_value=True), patch.object(h, "command", return_value=b"device") as cmd:
            phone.cmd(["get-state"])
        self.assertIsNone(cmd.call_args.kwargs["read_ready"])
        self.assertEqual(cmd.call_args.kwargs["deadline"], phone.deadline - 5)

    def test_absolute_command_deadline_includes_process_creation(self):
        process_type = h.Process
        for elapsed in (.75, 1.25):
            with self.subTest(elapsed=elapsed):
                now = [0.0]
                owned = process_type.__new__(process_type)
                owned.argv = ["synthetic-read-only"]
                owned.process = Mock()
                owned.process.wait.return_value = 0
                owned.close = Mock()
                path = self.out / ("absolute-%s.stdout" % elapsed)
                h.raw(path, b"original")
                owned.paths = dict(stdout=path)
                def construct(*args, **kwargs):
                    now[0] += elapsed
                    return owned
                with patch.object(h.time, "monotonic", lambda: now[0]), \
                     patch.object(h, "Process", side_effect=construct):
                    if elapsed < 1:
                        self.assertEqual(h.command(self.out, "synthetic", [], {}, seconds=1, deadline=1), b"original")
                        owned.process.wait.assert_called_once_with(timeout=.25)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "tool timeout"):
                            h.command(self.out, "synthetic", [], {}, seconds=1, deadline=1)
                        owned.process.wait.assert_not_called()
                        owned.close.assert_any_call("timeout_outcome_unknown")
        with patch.object(h.time, "monotonic", return_value=1), patch.object(h, "Process") as construct:
            with self.assertRaisesRegex(RuntimeError, "before launch"):
                h.command(self.out, "expired", [], {}, seconds=1, deadline=1)
        construct.assert_not_called()

    def test_mcu_process_check_and_commander_share_absolute_deadline(self):
        mcu = m.MCU(dict(probe_serial=123456), self.out / "mcu")
        now, calls = [0.0], []
        def command(out, label, argv, env, **kwargs):
            calls.append((label, kwargs["seconds"]))
            self.assertEqual(kwargs["deadline"], 5)
            now[0] += 2
            return b""
        with patch.object(m.time, "monotonic", lambda: now[0]), \
             patch.object(m, "os", SimpleNamespace(name="nt")), \
             patch.object(mcu, "tool", return_value=Path(sys.executable)), \
             patch.object(h, "command", side_effect=command):
            mcu.execute([], {}, "bounded", deadline=5)
            self.assertEqual(calls, [("processes", 5), ("commander", 3)])
            with self.assertRaisesRegex(RuntimeError, "observation deadline"):
                mcu.execute([], {}, "expired", deadline=4)
            self.assertEqual(len(calls), 2)
        for deadline in (True, float("nan"), float("inf")):
            with self.assertRaisesRegex(RuntimeError, "finite MCU"):
                m.MCU.remaining(180, deadline)

    def test_mcu_does_not_launch_commander_after_precheck_uses_remainder(self):
        mcu = m.MCU(dict(probe_serial=123456), self.out / "mcu")
        now, calls = [0.0], []
        def command(out, label, argv, env, **kwargs):
            calls.append(label)
            now[0] = 6
            return b""
        with patch.object(m.time, "monotonic", lambda: now[0]), \
             patch.object(m, "os", SimpleNamespace(name="nt")), \
             patch.object(mcu, "tool", return_value=Path(sys.executable)), \
             patch.object(h, "command", side_effect=command):
            with self.assertRaisesRegex(RuntimeError, "observation deadline"):
                mcu.execute([], {}, "spent-precheck", deadline=5)
        self.assertEqual(calls, ["processes"])

    def test_terminal_deadline_cannot_trigger_a_new_symbol_binding(self):
        mcu = m.MCU({}, self.out / "mcu")
        with patch.object(mcu, "bind") as binding, \
             self.assertRaisesRegex(RuntimeError, "prebound original base"):
            mcu.transfer_snapshot(b"synthetic", deadline=999)
        binding.assert_not_called()

    def test_expired_terminal_snapshot_never_starts_a_bound_read(self):
        mcu = m.MCU({}, self.out / "mcu")
        mcu.bound["base"] = {}
        with patch.object(m.time, "monotonic", return_value=100), \
             patch.object(mcu, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "observation deadline"):
                mcu.transfer_snapshot(bytes(420), deadline=100)
        execute.assert_not_called()

    def test_uncertain_device_action_retains_lock_and_blocks_next_action(self):
        # Patch only the lock root; all writes still pass the real boundary guard.
        with patch.object(h, "ROOT", self.out):
            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                with h.device_owner(self.out / "first"):
                    raise RuntimeError("uncertain")
            lock = self.out / ".cache/p34-live-device.lock"
            original = lock.read_bytes()
            with self.assertRaises(FileExistsError):
                with h.device_owner(self.out / "second"):
                    self.fail("another mutation ran")
            with patch.object(h, "command", return_value=b""), h.device_owner(self.out / "inspect", read_only=True):
                pass
            self.assertEqual(lock.read_bytes(), original)
            pid = json.loads(original)["pid"]
            with patch.object(h, "command", return_value=('"python.exe","%d"\n' % pid).encode()):
                with self.assertRaisesRegex(RuntimeError, "still running"):
                    with h.device_owner(self.out / "racing-inspect", read_only=True):
                        self.fail("raced the outstanding process")

    def test_outputs_and_pins_fail_closed(self):
        with self.assertRaises(ValueError):
            h.checked(ROOT.parent / "outside-p34-test")
        item = self.file("original.bin", b"original")
        self.assertTrue(h.pinned(item).is_file())
        for change in (dict(sha256="0" * 64), dict(bytes=1), dict(path="missing.bin")):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                h.pinned(dict(item, **change))
        with self.assertRaises(FileExistsError):
            h.raw(self.out / "original.bin", b"replacement")

    def test_full_frozen_command_not_substring_or_parameter_mix(self):
        argv = ["Tools/ota/p34-acceptance/live.py", "phone", "--inputs", "a.json", "--out", "b", "--baud", "921600"]
        command = "python -I -S -B -X utf8 " + " ".join(argv)
        live.frozen_invocation(command, argv)
        for changed in (command.replace("921600", "115200"), command + " --timeout-ms 500",
                        command.replace("-I ", ""), "python -c '" + command + "'"):
            with self.subTest(command=changed), self.assertRaises(RuntimeError):
                live.frozen_invocation(changed, argv)

    def test_actual_runner_dependencies_are_covered_by_standard_profiles(self):
        validator = h.host.load("p34_live_validator_test", ROOT / "Tools/acceptance/validate_bundle.py")
        config = validator.MANIFEST_PROFILE_CONFIG
        covered = set()
        for name in ("Production", "Validation", "Governance"):
            covered.update(validator._filter_profile_paths(live.COMMON_RUNNERS, config["profiles"][name]))
        self.assertEqual(set(live.COMMON_RUNNERS), covered)
        self.assertTrue(all((ROOT / name).is_file() for name in live.COMMON_RUNNERS))
        self.assertIn("Tools/ota/p34-acceptance/build.py", covered)
        self.assertIn("Tools/acceptance/validate_bundle.py", covered)

    def test_missing_contract_never_calls_a_tool(self):
        args = Mock(contract=None, matrix=None, command_id=None)
        with patch.object(h, "command") as command:
            with self.assertRaisesRegex(RuntimeError, "actual contract"):
                live.contract_gate(args, self.out)
            command.assert_not_called()

    def test_actual_accessor_parser_rejects_ambiguous_or_unrecognized_layout(self):
        good = "08020000 <ota_ble_session_active>:\n ldrb.w r0, [r0, #212]\n bx\tlr\n"
        self.assertEqual(m.byte_member(good, "ota_ble_session_active", 632), 212)
        for bad in (good.replace("#212", "#999"), good.replace("ldrb.w", "ldr"), good + good,
                    good.replace("ota_ble_session_active", "unrelated")):
            with self.assertRaises(RuntimeError):
                m.byte_member(bad, "ota_ble_session_active", 632)
        self.assertIsNone(m.symbols("20001000 00000010 B x\n20002000 00000010 B x")["x"])

    def test_install_matrix_rejects_app_only_downgrade_before_any_device_command(self):
        mcu = m.MCU({}, self.out / "mcu")
        with patch.object(mcu, "inspect") as inspect:
            for current, target in (("target", "base"), ("target", "maintenance"), ("base", "restore"),
                                    ("restore", "base"), ("initial", "maintenance"), ("base", "base")):
                with self.subTest(current=current, target=target), self.assertRaises(RuntimeError):
                    mcu.install(current, target)
            inspect.assert_not_called()
        self.assertEqual(m.INSTALL_PAIRS, {("initial", "base"), ("base", "maintenance"),
                                        ("maintenance", "base"), ("target", "restore")})

    def test_safe_install_waits_for_boot_and_rejects_wrong_storage_halt(self):
        mcu = m.MCU({}, self.out / "mcu")
        destination = h.pinned(self.file("candidate.bin", b"synthetic"))
        bound = dict(table={m.SYMBOLS["main_loop"]: (0x08020000, 12)}, image=destination)
        halted = dict(sdio=bytes(4), dhcsr=struct.pack("<I", 0x20000))
        calls = []
        def execute(commands, reads, label, **kwargs):
            calls.append((commands, label))
            return halted, "PC = 08020000", self.out
        with patch.object(mcu, "inspect", return_value=dict(registers=dict(freeze=0), storage=dict(journal=dict(committed_target=None)))), \
             patch.object(mcu, "bind", return_value=bound), patch.object(mcu, "execute", side_effect=execute), \
             patch.object(mcu, "wait_boot") as wait:
            mcu.install("initial", "base")
            wait.assert_called_once_with("base")
            script = "\n".join(str(x) for x, _ in calls)
            self.assertIn("0x08010000", script)
            self.assertNotIn("erase", script.lower())
            halted["sdio"] = struct.pack("<I", 0x2000)
            calls.clear()
            with self.assertRaisesRegex(RuntimeError, "halt not proved safe"):
                mcu.install("initial", "base")
            self.assertEqual(len(calls), 1)

    def test_stack_and_qspi_capacity_observations_are_not_constant_pass(self):
        stack = b"\xa5" * 4096 + bytes(4096)
        self.assertEqual(m.stack_observation(b"\x5a" * 32, stack)["high_water_bytes"], 4096)
        for guard, raw in ((bytes(32), stack), (b"\x5a" * 32, bytes(8192)), (b"\x5a" * 32, stack[:-1])):
            with self.assertRaises(RuntimeError):
                m.stack_observation(guard, raw)
        data = dict(disabled=b"\0", jedec=struct.pack("<I", 0xef4018), staging=b"\xff" * 4096,
                    candidate_slot=b"\xff" * 32, backup_slot=b"\xff" * 32, recovery_slot=b"\xff" * 32)
        self.assertEqual(m.storage_observation(data)["capacity_bytes"], 16777216)
        for changes in (dict(disabled=b"\1"), dict(jedec=bytes(4)), dict(candidate_slot=bytes(32))):
            with self.assertRaises(RuntimeError):
                m.storage_observation(dict(data, **changes))

    def test_health_requires_confirmed_advancing_idle_current_boot(self):
        data = dict(health0=struct.pack("<9I", 0, 0, 0, 10, 20, 30, 0, 1, 1),
            health1=struct.pack("<9I", 0, 0, 0, 10, 21, 31, 0, 1, 1), state=b"\4", snapped=b"\1",
            confirmed=b"\1", sd=b"\1", owner=b"\0", active=b"\0", isr=b"\0",
            **{key: struct.pack("<I", 0x08010800 if key == "vtor" else 0) for key in m.REGISTERS})
        self.assertIn("not an EEPROM dump", m.health_gate(data)["confirmation_source"])
        for changed in (dict(state=b"\3"), dict(active=b"\1"), dict(health1=data["health0"]),
                        dict(sd=b"\0"), dict(hfsr=struct.pack("<I", 1)), dict(vtor=bytes(4))):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                m.health_gate(dict(data, **changed))

    def test_journal_reference_zero_resume_and_noncontiguous_rejection(self):
        package = dict(bytes=1048576, sha256="a" * 64)
        raw = bytearray(b"\xff" * 4096)
        self.assertEqual(m.journal_observation(raw, package)["expected_begin_durable"], 0)
        journal = b"ETRJ" + bytes.fromhex(package["sha256"]) + struct.pack("<I", package["bytes"])
        raw[0x40:0x6c] = journal + struct.pack("<I", zlib.crc32(journal))
        raw[0x70] = 0xfc
        self.assertEqual(m.journal_observation(raw, package)["expected_begin_durable"], 8192)
        self.assertEqual(m.journal_observation(raw, dict(package, sha256="b" * 64))["expected_begin_durable"], 0)
        for offset in (0x40, 0x68, 0x71, 0x90):
            bad = bytearray(raw)
            bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                m.journal_observation(bad, package)

    def test_terminal_stack_is_bound_before_reboot_not_the_next_boot(self):
        mcu = m.MCU({}, self.out / "mcu")
        image = b"\0" * 0x400 + b"h" * 96
        file = h.pinned(self.file("image.bin", image))
        names = ("g_ota_link_metrics", "g_ota_metrics_publish_bytes", "__StackGuardStart", "__StackLimit", "system_core_clock", "SystemTickCount")
        bound = dict(image=file, table={name: (0x20000100 + i * 1000, 4) for i, name in enumerate(names)})
        data = dict(header_before=image[0x400:], header_after=image[0x400:], metrics=b"m" * 420,
            published=struct.pack("<I", 853), guard=b"\x5a" * 32, stack=b"\xa5" * 4096 + bytes(4096),
            clock=struct.pack("<I", 288000000), systick=struct.pack("<3I", 7, 287999, 10),
            vtor=struct.pack("<I", 0x08010800), wdt=struct.pack("<2I", 6, 1561),
            tick0=struct.pack("<I", 123000), tick1=struct.pack("<I", 123100))
        for name, raw in data.items():
            self.file(name + ".bin", raw)
        with patch.object(mcu, "bind", return_value=bound), patch.object(mcu, "execute", return_value=(data, "", self.out)):
            self.assertEqual(mcu.transfer_snapshot(data["metrics"])["stack"]["high_water_bytes"], 4096)
            for name, bad in (("header_after", bytes(96)), ("published", bytes(4)), ("vtor", bytes(4)), ("clock", bytes(4)), ("tick1", bytes(4))):
                original = data[name]
                data[name] = bad
                with self.subTest(name=name), self.assertRaises(RuntimeError):
                    mcu.transfer_snapshot(data["metrics"])
                data[name] = original

    def test_restore_mailbox_requires_exact_phase_backup_and_preserved_config(self):
        base, boot = b"synthetic backup", "a" * 64
        raw = bytearray(640)
        struct.pack_into("<16I", raw, 0, 0x41343352, 1, 1, 0, 100, 0, 0, 1,
                         30287, 30286, len(base), zlib.crc32(base), 0, 0, 0, 0)
        raw[319] = 0x55
        raw[576:608], raw[608:640] = bytes.fromhex(boot), hashlib.sha256(base).digest()
        self.assertEqual(m.restore_gate(raw, base, boot, 1)["phase"], 1)
        for offset in (0, 4, 8, 12, 28, 32, 36, 40, 44, 48, 319, 576, 608):
            bad = bytearray(raw)
            bad[offset] ^= 0x80
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                m.restore_gate(bad, base, boot, 1)
        struct.pack_into("<I", raw, 8, 3)
        struct.pack_into("<3I", raw, 48, 1, 0, 1)
        raw[448:576] = raw[192:320]
        self.assertEqual(m.restore_gate(raw, base, boot, 3)["mutation_started"], 1)
        raw[448] ^= 1
        with self.assertRaises(RuntimeError):
            m.restore_gate(raw, base, boot, 3)

    def test_rtt_down_uses_live_ring_indices_and_rejects_arbitrary_commands(self):
        mcu = m.MCU({}, self.out / "mcu")
        written, wr = [], [11]
        def read(address, size, label):
            return struct.pack("<6I", 0, 0x20002000, 16, wr[0], wr[0], 0)
        def execute(commands, *args):
            written.extend(commands)
            wr[0] = int(next(s for s in commands if s.startswith("w4 ")).split(", ")[1], 16)
        with patch.object(mcu, "signature", return_value=0x20001000), patch.object(mcu, "read", side_effect=read), \
             patch.object(mcu, "execute", side_effect=execute):
            mcu.down("probe 1 921600")
            self.assertTrue(any("0x2000200B" in line for line in written))
            self.assertTrue(any("0x20002000" in line for line in written))
            count = len(written)
            for text in ("erase", "at 1 AT+RESET", "rate set 1 1000000", "status\nrate set 1 115200"):
                with self.assertRaises(RuntimeError):
                    mcu.down(text)
            self.assertEqual(len(written), count)

    def test_private_adb_quotes_remote_shell_as_one_command(self):
        phone = self.phone()
        phone.server = Mock(alive=lambda: True)
        with patch.object(h, "listening", return_value=True), patch.object(h, "command", return_value=b"ok") as run:
            phone.cmd(["exec-out", "run-as", phone.pkg, "sh", "-c", "if test -e files/x; then printf yes; fi"])
        argv = run.call_args.args[2]
        self.assertEqual(argv[-2], "exec-out")
        self.assertIn("sh -c 'if test -e files/x; then printf yes; fi'", argv[-1])
        self.assertEqual(argv[1:7], ["-H", "127.0.0.1", "-P", "5062", "-s", "fixture"])

    def test_private_adb_owner_death_cannot_be_hidden_by_a_successful_client(self):
        phone = self.phone()
        phone.server = Mock()
        phone.server.alive.side_effect = [True, False]
        with patch.object(h, "listening", return_value=True), patch.object(h, "command", return_value=b"device"):
            with self.assertRaisesRegex(RuntimeError, "owner changed"):
                phone.cmd(["get-state"])

    def test_private_adb_commands_inherit_remaining_phase_not_a_fresh_timeout(self):
        phone = self.phone()
        phone.server = Mock(alive=lambda: True)
        phone.operation_deadline = 10
        with patch.object(p.time, "monotonic", return_value=8), patch.object(h, "listening", return_value=True), \
             patch.object(h, "command", return_value=b"original") as command:
            self.assertEqual(phone.cmd(["get-state"], seconds=60), b"original")
            self.assertEqual(command.call_args.kwargs["seconds"], 2)
        with patch.object(p.time, "monotonic", return_value=10), patch.object(h, "listening", return_value=True), \
             patch.object(h, "command") as command:
            with self.assertRaisesRegex(RuntimeError, "phase deadline"):
                phone.cmd(["get-state"])
            command.assert_not_called()

    def test_private_adb_success_after_phase_expiry_is_not_accepted(self):
        phone = self.phone()
        phone.server = Mock(alive=lambda: True)
        phone.operation_deadline = 10
        now = [8]

        def late_command(*args, **kwargs):
            now[0] = 11
            return b"late result"

        with patch.object(p.time, "monotonic", side_effect=lambda: now[0]), patch.object(h, "listening", return_value=True), \
             patch.object(h, "command", side_effect=late_command):
            with self.assertRaisesRegex(RuntimeError, "phase deadline"):
                phone.cmd(["get-state"])

    def test_remote_path_checks_allow_missing_children_not_links_or_escapes(self):
        phone = self.phone()
        def command(args, **kwargs):
            if args[-3:] == ["readlink", "-f", "."]:
                return b"/data/user/0/test.p34\n"
            self.assertIn("test ! -L files/p34-observations", args[-1])
            return b""
        with patch.object(phone, "cmd", side_effect=command):
            phone.safe_remote("files/p34-observations/new/health.json")
            for bad in ("/sdcard/x", "files/../x", "files/./x", "files/a;rm", "files//x"):
                with self.assertRaises(RuntimeError):
                    phone.safe_remote(bad)
        with patch.object(phone, "cmd", return_value=b"/data/user/0/other\n"):
            with self.assertRaises(RuntimeError):
                phone.safe_remote("files/new.json")

    def test_live_health_accepts_atomic_replacement_without_stat_cat_race(self):
        phone = self.phone()
        capture = "1790000000000000-" + "1" * 24
        old = self.health_bytes(capture, records=10, producerLines=9, bytes=9999)
        new = self.health_bytes(capture, records=11, producerLines=10, bytes=10000)
        self.assertNotEqual(len(old), len(new))
        files = {"files/p34-observations/" + capture + "/health.json":
                 lambda mode: old if mode == "stat" else new}
        with self.app_files(phone, files) as calls:
            value = phone.health(capture)
        self.assertEqual(value["producerLines"], 10)
        self.assertEqual([args[3] for args in calls].count("head"), 1)
        self.assertFalse(any(args[3] in ("stat", "cat") for args in calls))
        self.assertEqual(next(args for args in calls if args[3] == "head")[-2], "8193")

    def test_health_schema_identity_and_counters_fail_closed(self):
        phone = self.phone()
        capture = "1790000000000000-" + "1" * 24
        cases = [b"{}\n", b"[]\n", b"{broken}\n", b"\xff\n"]
        changes = [dict(schema=True), dict(schema=2), dict(captureId="other"),
            dict(time=None), dict(records=0), dict(records=4), dict(bytes=0),
            dict(bytes=p.observation_capture.MAX_BYTES + 1), dict(producerLines="2"),
            dict(upgradeStarts=False), dict(upgradeStarts="0"), dict(upgradeEnds="0"),
            dict(upgradeStarts=2, records=5), dict(upgradeEnds=1, records=4),
            dict(lost=-1), dict(lost=1.5), dict(healthy=1), dict(healthy=False),
            dict(error=12), dict(error="io-write"), dict(outcome="completed")]
        cases.extend(self.health_bytes(capture, **change) for change in changes)
        cases += [self.health_bytes(capture).replace(b'"schema": 1', b'"schema": 1, "schema": 1'),
                  self.health_bytes(capture).replace(b'"lost": 0', b'"lost": NaN')]
        for raw in cases:
            with self.subTest(raw=raw), self.app_files(phone, {
                    "files/p34-observations/" + capture + "/health.json": raw}):
                with self.assertRaises((RuntimeError, p.observation_capture.CaptureError)):
                    phone.health(capture)

    def test_live_health_bounds_truncation_and_io_errors_are_not_retried(self):
        phone = self.phone()
        capture = "1790000000000000-" + "1" * 24
        remote = "files/p34-observations/" + capture + "/health.json"
        for raw in (b"", b" " * 8193, self.health_bytes(capture)[:-1]):
            with self.subTest(raw=raw[:30]), self.app_files(phone, {remote: raw}) as calls:
                with self.assertRaises(RuntimeError):
                    phone.health(capture)
                self.assertEqual(sum(args[3] == "head" for args in calls), 1)
        def failed_read(mode):
            raise OSError("actual ADB read failure")
        with self.app_files(phone, {remote: failed_read}) as calls:
            with self.assertRaisesRegex(OSError, "actual ADB"):
                phone.health(capture)
        self.assertEqual(sum(args[3] == "head" for args in calls), 1)

    def test_unhealthy_capture_cannot_reach_download_readiness(self):
        phone = self.phone()
        phone.capture = "1790000000000000-" + "1" * 24
        remote = "files/p34-observations/" + phone.capture + "/health.json"
        for changes in (dict(lost=1, healthy=False), dict(error="io-write", healthy=False)):
            with self.subTest(changes=changes), self.app_files(phone, {
                    remote: self.health_bytes(phone.capture, **changes)}), \
                    patch.object(phone, "exists") as exists:
                with self.assertRaisesRegex(RuntimeError, "App observation failed"):
                    phone.downloaded("app_flutter/firmware/reference.etu", None)
                exists.assert_not_called()

    def test_provision_rejects_unknown_or_active_health_before_mutation(self):
        phone = self.phone()
        capture = "1790000000000000-" + "1" * 24
        remote = "files/p34-observations/" + capture + "/health.json"
        cases = [b"{}\n", self.health_bytes(capture, captureId="other"),
            self.health_bytes(capture, upgradeStarts="0", upgradeEnds="0"),
            self.health_bytes(capture, upgradeStarts=1, records=4)]
        for raw in cases:
            with self.subTest(raw=raw), self.app_files(phone, {remote: raw}) as calls, \
                    patch.object(phone, "captures", return_value={capture}), \
                    patch.object(phone, "exists", return_value=False):
                with self.assertRaises((RuntimeError, p.observation_capture.CaptureError)):
                    phone.provision({})
                self.assertFalse(any("force-stop" in args for args in calls))
        self.assertFalse((phone.out / "runtime.json").exists())

    def test_install_rejects_unknown_health_before_replacement(self):
        phone = self.phone()
        phone.plan["replace_apk_sha256"] = ["a" * 64]
        capture = "1790000000000000-" + "1" * 24
        with self.app_files(phone, {"files/p34-observations/" + capture + "/health.json": b"{}\n"}), \
                patch.object(phone, "start"), patch.object(phone, "captures", return_value={capture}):
            remote_command = phone.cmd
            def command(args, **kwargs):
                if args[:4] == ["shell", "pm", "list", "packages"]:
                    return ("package:" + phone.pkg).encode()
                if args[:3] == ["shell", "pm", "path"]:
                    return b"package:/data/app/synthetic/base.apk"
                if args[:2] == ["shell", "sha256sum"]:
                    return ("a" * 64 + "  /data/app/synthetic/base.apk").encode()
                self.assertNotEqual(args[0], "install")
                return remote_command(args, **kwargs)
            with patch.object(phone, "cmd", side_effect=command):
                with self.assertRaisesRegex(RuntimeError, "health fields"):
                    phone.install()

    def test_static_file_keeps_exact_size_and_limit_checks(self):
        phone = self.phone()
        remote = "app_flutter/firmware/reference.etu"
        with self.app_files(phone, {remote: lambda mode: b"old" if mode == "stat" else b"new!"}):
            with self.assertRaisesRegex(RuntimeError, "changed during read"):
                phone.file(remote)
        with self.app_files(phone, {remote: b"oversize"}) as calls:
            with self.assertRaisesRegex(RuntimeError, "file size"):
                phone.file(remote, 3)
        self.assertFalse(any(args[3] == "cat" for args in calls))

    def test_old_cached_package_alone_cannot_signal_start_ready(self):
        phone = self.phone()
        phone.pid, phone.capture = 123, "capture"
        phone.plan["package"] = self.file("package.etu", b"synthetic download")
        old, current = "1:2:18:100:100", ["1:2:18:100:100"]
        records = [dict(kind="open", pid=123, captureId="capture")]
        def file(remote, *args, **kwargs):
            if remote.endswith("events.jsonl"):
                return b"".join((json.dumps(row) + "\n").encode() for row in records)
            return b"synthetic download"
        with patch.object(phone, "health", return_value=dict(upgradeStarts=0, healthy=True)), patch.object(phone, "exists", return_value=True), \
             patch.object(phone, "file_stamp", side_effect=lambda path: current[0]), patch.object(phone, "file", side_effect=file):
            self.assertFalse(phone.downloaded("app_flutter/firmware/reference.etu", old))
            current[0] = "1:3:18:101:101"
            self.assertFalse(phone.downloaded("app_flutter/firmware/reference.etu", old))
            records.append(dict(kind="line", message="OTA_LINK_SAMPLE label=query kind=get_info us=123 ok=1"))
            self.assertTrue(phone.downloaded("app_flutter/firmware/reference.etu", old))
        self.assertTrue((phone.out / "downloaded.etu").is_file())

    def snapshot(self, phone, *, wrong_stamp=False):
        source, messages = stats_fixture.fixture()
        runtime = self.file("phone/runtime.json", b"synthetic runtime config")
        stamp = json.loads(messages[0][len("OTA_EXPERIMENT "):])
        stamp["configSha256"] = "0" * 64 if wrong_stamp else runtime["sha256"]
        messages[0] = "OTA_EXPERIMENT " + json.dumps(stamp)
        raw = stats_fixture.snapshot(source, messages)
        rows = [json.loads(line) for line in raw.splitlines()]
        phone.plan.update(sentinel=rows[0]["sentinel"], ble_address=rows[0]["target"], package=dict(sha256="a" * 64))
        phone.pid, phone.capture = rows[0]["pid"], rows[0]["captureId"]
        return raw, dict(runId="fixture")

    def test_actual_snapshot_reader_requires_pid_runtime_and_original_bytes(self):
        phone = self.phone()
        raw, cfg = self.snapshot(phone)
        with self.app_files(phone, self.snapshot_files(phone, raw)):
            value = phone.finished(phone.pid, phone.capture, cfg)
            self.assertTrue(value["success"])
        self.assertEqual((phone.out / "snapshot.jsonl").read_bytes(), raw)
        self.assertEqual(value["initialDurable"], 0)

    def test_wrong_runtime_stamp_keeps_snapshot_and_cannot_be_archived(self):
        phone = self.phone()
        raw, cfg = self.snapshot(phone, wrong_stamp=True)
        with self.app_files(phone, self.snapshot_files(phone, raw)):
            with self.assertRaisesRegex(RuntimeError, "runtime config"):
                phone.finished(phone.pid, phone.capture, cfg)
        self.assertEqual((phone.out / "snapshot.jsonl").read_bytes(), raw)
        with self.assertRaisesRegex(RuntimeError, "unverified capture"):
            phone.archive_capture()

    def test_finished_waits_for_snapshot_creation_and_footer_in_original_budget(self):
        phone = self.phone()
        raw, cfg = self.snapshot(phone)
        files = self.snapshot_files(phone, raw)
        snapshot = "files/p34-observations/" + phone.capture + "/snapshot-1.jsonl"
        now = [0.0]
        phone.deadline, phone.operation_deadline = 10, 4
        versions = (b"", b"", raw.rsplit(b"\n", 2)[0] + b"\n", raw[:-4], raw)
        files[snapshot] = lambda mode: versions[min(int(now[0] * 2), 4)]
        def sleep(seconds):
            now[0] += seconds
        with patch.object(p.time, "monotonic", side_effect=lambda: now[0]), \
                patch.object(p.time, "sleep", side_effect=sleep), \
                self.app_files(phone, files, listing=lambda: [] if now[0] == 0 else ["snapshot-1.jsonl"]):
            value = phone.finished(phone.pid, phone.capture, cfg)
        self.assertTrue(value["success"])
        self.assertEqual(now[0], 2)
        self.assertEqual(phone.operation_deadline, 4)
        self.assertEqual((phone.out / "snapshot.jsonl").read_bytes(), raw)

    def test_finished_missing_partial_and_query_only_snapshots_share_deadline(self):
        phone = self.phone()
        raw, cfg = self.snapshot(phone)
        rows = [json.loads(line) for line in raw.splitlines()]
        query = [row for row in rows[:-1] if row["kind"] not in ("upgrade-start", "upgrade-end")]
        for index, row in enumerate(query, 1):
            row["seq"] = index
        prefix = b"".join((json.dumps(row) + "\n").encode() for row in query)
        footer = dict(rows[-1], records=len(query), bytes=len(prefix), sha256=hashlib.sha256(prefix).hexdigest(),
                      upgradeStarts=0, upgradeEnds=0, outcome=None)
        query_raw = prefix + (json.dumps(footer) + "\n").encode()
        header = (json.dumps(query[0]) + "\n").encode()
        header_footer = dict(footer, records=1, producerLines=0, bytes=len(header),
                             sha256=hashlib.sha256(header).hexdigest())
        header_only = header + (json.dumps(header_footer) + "\n").encode()
        for pending in (None, raw[:-4], query_raw, header_only):
            files = self.snapshot_files(phone, raw)
            snapshot = "files/p34-observations/" + phone.capture + "/snapshot-1.jsonl"
            if pending is None:
                del files[snapshot]
            else:
                files[snapshot] = pending
            now = [0.0]
            phone.deadline, phone.operation_deadline = 10, 1.5
            def sleep(seconds):
                now[0] += seconds
            with self.subTest(pending=None if pending is None else len(pending)), \
                    patch.object(p.time, "monotonic", side_effect=lambda: now[0]), \
                    patch.object(p.time, "sleep", side_effect=sleep), self.app_files(phone, files):
                with self.assertRaisesRegex(RuntimeError, "observation deadline"):
                    phone.finished(phone.pid, phone.capture, cfg)
            self.assertEqual(now[0], 1.5)
            self.assertFalse((phone.out / "snapshot.jsonl").exists())

    def test_finished_rejects_sealed_corruption_without_waiting(self):
        phone = self.phone()
        raw, cfg = self.snapshot(phone)
        prefix, footer_raw, _ = raw.rsplit(b"\n", 2)
        footer = json.loads(footer_raw)
        footer["sha256"] = "0" * 64
        damaged = prefix + b"\n" + (json.dumps(footer) + "\n").encode()
        with self.app_files(phone, self.snapshot_files(phone, damaged)), patch.object(p.time, "sleep") as sleep:
            with self.assertRaisesRegex(p.observation_capture.CaptureError, "SHA-256 mismatch"):
                phone.finished(phone.pid, phone.capture, cfg)
            sleep.assert_not_called()
        self.assertEqual((phone.out / "snapshot.jsonl").read_bytes(), damaged)

    def test_finished_rejects_same_size_replacement_after_footer(self):
        phone = self.phone()
        raw, cfg = self.snapshot(phone)
        files = self.snapshot_files(phone, raw)
        changed = raw.replace(b'"seq":1,', b'"seq":9,', 1)
        self.assertTrue(raw != changed and len(raw) == len(changed), "fixture must change bytes, not size")
        files["files/p34-observations/" + phone.capture + "/snapshot-1.jsonl"] = \
            lambda mode: changed if mode == "cat" else raw
        with self.app_files(phone, files), patch.object(p.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "completed App snapshot changed"):
                phone.finished(phone.pid, phone.capture, cfg)
            sleep.assert_not_called()

    def test_finished_propagates_read_error_without_retry(self):
        phone = self.phone()
        raw, cfg = self.snapshot(phone)
        files = self.snapshot_files(phone, raw)
        def failed_read(mode):
            raise OSError("actual ADB snapshot read failure")
        files["files/p34-observations/" + phone.capture + "/snapshot-1.jsonl"] = failed_read
        with self.app_files(phone, files), patch.object(p.time, "sleep") as sleep:
            with self.assertRaisesRegex(OSError, "actual ADB snapshot"):
                phone.finished(phone.pid, phone.capture, cfg)
            sleep.assert_not_called()

    def test_salvage_keeps_growing_and_partial_originals_without_restart(self):
        phone = self.phone()
        phone.capture = "1790000000000000-" + "1" * 24
        phone.server = SimpleNamespace(alive=lambda: True)
        remote = "files/p34-observations/" + phone.capture
        originals = {"health.json": self.health_bytes(phone.capture),
            "events.jsonl": b'{"seq":1}\n{"seq":2}\n', "snapshot-1.jsonl": b'{"seq":1}\n{"seq":'}
        files = {remote + "/" + name: (lambda mode, raw=raw: raw[:-1] if mode == "stat" else raw)
                 for name, raw in originals.items()}
        with self.app_files(phone, files) as calls, patch.object(phone, "exists", side_effect=lambda path: path in files):
            phone.salvage()
        receipt = h.read_json(phone.out / "salvage.json")
        self.assertEqual(receipt["errors"], [])
        self.assertEqual(len(receipt["originals"]), 3)
        self.assertIn("not a finished snapshot", receipt["read_mode"])
        self.assertFalse(any(args[3] in ("stat", "cat", "rm", "force-stop") for args in calls))
        for name, raw in originals.items():
            self.assertEqual((phone.out / "salvage" / name).read_bytes(), raw)

    def test_salvage_preserves_other_originals_after_one_read_error(self):
        phone = self.phone()
        phone.capture = "1790000000000000-" + "1" * 24
        phone.server = SimpleNamespace(alive=lambda: True)
        remote = "files/p34-observations/" + phone.capture
        def failed_read(mode):
            raise OSError("health read failed")
        files = {remote + "/health.json": failed_read, remote + "/events.jsonl": b"exact partial bytes"}
        with self.app_files(phone, files), patch.object(phone, "exists", side_effect=lambda path: path in files):
            phone.salvage()
        receipt = h.read_json(phone.out / "salvage.json")
        self.assertEqual(receipt["errors"], [dict(file="health.json", error="health read failed")])
        self.assertEqual((phone.out / "salvage/events.jsonl").read_bytes(), b"exact partial bytes")

    def test_capture_archive_verifies_all_bytes_before_bounded_unlink(self):
        phone = self.phone()
        phone.pid, phone.capture = 123, "1791485067506601-646e66bbbe96e9c037f0f0d7"
        h.save(phone.out / "statistics.json", dict(synthetic=True))
        h.raw(phone.out / "runtime.json", b"synthetic config")
        data = {"events.jsonl": b"events", "health.json": b"health", "snapshot-1.jsonl": b"snapshot"}
        stopped, deleted, commands = [False], [], []
        def command(args, **kwargs):
            commands.append(args)
            if "pidof" in args: return b"" if stopped[0] else b"123\n"
            if "force-stop" in args: stopped[0] = True
            if "ls" in args: return "\n".join(data).encode()
            if "sha256sum" in args: return hashlib.sha256(data[args[-1].split("/")[-1]]).hexdigest().encode()
            if "rm" in args:
                self.assertTrue((phone.out / "archived.json").is_file())
                deleted.append(args[-1])
            return b""
        with patch.object(phone, "health", return_value=dict(upgradeStarts=1, upgradeEnds=1)), \
             patch.object(phone, "safe_remote"), patch.object(phone, "cmd", side_effect=command), \
             patch.object(phone, "file", side_effect=lambda remote, **kw: data[remote.split("/")[-1]]), \
             patch.object(phone, "exists", return_value=False):
            phone.archive_capture()
        self.assertEqual(len(deleted), 3)
        self.assertTrue(all(phone.capture in path for path in deleted))
        self.assertFalse(any("-r" in args or "clear" in args for args in commands))
        self.assertTrue(h.read_json(phone.out / "closed-capture.json")["remote_pruned"])

    def test_runtime_and_real_service_configuration_are_compatible(self):
        plan = dict(ble_address="E3:49:E1:14:D6:CB", package=self.file("reference.etu", service_fixture.container("patch")),
            images=dict(base=dict(image=dict(sha256=service_fixture.BASE)), target=dict(image=dict(sha256=service_fixture.TARGET))))
        cfg = p.config(plan, "host-test", "https://actual.example", 460800, 500)
        self.assertEqual((cfg["schema"], cfg["senderWindowSegments"], cfg["dataBatchFrames"]), (10, 24, 12))
        self.assertEqual(cfg["transferMode"], "full")  # Entire PATCH transfer, not a mislabeled asset kind.
        state = p.service.V2ServiceState(p.service_config(plan, "https://actual.example"), str(ROOT))
        self.assertEqual(state.releases["reference"].asset.kind, "patch")
        for origin in ("http://actual.example", "https://user@actual.example", "https://actual.example/path", "https://actual.example?x=1"):
            with self.assertRaises(RuntimeError):
                p.config(plan, "host-test", origin, 460800, 500)

    def test_soak_clock_uses_one_identity_real_gaps_and_excludes_prior_actions(self):
        campaign = h.fresh(self.out / "campaign")
        h.save(campaign / "old/result.json", dict(old=True))
        clock = h.fresh(self.out / "clock")
        ticks = [0]
        def monotonic_ns():
            return ticks[0]
        def sleep(seconds):
            if not (campaign / "new/intent.json").exists():
                h.save(campaign / "new/intent.json", dict(action="phone"))
            ticks[0] += int(seconds * 1e9)
        with patch.object(live.time, "monotonic_ns", side_effect=monotonic_ns), patch.object(live.time, "sleep", side_effect=sleep):
            live.soak_clock(clock, campaign, 2)
        rows = [json.loads(line) for line in (clock / "monotonic.jsonl").read_text().splitlines()]
        self.assertEqual(len({row["clock_id"] for row in rows}), 1)
        self.assertEqual(len({row["pid"] for row in rows}), 1)
        actions = [row for row in rows if row["kind"] == "action_observed"]
        self.assertEqual(len(actions), 1)
        self.assertIn("new/intent.json", actions[0]["original"]["path"].replace("\\", "/"))
        result = h.read_json(clock / "clock-result.json")
        self.assertEqual(result["max_heartbeat_gap_ns"], 1000000000)
        self.assertFalse(result["independent_acceptance"])


class ProcessCloseTests(unittest.TestCase):
    """Execute the real lifecycle methods with local streams and modeled APIs."""
    def setUp(self):
        parent = h.checked(Path(os.environ.get("P34_HOST_TEST_OUT", ROOT / ".cache/p34-live-tests")))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="close-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        platform = patch.object(h, "os", SimpleNamespace(name="nt"))
        platform.start()
        self.addCleanup(platform.stop)

    def owner(self, label="owned", code=0):
        owned = h.Process.__new__(h.Process)
        owned.out, owned.label = self.out, label
        owned.argv, owned.started, owned.closed = ["modeled-tool"], 1, False
        owned.paths = {name: h.checked(self.out / (label + "." + name))
                       for name in ("stdout", "stderr", "closed.json")}
        owned.streams = []
        for name, data in (("stdout", b"original\x00\xff\n"), ("stderr", b"original diagnostic\n")):
            stream = owned.paths[name].open("xb")
            self.addCleanup(stream.close)
            stream.write(data)
            stream.flush()
            owned.streams.append(stream)
        owned.process = Mock(returncode=code, pid=123, stdin=io.BytesIO())
        owned.process.poll.side_effect = lambda: owned.process.returncode
        def wait(timeout):
            if owned.process.returncode is None:
                raise h.subprocess.TimeoutExpired(owned.argv, timeout)
            return owned.process.returncode
        def stop():
            if owned.process.returncode is None:
                owned.process.returncode = 1
        owned.process.wait.side_effect = wait
        owned.process.kill.side_effect = stop
        owned.job = Mock()
        owned.job.terminate.side_effect = stop
        return owned

    def receipt(self, owned):
        self.assertTrue(owned.paths["closed.json"].is_file())
        value = h.read_json(owned.paths["closed.json"])
        self.assertEqual(owned.paths["stdout"].read_bytes(), b"original\x00\xff\n")
        self.assertEqual(owned.paths["stderr"].read_bytes(), b"original diagnostic\n")
        return value

    def assert_failed_once(self, owned, error):
        self.assertFalse(owned.closed)
        path = owned.paths["closed.json"]
        original, modified = path.read_bytes(), path.stat().st_mtime_ns
        job_calls, process_calls = list(owned.job.mock_calls), list(owned.process.mock_calls)
        with self.assertRaises(type(error)) as caught:
            owned.close("duplicate")
        self.assertIs(caught.exception, error)
        self.assertEqual(owned.job.mock_calls, job_calls)
        self.assertEqual(owned.process.mock_calls, process_calls)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), (original, modified))

    def test_close_normal_and_nonzero_exit_receipts_are_idempotent(self):
        for code in (0, 7):
            with self.subTest(code=code):
                owned = self.owner(str(code), code)
                owned.close()
                value = self.receipt(owned)
                self.assertEqual(value["exit_code"], code)
                self.assertEqual(value["exit_status"], "exited")
                self.assertEqual(value["cleanup_errors"], [])
                self.assertTrue(value["cleanup_complete"])
                self.assertTrue(owned.closed)
                self.assertTrue(all(stream.closed for stream in owned.streams))
                original = owned.paths["closed.json"].read_bytes()
                calls = list(owned.process.mock_calls)
                owned.close("duplicate")
                self.assertEqual(owned.paths["closed.json"].read_bytes(), original)
                self.assertEqual(owned.process.mock_calls, calls)
                owned.job.terminate.assert_called_once()
                owned.job.close.assert_called_once()

    def test_terminate_error_still_closes_handle_and_preserves_streams(self):
        owned = self.owner(code=None)
        error = OSError("terminate denied")
        owned.job.terminate.side_effect = error
        owned.job.close.side_effect = owned.process.kill.side_effect
        with self.assertRaises(OSError) as caught:
            owned.close("cancelled")
        self.assertIs(caught.exception, error)
        owned.job.close.assert_called_once()
        owned.process.wait.assert_called_once_with(timeout=5)
        value = self.receipt(owned)
        self.assertEqual(value["reason"], "cancelled")
        self.assertEqual(value["exit_code"], 1)
        self.assertFalse(value["job_terminated"])
        self.assertTrue(value["job_handle_closed"])
        self.assertFalse(value["cleanup_complete"])
        self.assertEqual(value["cleanup_errors"], [dict(step="job_terminate", type="OSError", message=str(error))])
        self.assertTrue(all(stream.closed for stream in owned.streams))
        self.assert_failed_once(owned, error)

    def test_handle_close_error_retains_known_exit_and_failure(self):
        owned = self.owner(code=None)
        error = OSError("handle close denied")
        owned.job.close.side_effect = error
        with self.assertRaises(OSError) as caught:
            owned.close()
        self.assertIs(caught.exception, error)
        value = self.receipt(owned)
        self.assertEqual(value["exit_code"], 1)
        self.assertEqual(value["exit_status"], "exited")
        self.assertTrue(value["job_terminated"])
        self.assertFalse(value["job_handle_closed"])
        self.assertEqual(value["cleanup_errors"][0]["step"], "job_close")
        self.assertFalse(value["cleanup_complete"])
        self.assert_failed_once(owned, error)

    def test_unreaped_process_is_unknown_after_bounded_fallback(self):
        owned = self.owner(code=None)
        errors = [OSError("terminate denied"), OSError("handle close denied"), OSError("kill denied")]
        owned.job.terminate.side_effect, owned.job.close.side_effect, owned.process.kill.side_effect = errors
        with self.assertRaises(OSError) as caught:
            owned.close()
        self.assertIs(caught.exception, errors[0])
        self.assertEqual([call.kwargs for call in owned.process.wait.call_args_list], [dict(timeout=5)] * 2)
        owned.process.kill.assert_called_once()
        value = self.receipt(owned)
        self.assertIsNone(value["exit_code"])
        self.assertEqual(value["exit_status"], "unknown")
        self.assertFalse(value["cleanup_complete"])
        self.assertEqual([item["step"] for item in value["cleanup_errors"]],
                         ["job_terminate", "job_close", "process_kill", "process_wait_after_kill"])
        self.assertIn("kill denied", "\n".join(caught.exception.__notes__))
        self.assert_failed_once(owned, errors[0])

    def test_fallback_reaps_after_first_wait_timeout(self):
        owned = self.owner(code=None)
        owned.job.terminate.side_effect = None
        owned.close()
        value = self.receipt(owned)
        self.assertEqual(value["exit_code"], 1)
        self.assertTrue(value["cleanup_complete"])
        self.assertEqual([call.kwargs for call in owned.process.wait.call_args_list], [dict(timeout=5)] * 2)
        owned.process.kill.assert_called_once()

    def test_wait_error_still_tries_bounded_owned_fallback(self):
        owned = self.owner(code=None)
        error = OSError("wait handle error")
        owned.process.wait.side_effect = [error, 1]
        with self.assertRaises(OSError) as caught:
            owned.close()
        self.assertIs(caught.exception, error)
        owned.process.kill.assert_called_once()
        self.assertEqual(owned.process.wait.call_count, 2)
        value = self.receipt(owned)
        self.assertEqual(value["exit_code"], 1)
        self.assertEqual(value["cleanup_errors"][0]["step"], "process_wait")

    def test_stream_close_error_does_not_skip_other_stream_or_receipt(self):
        owned = self.owner()
        stream = owned.streams[0]
        owned.streams[0] = Mock(wraps=stream)
        error = OSError("stdout close denied")
        owned.streams[0].close.side_effect = error
        with self.assertRaises(OSError) as caught:
            owned.close()
        self.assertIs(caught.exception, error)
        self.assertTrue(owned.streams[1].closed)
        self.assertTrue(owned.process.stdin.closed)
        value = self.receipt(owned)
        self.assertEqual(value["cleanup_errors"][0]["step"], "stdout_close")
        self.assertFalse(value["cleanup_complete"])
        self.assert_failed_once(owned, error)

    def test_receipt_failure_is_explicit_and_not_retried(self):
        owned = self.owner()
        error = OSError("receipt disk full")
        with patch.object(h, "save", side_effect=error) as save:
            for _ in range(2):
                with self.assertRaises(OSError) as caught:
                    owned.close()
                self.assertIs(caught.exception, error)
            save.assert_called_once()
        self.assertFalse(owned.closed)
        self.assertFalse(owned.paths["closed.json"].exists())
        self.assertTrue(all(stream.closed for stream in owned.streams))
        self.assertIn("close_receipt", "\n".join(error.__notes__))
        owned.job.terminate.assert_called_once()
        owned.job.close.assert_called_once()

    def test_command_preserves_primary_error_with_secondary_cleanup(self):
        for index, primary in enumerate((ValueError("primary operation failed"), KeyboardInterrupt("cancelled"))):
            with self.subTest(error=type(primary).__name__):
                owned = self.owner(str(index))
                secondary = OSError("secondary cleanup failed")
                owned.job.terminate.side_effect = secondary
                original_cause = LookupError("original cause")
                primary.__cause__ = original_cause
                owned.process.wait.side_effect = [primary, 0]
                observed, frames = None, []
                with patch.object(h, "Process", return_value=owned):
                    try:
                        h.command(self.out, "modeled", [], {}, seconds=1)
                    except BaseException as caught:
                        observed, frames = caught, traceback.extract_tb(caught.__traceback__)
                self.assertIs(observed, primary)
                self.assertIs(primary.__cause__, original_cause)
                self.assertIs(primary.process_cleanup_error, secondary)
                self.assertIn("secondary cleanup failed", "\n".join(primary.__notes__))
                self.assertIn("wait", [frame.name for frame in frames])
                self.assertEqual(self.receipt(owned)["reason"], "caller_failed")
                self.assert_failed_once(owned, secondary)

    def test_timeout_keeps_primary_with_cleanup_error(self):
        owned = self.owner(code=None)
        error = OSError("terminate denied")
        owned.job.terminate.side_effect = error
        owned.job.close.side_effect = owned.process.kill.side_effect
        with patch.object(h, "Process", return_value=owned):
            with self.assertRaisesRegex(RuntimeError, "tool timeout") as caught:
                h.command(self.out, "modeled", [], {}, seconds=1)
        self.assertIs(caught.exception.process_cleanup_error, error)
        self.assertEqual(self.receipt(owned)["reason"], "timeout_outcome_unknown")
        self.assertEqual(owned.process.wait.call_count, 2)

    def test_primary_reports_cleanup_and_receipt_failure_without_retries(self):
        owned = self.owner()
        primary, secondary = ValueError("operation failed"), OSError("terminate denied")
        owned.job.terminate.side_effect = secondary
        owned.process.wait.side_effect = [primary, 0]
        with patch.object(h, "Process", return_value=owned), \
             patch.object(h, "save", side_effect=OSError("receipt disk full")) as save:
            with self.assertRaises(ValueError) as caught:
                h.command(self.out, "modeled", [], {}, seconds=1)
            self.assertIs(caught.exception, primary)
            self.assertIs(primary.process_cleanup_error, secondary)
            notes = "\n".join(primary.__notes__)
            self.assertIn("terminate denied", notes)
            self.assertIn("close_receipt: OSError: receipt disk full", notes)
            with self.assertRaises(OSError) as repeated:
                owned.close()
            self.assertIs(repeated.exception, secondary)
            save.assert_called_once()
        self.assertFalse(owned.closed)
        self.assertFalse(owned.paths["closed.json"].exists())
        self.assertTrue(all(stream.closed for stream in owned.streams))
        owned.job.terminate.assert_called_once()
        owned.job.close.assert_called_once()

    def test_nonzero_exit_keeps_primary_with_cleanup_error(self):
        owned = self.owner(code=7)
        error = OSError("handle close denied")
        owned.job.close.side_effect = error
        with patch.object(h, "Process", return_value=owned):
            with self.assertRaisesRegex(RuntimeError, "standard tool failed") as caught:
                h.command(self.out, "modeled", [], {}, seconds=1)
        self.assertIs(caught.exception.process_cleanup_error, error)
        value = self.receipt(owned)
        self.assertEqual((value["reason"], value["exit_code"]), ("completed", 7))

    def test_ready_yield_cannot_hide_cleanup_error(self):
        owned = self.owner(code=None)
        error = OSError("handle close denied")
        owned.job.close.side_effect = error
        with patch.object(h, "Process", return_value=owned):
            with self.assertRaises(OSError) as caught:
                h.command(self.out, "modeled", [], {}, seconds=1, read_ready=lambda: True)
        self.assertIs(caught.exception, error)
        self.assertEqual(self.receipt(owned)["reason"], "readonly_query_yielded_to_terminal")

    def test_poll_and_stream_record_failures_still_write_truthful_receipt(self):
        owned = self.owner()
        error = OSError("poll denied")
        owned.process.poll.side_effect = error
        real_record = h.record
        def record(path):
            if path == owned.paths["stdout"]:
                raise OSError("stdout record unavailable")
            return real_record(path)
        with patch.object(h, "record", side_effect=record):
            with self.assertRaises(OSError) as caught:
                owned.close()
        self.assertIs(caught.exception, error)
        value = self.receipt(owned)
        self.assertIsNone(value["stopped_while_running"])
        self.assertEqual(value["exit_code"], 0)
        self.assertIsNone(value["stdout"])
        self.assertEqual(value["stderr"], h.record(owned.paths["stderr"]))
        self.assertEqual([item["step"] for item in value["cleanup_errors"]], ["poll_before_close", "stdout_record"])

    def test_launch_failure_preserves_error_and_closes_owned_streams(self):
        model = self.owner(code=None)
        primary, secondary = ValueError("assignment failed"), OSError("terminate denied")
        model.job.assign.side_effect = primary
        model.job.terminate.side_effect = secondary
        model.job.close.side_effect = model.process.kill.side_effect
        owned = h.Process.__new__(h.Process)
        with patch.object(h.host.owned, "WindowsJob", return_value=model.job), \
             patch.object(h.subprocess, "CREATE_NO_WINDOW", 0, create=True), \
             patch.object(h.subprocess, "Popen", return_value=model.process) as popen:
            with self.assertRaises(ValueError) as caught:
                owned.__init__(self.out, "launch", ["modeled-tool"], {})
        self.assertIs(caught.exception, primary)
        self.assertIs(primary.process_cleanup_error, secondary)
        self.assertTrue(all(stream.closed for stream in owned.streams))
        self.assertFalse(owned.closed)
        self.assertEqual(h.read_json(owned.paths["closed.json"])["reason"], "launch_failed")
        popen.assert_called_once()

    def test_command_success_cannot_swallow_cleanup_error(self):
        owned = self.owner()
        error = OSError("handle close denied")
        owned.job.close.side_effect = error
        with patch.object(h, "Process", return_value=owned), patch.object(owned, "wait", return_value=b"result"):
            with self.assertRaises(OSError) as caught:
                h.command(self.out, "modeled", [], {}, seconds=1)
        self.assertIs(caught.exception, error)
        self.assertFalse(self.receipt(owned)["cleanup_complete"])

    def test_no_process_launch_receipt_has_no_fabricated_exit(self):
        owned = self.owner()
        owned.process, owned.job = None, None
        owned.close("launch_failed")
        value = self.receipt(owned)
        self.assertIsNone(value["exit_code"])
        self.assertEqual(value["exit_status"], "not_started")
        self.assertTrue(value["cleanup_complete"])

    def test_posix_signal_error_does_not_skip_kill_or_receipt(self):
        owned = self.owner()
        owned.job = None
        error = OSError("SIGTERM denied")
        killpg = Mock(side_effect=[error, None])
        signals = SimpleNamespace(SIGTERM=15, SIGKILL=9)
        with patch.object(h, "os", SimpleNamespace(name="posix", killpg=killpg)), \
             patch.object(h, "signal", signals):
            with self.assertRaises(OSError) as caught:
                owned.close()
        self.assertIs(caught.exception, error)
        self.assertEqual([call.args for call in killpg.call_args_list],
                         [(123, signals.SIGTERM), (123, signals.SIGKILL)])
        self.assertEqual(self.receipt(owned)["cleanup_errors"][0]["step"], "process_group_sigterm")


class NetworkStartupTests(unittest.TestCase):
    def setUp(self):
        parent = h.checked(Path(os.environ.get("P34_HOST_TEST_OUT", ROOT / ".cache/p34-live-tests")))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="network-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        source = os.environ.get("P34_REFERENCE_ETU")
        self.payload = Path(source).read_bytes() if source else service_fixture.container("patch")
        self.package = h.raw(self.out / "reference.etu", self.payload)
        self.plan = dict(package=self.package,
            tools=dict(cloudflared=h.raw(self.out / "synthetic-cloudflared", b"never executed")),
            images=dict(base=dict(image=dict(sha256=service_fixture.BASE)),
                        target=dict(image=dict(sha256=service_fixture.TARGET))))

    @staticmethod
    def reader_program(mode):
        # Patch network I/O inside the child, not the actual HTTPS-reader entry.
        return ("import io,os,runpy,socket,sys,time,urllib.request\n"
                "from urllib.error import URLError\n"
                "def forbidden(*a,**k): raise AssertionError('real network forbidden')\n"
                "socket.create_connection=forbidden\n"
                "class Opener:\n"
                " def open(self,url,timeout):\n"
                "  if " + repr(mode) + " == 'block':\n"
                "   sys.stderr.write('BLOCKING_RESOLVER_FIXTURE pid=%d\\n'%os.getpid());sys.stderr.flush();time.sleep(60)\n"
                "  if " + repr(mode) + " == 'dns': raise URLError(socket.gaierror(11001,'fixture'))\n"
                "  return io.BytesIO(b'\\x00\\xfforiginal')\n"
                "urllib.request.build_opener=lambda *a: Opener()\n"
                "sys.argv=[" + repr(str(ROOT / "Tools/ota/p34-acceptance/live_phone.py")) + ", '--https-read']\n"
                "runpy.run_path(sys.argv[0],run_name='__main__')\n")

    @contextmanager
    def network(self, label="case", *, dns_until=0, dns_code=11001, exit_at=None,
                request_error=None, metadata_change=None, package_data=None,
                package_dns_once=False, real_clock=False, block_reader=False):
        out = h.fresh(self.out / label)
        world = SimpleNamespace(out=out, now=0.0, tools=[], requests=[], sleeps=[], package_dns=False,
                                origin="https://synthetic-startup.trycloudflare.com")
        world.network = p.Network(self.plan, out / "network")
        real_process = h.Process

        def advance(seconds):
            world.sleeps.append(seconds)
            world.now += seconds

        def open_url(url, timeout):
            world.requests.append(dict(url=url, timeout=timeout, at=world.now))
            if request_error is not None:
                raise request_error
            is_package = url.endswith("/package.etu")
            if world.now < dns_until or (is_package and package_dns_once and not world.package_dns):
                world.package_dns |= is_package
                raise URLError(p.socket.gaierror(dns_code, "synthetic resolver"))
            if is_package:
                return io.BytesIO(self.payload if package_data is None else package_data)
            asset = dict(kind="patch", baseImageSha256=service_fixture.BASE,
                sha256=self.package["sha256"], sizeBytes=len(self.payload),
                downloadUrl=world.origin + "/package.etu")
            asset.update(metadata_change or {})
            return io.BytesIO(json.dumps(dict(updateAvailable=True, asset=asset)).encode())

        def opener(handler):
            self.assertEqual(handler.proxies, {})
            return SimpleNamespace(open=open_url)

        class Tool:
            _close_after_error = real_process._close_after_error

            def __init__(inner, output, name, argv, env, *, stdin=None):
                inner.label, inner.closed, inner.stdin = name, False, stdin
                inner.process = SimpleNamespace(returncode=None)
                inner.paths = {key: output / (name + "." + key) for key in ("stdout", "stderr", "closed.json")}
                world.tools.append(inner)
                if name == "https-tunnel":
                    h.raw(inner.paths["stderr"], (world.origin + "\n").encode())
                    h.raw(inner.paths["stdout"], b"")

            def alive(inner):
                return not inner.closed and (exit_at is None or world.now < exit_at)

            def wait(inner, seconds, success_codes=(0,)):
                self.assertGreater(seconds, 0)
                packet = json.loads(inner.stdin)
                self.assertLessEqual(seconds, packet["timeout"])
                body, errors = io.BytesIO(), io.StringIO()
                try:
                    code = p._https_read(packet, body, errors)
                except Exception:
                    code = 1
                    errors.write(traceback.format_exc())
                h.raw(inner.paths["stdout"], body.getvalue())
                h.raw(inner.paths["stderr"], errors.getvalue().encode())
                inner.process.returncode = code
                inner.close()
                h.require(code in success_codes, "standard tool failed; inspect original command streams")
                return body.getvalue()

            def close(inner, reason="completed"):
                if inner.closed:
                    return
                inner.closed = True
                if inner.process.returncode is None:
                    inner.process.returncode = -15
                h.save(inner.paths["closed.json"], dict(synthetic=True, exit_code=inner.process.returncode, reason=reason))

        def process(output, name, argv, env, *, stdin=None):
            if name != "https-tunnel" and block_reader:
                value = real_process(output, name,
                    [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", self.reader_program("block")], env, stdin=stdin)
                world.tools.append(value)
                return value
            return Tool(output, name, argv, env, stdin=stdin)

        with ExitStack() as stack:
            stack.enter_context(patch.object(h, "Process", side_effect=process))
            stack.enter_context(patch.object(p, "build_opener", side_effect=opener))
            if not real_clock:
                stack.enter_context(patch.object(p.time, "monotonic", side_effect=lambda: world.now))
                stack.enter_context(patch.object(p.time, "sleep", side_effect=advance))
            try:
                yield world
            finally:
                world.network.close()
                self.assertFalse(h.listening(world.network.server.server_address[1]) if world.network.server else False)
                self.assertTrue(all(not tool.alive() for tool in world.tools))

    def assert_failed_closed(self, world):
        self.assertFalse((world.network.out / "ready.json").exists())
        self.assertTrue((world.network.out / "startup-failed.json").is_file())
        self.assertTrue(world.network.closed)
        self.assertTrue(h.read_json(world.network.out / "closed.json")["tunnel_closed"])
        self.assertTrue(all(not tool.alive() for tool in world.tools))
        if world.network.server:
            self.assertFalse(h.listening(world.network.server.server_address[1]))

    def test_actual_start_recovers_dns_on_one_tunnel_with_original_deadline(self):
        with self.network(dns_until=2) as world:
            self.assertEqual(world.network.start(deadline=8), world.origin)
            self.assertEqual(world.now, 2)
            self.assertEqual(sum(tool.label == "https-tunnel" for tool in world.tools), 1)
            self.assertEqual((world.network.out / "https-package.etu").read_bytes(), self.payload)
            self.assertEqual(h.read_json(world.network.out / "ready.json")["prepare_deadline_monotonic"], 8)
            self.assertEqual([r["timeout"] for r in world.requests], [8, 7, 6, 6])
            for number in (1, 2):
                self.assertEqual(h.read_json(world.network.out / ("https-read-%03d.closed.json" % number))["exit_code"], 75)

    def test_dns_again_and_package_dns_do_not_restart_tunnel(self):
        for label, options in (("again", dict(dns_until=1, dns_code=p.socket.EAI_AGAIN)),
                               ("package", dict(package_dns_once=True))):
            with self.subTest(label=label), self.network(label, **options) as world:
                world.network.start(deadline=10)
                self.assertEqual(sum(tool.label == "https-tunnel" for tool in world.tools), 1)
                self.assertEqual((world.network.out / "https-package.etu").read_bytes(), self.payload)

    def test_permanent_dns_fails_within_original_budget_and_closes(self):
        with self.network(dns_until=1000) as world:
            with self.assertRaisesRegex(RuntimeError, "deadline"):
                world.network.start(deadline=2.25)
            self.assertEqual(world.now, 2.25)
            self.assertEqual(world.sleeps, [1, 1, .25])
            self.assertEqual(sum(tool.label == "https-tunnel" for tool in world.tools), 1)
            self.assert_failed_closed(world)

    def test_expired_prepare_deadline_never_creates_tunnel(self):
        with self.network() as world:
            with self.assertRaisesRegex(RuntimeError, "deadline"):
                world.network.start(deadline=0)
            self.assertFalse(world.tools)
            self.assert_failed_closed(world)

    def test_tunnel_exit_during_dns_wait_fails_without_another_request(self):
        with self.network(dns_until=100, exit_at=.5) as world:
            with self.assertRaisesRegex(RuntimeError, "tunnel stopped"):
                world.network.start(deadline=10)
            self.assertEqual(len(world.requests), 1)
            self.assert_failed_closed(world)

    def test_wrong_metadata_is_not_retried_or_downloaded(self):
        changes = [dict(kind="full"), dict(baseImageSha256="0" * 64), dict(sha256="0" * 64),
                   dict(sizeBytes=len(self.payload) + 1), dict(downloadUrl="https://different.invalid/package.etu")]
        for index, change in enumerate(changes):
            with self.subTest(change=change), self.network(str(index), metadata_change=change) as world:
                with self.assertRaisesRegex(RuntimeError, "metadata identity"):
                    world.network.start(deadline=10)
                self.assertEqual(len(world.requests), 1)
                self.assert_failed_closed(world)

    def test_wrong_or_short_package_is_not_retried(self):
        for index, data in enumerate((self.payload[:-1], self.payload + b"x", self.payload[:-1] + bytes([self.payload[-1] ^ 1]))):
            with self.subTest(index=index), self.network(str(index), package_data=data) as world:
                with self.assertRaisesRegex(RuntimeError, "original bytes mismatch"):
                    world.network.start(deadline=10)
                self.assertEqual(len(world.requests), 2)
                self.assert_failed_closed(world)

    def test_tls_http_unknown_dns_and_non_dns_errors_are_not_retried(self):
        errors = [URLError(ssl.SSLCertVerificationError(1, "synthetic certificate")),
                  HTTPError("https://synthetic.invalid", 503, "synthetic", {}, None),
                  URLError(p.socket.gaierror(11003, "synthetic permanent resolver error")),
                  URLError(ConnectionRefusedError("synthetic connection refusal")),
                  URLError("11001 is text, not a DNS exception")]
        for index, error in enumerate(errors):
            with self.subTest(index=index), self.network(str(index), request_error=error) as world:
                with self.assertRaisesRegex(RuntimeError, "standard tool failed"):
                    world.network.start(deadline=10)
                self.assertEqual(len(world.requests), 1)
                self.assert_failed_closed(world)

    def test_actual_phone_cell_uses_remaining_prepare_time_and_gates_phone(self):
        for label, ready in (("ready", True), ("not-ready", False)):
            with self.subTest(label=label), self.network(label, dns_until=597 if ready else 1000) as world:
                phone = Mock(out=world.out / "phone", deadline=3390)
                mcu = Mock()

                def inspect(*args):
                    world.now = 595
                    return dict(storage=dict(journal=dict(expected_begin_durable=0)))

                def phone_start():
                    self.assertTrue((world.network.out / "ready.json").is_file())
                    self.assertEqual(world.now, 597)
                    raise RuntimeError("stop before any phone I/O")

                mcu.inspect.side_effect = inspect
                phone.start.side_effect = phone_start
                args = SimpleNamespace(seconds=3390, run_role="clean", checkpoint_kib=None, previous_cell=None)
                with patch.object(live, "MCU", return_value=mcu), patch.object(live, "Phone", return_value=phone), \
                     patch.object(live, "Network", return_value=world.network):
                    with self.assertRaisesRegex(RuntimeError, "stop before any phone I/O" if ready else "deadline"):
                        live.phone_cell(self.plan, world.out, args)
                self.assertEqual(phone.start.call_count, int(ready))
                phone.provision.assert_not_called()
                phone.cmd.assert_not_called()
                self.assertEqual(world.now, 597 if ready else 600)

    def test_actual_isolated_https_reader_preserves_binary_and_typed_dns_exit(self):
        packet = json.dumps(dict(url="https://synthetic.invalid", timeout=5, limit=100)).encode()
        for mode, exit_code in (("ok", 0), ("dns", 75)):
            with self.subTest(mode=mode):
                data = h.command(self.out, mode, [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                    self.reader_program(mode)], h.environment(self.out), seconds=10, stdin=packet,
                    success_codes=(exit_code,))
                self.assertEqual(data, b"\x00\xfforiginal" if mode == "ok" else b"")
                self.assertEqual(h.read_json(self.out / (mode + ".closed.json"))["exit_code"], exit_code)
                if mode == "dns":
                    self.assertEqual(h.read_json(self.out / "dns.stderr"), dict(dns_errno=11001))

    def test_blocking_resolver_is_killed_by_existing_process_owner(self):
        packet = json.dumps(dict(url="https://synthetic.invalid", timeout=2, limit=100)).encode()
        started = p.time.monotonic()
        reader = h.Process(self.out, "blocking-resolver", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
            "-c", self.reader_program("block")], h.environment(self.out), stdin=packet)
        self.addCleanup(reader.close, "fixture_finished")

        def entered():
            self.assertTrue(reader.alive(), "reader exited before blocking fixture handshake")
            marker = reader.paths["stderr"].read_text(encoding="utf-8")
            if not marker.endswith("\n"):
                return None
            self.assertRegex(marker, r"^BLOCKING_RESOLVER_FIXTURE pid=[1-9][0-9]*\n$")
            return int(marker.split("=", 1)[1])

        # Startup is not the fault under test. Actual Network.start/phone_cell
        # cases above separately verify the unchanged absolute prepare budget.
        child_pid = h.wait_for(entered, 30)
        startup_seconds = p.time.monotonic() - started
        self.assertNotEqual(child_pid, reader.process.pid)
        wait_child = child_handle = None
        if os.name == "nt":
            from ctypes import wintypes
            kernel = reader.job.kernel
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            child_handle = kernel.OpenProcess(0x00100000, False, child_pid)  # SYNCHRONIZE
            self.assertTrue(child_handle, "cannot observe the actual reader process")
            self.addCleanup(kernel.CloseHandle, child_handle)
            wait_child = kernel.WaitForSingleObject
            self.assertEqual(wait_child(child_handle, 0), 258)  # WAIT_TIMEOUT: still running

        termination_started = p.time.monotonic()
        deadline = termination_started + 2
        with self.assertRaisesRegex(RuntimeError, "tool timeout"):
            reader.wait(deadline - p.time.monotonic())
        termination_seconds = p.time.monotonic() - termination_started
        self.assertLess(termination_seconds, 17)  # Existing Job/launcher close allowance.
        self.assertTrue(reader.closed)
        self.assertFalse(reader.alive())
        child_wait_result = wait_child(child_handle, 0) if wait_child else None
        if wait_child:
            self.assertEqual(child_wait_result, 0)  # WAIT_OBJECT_0: retained child handle signaled
        receipt = h.read_json(reader.paths["closed.json"])
        self.assertEqual(receipt["reason"], "timeout_outcome_unknown")
        self.assertTrue(receipt["stopped_while_running"])
        self.assertEqual(reader.paths["stdout"].read_bytes(), b"")
        marker = reader.paths["stderr"].read_text(encoding="utf-8")
        self.assertIn("BLOCKING_RESOLVER_FIXTURE pid=%d" % child_pid, marker)
        print("BLOCKING_RESOLVER_PROOF " + json.dumps(dict(marker=marker.strip(),
            startup_seconds=startup_seconds, timeout_seconds=2, termination_seconds=termination_seconds,
            reason=receipt["reason"], exit_code=receipt["exit_code"],
            launcher_exited=not reader.alive(), child_wait_result=child_wait_result)), flush=True)


class CallerCloseTests(unittest.TestCase):
    """Caller methods and Process are real; device and Job APIs stay modeled."""
    owner = ProcessCloseTests.owner
    file = LiveRouteTests.file
    phone = LiveRouteTests.phone

    def setUp(self):
        NetworkStartupTests.setUp(self)
        platform = patch.object(h, "os", SimpleNamespace(**(vars(os) | dict(name="nt"))))
        platform.start()
        self.addCleanup(platform.stop)

    def network_model(self, label="network"):
        network = p.Network(self.plan, self.out / label)
        network.tunnel = self.owner(label + "-tunnel")
        network.server = Mock()
        network.thread = Mock(ident=123)
        network.thread.is_alive.return_value = False
        network.log_handler = Mock()
        return network

    def phone_model(self):
        phone = self.phone()
        phone.server = self.owner("private-server", code=None)
        return phone

    def assert_network_drained_once(self, network):
        network.server.shutdown.assert_called_once()
        network.server.server_close.assert_called_once()
        network.thread.join.assert_called_once_with(timeout=5)
        network.log_handler.close.assert_called_once()
        network.tunnel.job.terminate.assert_called_once()
        network.tunnel.job.close.assert_called_once()

    def assert_duplicate_failure(self, owner, error):
        receipt = owner.out / "closed.json"
        original = (receipt.read_bytes(), receipt.stat().st_mtime_ns) if receipt.exists() else None
        with patch.object(h, "save") as save, patch.object(h, "command") as command, \
             patch.object(h, "listening") as listening:
            with self.assertRaises(type(error)) as caught:
                owner.close()
            self.assertIs(caught.exception, error)
            save.assert_not_called()
            command.assert_not_called()
            listening.assert_not_called()
        self.assertEqual((receipt.read_bytes(), receipt.stat().st_mtime_ns) if receipt.exists() else None, original)

    def failed_start(self, label, *, code=7, reader_error=None, tunnel_error=None):
        network = p.Network(self.plan, self.out / label)
        tunnel = self.owner(label + "-tunnel", code=None)
        tunnel.streams[1].write(b"https://caller-fixture.trycloudflare.com\n")
        tunnel.streams[1].flush()
        reader = self.owner(label + "-reader", code=code)
        reader.job.close.side_effect = reader_error
        tunnel.job.close.side_effect = tunnel_error
        observed = []
        real_wait = reader.wait
        def wait(*args, **kwargs):
            try:
                return real_wait(*args, **kwargs)
            except BaseException as error:
                observed.append(error)
                raise
        def release_fixture():
            if network.thread and network.thread.is_alive():
                network.server.shutdown()
                network.thread.join(timeout=5)
            if network.server and network.server.fileno() >= 0:
                network.server.server_close()
            if network.log_handler and network.log_handler.stream is not None:
                network.log_handler.close()
        self.addCleanup(release_fixture)
        error, frames = None, []
        with patch.object(h, "Process", side_effect=[tunnel, reader]) as construct, \
             patch.object(reader, "wait", side_effect=wait):
            try:
                network.start(deadline=p.time.monotonic() + 10)
            except BaseException as caught:
                error, frames = caught, traceback.extract_tb(caught.__traceback__)
        self.assertEqual(construct.call_count, 2)
        self.assertIsNotNone(error)
        self.assertEqual(len(observed), 1)
        self.assertFalse(network.thread.is_alive())
        self.assertEqual(network.server.fileno(), -1)
        self.assertIsNone(network.log_handler.stream)
        return SimpleNamespace(network=network, tunnel=tunnel, reader=reader, error=error,
                               primary=observed[0], frames=frames)

    def test_network_normal_close_is_idempotent(self):
        network = self.network_model()
        network.close()
        value = h.read_json(network.out / "closed.json")
        self.assertTrue(network.closed)
        self.assertTrue(value["cleanup_complete"])
        self.assertTrue(value["thread_closed"] and value["tunnel_closed"])
        self.assertEqual(value["cleanup_errors"], [])
        original = (network.out / "closed.json").read_bytes()
        network.close()
        self.assertEqual((network.out / "closed.json").read_bytes(), original)
        self.assert_network_drained_once(network)

    def test_network_tunnel_failure_does_not_skip_remaining_cleanup(self):
        for stage in ("terminate", "close"):
            with self.subTest(stage=stage):
                network = self.network_model(stage)
                error = OSError("tunnel " + stage + " failed")
                getattr(network.tunnel.job, stage).side_effect = error
                with self.assertRaises(OSError) as caught:
                    network.close()
                self.assertIs(caught.exception, error)
                self.assert_network_drained_once(network)
                self.assertFalse(network.closed)
                value = h.read_json(network.out / "closed.json")
                self.assertFalse(value["cleanup_complete"])
                self.assertTrue(value["thread_closed"])
                self.assertEqual(value["cleanup_errors"][0]["step"], "tunnel_close")
                self.assert_duplicate_failure(network, error)
                self.assert_network_drained_once(network)

    def test_network_multiple_cleanup_failures_are_retained(self):
        network = self.network_model()
        first = OSError("tunnel close failed")
        network.tunnel.job.close.side_effect = first
        network.server.shutdown.side_effect = OSError("shutdown failed")
        network.server.server_close.side_effect = OSError("server close failed")
        network.thread.join.side_effect = OSError("join failed")
        network.log_handler.close.side_effect = OSError("log close failed")
        with self.assertRaises(OSError) as caught:
            network.close()
        self.assertIs(caught.exception, first)
        self.assert_network_drained_once(network)
        value = h.read_json(network.out / "closed.json")
        self.assertEqual([item["step"] for item in value["cleanup_errors"]],
                         ["tunnel_close", "http_shutdown", "http_server_close", "http_thread_join", "http_log_close"])
        self.assertIn("log close failed", "\n".join(first.__notes__))
        self.assertFalse(value["cleanup_complete"])
        self.assert_duplicate_failure(network, first)

    def test_network_receipt_failure_does_not_retry_cleanup(self):
        network = self.network_model()
        error, real_save = OSError("network receipt unavailable"), h.save
        def save(path, value):
            if path == network.out / "closed.json":
                raise error
            return real_save(path, value)
        with patch.object(h, "save", side_effect=save):
            with self.assertRaises(OSError) as caught:
                network.close()
        self.assertIs(caught.exception, error)
        self.assertFalse(network.closed)
        self.assertIn("close_receipt", "\n".join(error.__notes__))
        self.assert_duplicate_failure(network, error)
        self.assert_network_drained_once(network)

    def test_network_unstarted_http_thread_is_not_shutdown_or_joined(self):
        network = p.Network(self.plan, self.out / "unstarted")
        network.server = p.service.ThreadingHTTPServer(("127.0.0.1", 0), p.service.P33RequestHandler)
        self.addCleanup(network.server.server_close)
        network.thread = p.threading.Thread(target=network.server.serve_forever, daemon=True)
        network.log_handler = Mock()
        with patch.object(network.server, "shutdown", side_effect=AssertionError("unstarted shutdown can deadlock")) as shutdown, \
             patch.object(network.thread, "join", side_effect=AssertionError("cannot join before start")) as join:
            network.close()
            shutdown.assert_not_called()
            join.assert_not_called()
        self.assertTrue(network.closed)
        self.assertEqual(network.server.fileno(), -1)
        network.log_handler.close.assert_called_once()
        self.assertTrue(h.read_json(network.out / "closed.json")["thread_closed"])

    def test_network_live_or_unknown_thread_is_not_confirmed_closed(self):
        for label, observation in (("alive", True), ("unknown", OSError("thread state unknown"))):
            with self.subTest(label=label):
                network = self.network_model(label)
                if isinstance(observation, BaseException):
                    network.thread.is_alive.side_effect = observation
                else:
                    network.thread.is_alive.return_value = observation
                with self.assertRaises((RuntimeError, OSError)) as caught:
                    network.close()
                value = h.read_json(network.out / "closed.json")
                self.assertIs(value["thread_closed"], False if label == "alive" else None)
                self.assertFalse(value["cleanup_complete"])
                self.assert_duplicate_failure(network, caught.exception)
                self.assert_network_drained_once(network)

    def test_network_read_preserves_nonzero_error_and_cleanup_diagnostics(self):
        for label, cleanup in (("normal", None), ("cleanup-failed", OSError("reader handle close failed"))):
            with self.subTest(label=label):
                case = self.failed_start(label, reader_error=cleanup)
                self.assertIs(case.error, case.primary)
                self.assertIsInstance(case.error, RuntimeError)
                self.assertIn("standard tool failed", str(case.error))
                self.assertIn("wait", [frame.name for frame in case.frames])
                if cleanup:
                    self.assertIs(case.error.process_cleanup_error, cleanup)
                value = h.read_json(case.network.out / "startup-failed.json")
                self.assertEqual((value["error_type"], value["message"]), ("RuntimeError", str(case.primary)))
                self.assertEqual(h.read_json(case.reader.paths["closed.json"])["exit_code"], 7)
                case.reader.job.terminate.assert_called_once()
                case.reader.job.close.assert_called_once()

    def test_network_reader_cleanup_failure_alone_stays_failure(self):
        error = OSError("reader cleanup failed after exit zero")
        case = self.failed_start("read-success", code=0, reader_error=error)
        self.assertIs(case.error, error)
        self.assertEqual(h.read_json(case.reader.paths["closed.json"])["exit_code"], 0)
        self.assertFalse((case.network.out / "ready.json").exists())
        self.assertEqual(h.read_json(case.network.out / "startup-failed.json")["error_type"], "OSError")

    def test_network_start_retains_reader_and_outer_cleanup_errors(self):
        reader_error, tunnel_error = OSError("reader handle close failed"), OSError("tunnel close failed")
        case = self.failed_start("both-cleanups", reader_error=reader_error, tunnel_error=tunnel_error)
        self.assertIs(case.error, case.primary)
        self.assertIs(case.error.process_cleanup_error, reader_error)
        self.assertIs(case.error.network_cleanup_error, tunnel_error)
        notes = "\n".join(case.error.__notes__)
        self.assertIn(str(reader_error), notes)
        self.assertIn(str(tunnel_error), notes)
        value = h.read_json(case.network.out / "startup-failed.json")
        self.assertEqual(value["error_type"], "RuntimeError")
        self.assertIn(str(reader_error), "\n".join(value["notes"]))
        self.assertIn(str(tunnel_error), "\n".join(value["notes"]))
        self.assertFalse(case.network.closed)
        self.assert_duplicate_failure(case.network, tunnel_error)

    def test_network_start_receipt_failure_preserves_primary_and_drains(self):
        for label, close_error in (("clean-close", None), ("failed-close", OSError("outer cleanup failed"))):
            with self.subTest(label=label):
                network = self.network_model(label)
                network.tunnel.job.close.side_effect = close_error
                primary, receipt_error = ValueError("startup operation failed"), OSError("startup receipt unavailable")
                cause = LookupError("original cause")
                primary.__cause__ = cause
                resources = {name: getattr(network, name) for name in ("server", "thread", "tunnel", "log_handler")}
                for name in resources:
                    setattr(network, name, None)
                def fail_start(deadline):
                    for name, resource in resources.items():
                        setattr(network, name, resource)
                    raise primary
                real_save = h.save
                def save(path, value):
                    if path == network.out / "startup-failed.json":
                        raise receipt_error
                    return real_save(path, value)
                with patch.object(network, "_start", side_effect=fail_start) as start, patch.object(h, "save", side_effect=save):
                    with self.assertRaises(ValueError) as caught:
                        network.start(deadline=p.time.monotonic() + 10)
                    self.assertIs(caught.exception, primary)
                    self.assertIs(primary.__cause__, cause)
                    self.assertIs(primary.startup_receipt_error, receipt_error)
                    self.assertIn(str(receipt_error), "\n".join(primary.__notes__))
                    if close_error:
                        self.assertIs(primary.network_cleanup_error, close_error)
                    with self.assertRaisesRegex(RuntimeError, "single-use"):
                        network.start(deadline=p.time.monotonic() + 10)
                    start.assert_called_once()
                self.assert_network_drained_once(network)
                self.assertFalse((network.out / "startup-failed.json").exists())
                self.assertEqual(network.closed, close_error is None)

    def test_phone_normal_close_is_single_use(self):
        phone = self.phone_model()
        with patch.object(h, "listening", side_effect=lambda port: phone.server.process.returncode is None), \
             patch.object(h, "command", return_value=b"") as stop:
            phone.close()
            original = (phone.out / "closed.json").read_bytes()
            phone.close()
            self.assertEqual((phone.out / "closed.json").read_bytes(), original)
            stop.assert_called_once()
            self.assertEqual(stop.call_args.kwargs["seconds"], 10)
            self.assertEqual(stop.call_args.args[1], "adb-stop")
        self.assertTrue(phone.closed)
        self.assertTrue(h.read_json(phone.out / "closed.json")["cleanup_complete"])
        phone.server.job.terminate.assert_called_once()
        phone.server.job.close.assert_called_once()

    def test_phone_stop_error_survives_server_cleanup_failure(self):
        phone = self.phone_model()
        primary, cleanup = ValueError("private stop failed"), OSError("server handle close failed")
        phone.server.job.close.side_effect = cleanup
        with patch.object(h, "listening", side_effect=lambda port: phone.server.process.returncode is None), \
             patch.object(h, "command", side_effect=primary) as stop:
            with self.assertRaises(BaseException) as caught:
                phone.close()
            self.assertIs(caught.exception, primary)
            self.assertIs(primary.process_cleanup_error, cleanup)
            self.assertIn(str(cleanup), "\n".join(primary.__notes__))
            self.assert_duplicate_failure(phone, primary)
            stop.assert_called_once()
        value = h.read_json(phone.out / "closed.json")
        self.assertFalse(value["cleanup_complete"])
        self.assertTrue(value["server_closed"])
        self.assertFalse(value["listening"])
        self.assertIn(str(cleanup), json.dumps(value["cleanup_errors"]))
        self.assertFalse(phone.closed)
        phone.server.job.terminate.assert_called_once()
        phone.server.job.close.assert_called_once()

    def test_phone_stop_error_with_successful_cleanup_remains_primary(self):
        phone = self.phone_model()
        error = ValueError("stop operation failed")
        with patch.object(h, "listening", side_effect=lambda port: phone.server.process.returncode is None), \
             patch.object(h, "command", side_effect=error) as stop:
            with self.assertRaises(ValueError) as caught:
                phone.close()
            self.assertIs(caught.exception, error)
            self.assert_duplicate_failure(phone, error)
            stop.assert_called_once()
        self.assertFalse(phone.closed)
        value = h.read_json(phone.out / "closed.json")
        self.assertEqual(value["cleanup_errors"][0]["step"], "adb_stop")
        self.assertTrue(value["server_closed"])

    def test_phone_successful_stop_does_not_hide_cleanup_failure(self):
        phone = self.phone_model()
        error = OSError("server close failed")
        phone.server.job.close.side_effect = error
        with patch.object(h, "listening", side_effect=lambda port: phone.server.process.returncode is None), \
             patch.object(h, "command", return_value=b"") as stop:
            with self.assertRaises(OSError) as caught:
                phone.close()
            self.assertIs(caught.exception, error)
            self.assert_duplicate_failure(phone, error)
            stop.assert_called_once()
        self.assertFalse(h.read_json(phone.out / "closed.json")["cleanup_complete"])

    def test_phone_receipt_failure_never_repeats_stop_or_cleanup(self):
        phone = self.phone_model()
        error, real_save = OSError("phone receipt unavailable"), h.save
        def save(path, value):
            if path == phone.out / "closed.json":
                raise error
            return real_save(path, value)
        with patch.object(h, "listening", side_effect=lambda port: phone.server.process.returncode is None), \
             patch.object(h, "command", return_value=b"") as stop, patch.object(h, "save", side_effect=save):
            with self.assertRaises(OSError) as caught:
                phone.close()
            self.assertIs(caught.exception, error)
            self.assert_duplicate_failure(phone, error)
            stop.assert_called_once()
        self.assertFalse(phone.closed)
        self.assertFalse((phone.out / "closed.json").exists())
        self.assertIn("close_receipt", "\n".join(error.__notes__))
        phone.server.job.terminate.assert_called_once()
        phone.server.job.close.assert_called_once()

    def test_phone_unknown_port_state_does_not_claim_closure(self):
        phone = self.phone_model()
        error = OSError("port observation unavailable")
        with patch.object(h, "listening", side_effect=[True, error]), patch.object(h, "command", return_value=b""):
            with self.assertRaises(OSError) as caught:
                phone.close()
            self.assertIs(caught.exception, error)
            self.assert_duplicate_failure(phone, error)
        value = h.read_json(phone.out / "closed.json")
        self.assertIsNone(value["listening"])
        self.assertFalse(value["cleanup_complete"])

    def test_phone_live_foreign_port_is_not_killed_or_marked_closed(self):
        phone = self.phone_model()
        phone.server = None
        with patch.object(h, "listening", return_value=True), patch.object(h, "command") as stop:
            with self.assertRaisesRegex(RuntimeError, "ADB port still live") as caught:
                phone.close()
            self.assert_duplicate_failure(phone, caught.exception)
            stop.assert_not_called()
        value = h.read_json(phone.out / "closed.json")
        self.assertTrue(value["listening"])
        self.assertFalse(value["cleanup_complete"])


class PhoneCellTests(unittest.TestCase):
    """Run the complete entry; only physical I/O and the clock are synthetic."""

    def setUp(self):
        parent = h.checked(Path(os.environ.get("P34_HOST_TEST_OUT", ROOT / ".cache/p34-live-tests")))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="cell-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def cell(self, label="run", *, user_delay=0, transfer=100, reboot=170,
             seconds=3390, prepare=0, download=0, terminal_read=0,
             snapshot_read=0, boot=0, readback=0, archive=0,
             health_error=None, collector_exit=None, command_failure=False,
             archive_error=False, close_error=False, missing_metrics=False,
             terminal_error=False, ota_success=True, health_delay=0, withdraw_at=None,
             decode_error=None, real_decode=False, metric_raw=None, logger_stop=0):
        out = h.fresh(self.out / label)
        now, calls = [0.0], []
        start_at = prepare + download + user_delay
        terminal_at, complete_at = start_at + transfer, start_at + transfer + reboot

        def advance(delay):
            now[0] += delay
            if withdraw_at is not None and now[0] >= withdraw_at and not (out / "start-withdrawn.json").exists():
                h.save(out / "start-withdrawn.json", dict(reason="synthetic late notification result",
                    monotonic=now[0], no_ota_cancel=True))

        def event(name, delay=0):
            calls.append((name, now[0]))
            advance(delay)

        phone = Mock(out=out / "phone", deadline=float(seconds))
        phone.exists.return_value = False

        def provision(*args):
            h.raw(phone.out / "runtime.json", b"synthetic runtime\n")
            return 123, "synthetic-capture"

        def downloaded(*args):
            if now[0] < prepare + download:
                return False
            h.raw(phone.out / "downloaded.etu", b"synthetic package\n")
            return True

        def health(*args, terminal_ready=None):
            if not (out / "start-ready.json").exists():
                return dict(upgradeStarts=0, upgradeEnds=0, healthy=True)
            if health_delay and not mcu.transfer_snapshot.called:
                event("health-query", health_delay)
            if terminal_ready and terminal_ready():
                raise h.ObservationReady("synthetic read yielded to terminal")
            return dict(lost=int(health_error == "lost"), error=health_error if health_error != "lost" else None,
                upgradeStarts=int(now[0] >= start_at), upgradeEnds=int(now[0] >= complete_at))

        def finished(*args):
            event("finished", snapshot_read)
            h.raw(phone.out / "snapshot.jsonl", b"synthetic sealed snapshot\n")
            if command_failure:
                h.command(out, "failed-read", [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", "raise SystemExit(7)"],
                          h.environment(out), seconds=10)
            value = dict(success=ota_success, initialDurable=0)
            h.save(phone.out / "statistics.json", value)
            return value

        def archive_capture():
            event("archive", archive)
            if archive_error:
                raise RuntimeError("archive readback mismatch")
            h.raw(phone.out / "archive/snapshot.jsonl", (phone.out / "snapshot.jsonl").read_bytes())

        phone.provision.side_effect = provision
        phone.downloaded.side_effect = downloaded
        phone.health.side_effect = health
        phone.finished.side_effect = finished
        phone.archive_capture.side_effect = archive_capture
        phone.salvage.side_effect = lambda: h.raw(phone.out / "salvage/original.jsonl", b"synthetic partial original\n")
        if close_error:
            phone.close.side_effect = RuntimeError("private ADB close failed")
        mcu = Mock()

        def inspect(role, name):
            event(name, prepare if name == "pre-transfer-current-boot" else readback)
            return dict(storage=dict(journal=dict(expected_begin_durable=0)))

        mcu.inspect.side_effect = inspect
        mcu.wait_boot.side_effect = lambda *args: event("boot", boot)
        sample = bytes(420) if metric_raw is None else metric_raw
        image = h.pinned(h.raw(out / "base-fixture.bin", bytes(0x400) + b"h" * 96))
        names = ("g_ota_link_metrics", "g_ota_metrics_publish_bytes", "__StackGuardStart",
                 "__StackLimit", "system_core_clock", "SystemTickCount")
        observer = m.MCU.__new__(m.MCU)
        observer.bound = {"base": dict(image=image,
            table={name: (0x20000100 + i * 10000, 4) for i, name in enumerate(names)})}
        ram_out = out / "mcu/terminal-before-reboot"

        def read_memory(commands, sizes, label, *, deadline):
            observer.remaining(180, deadline)
            event("terminal-read", terminal_read)
            reads = {row[0]: row[1:] for row in commands if isinstance(row, tuple)}
            self.assertEqual(reads["metrics"], (observer.bound["base"]["table"]["g_ota_link_metrics"][0], 420))
            self.assertEqual(reads["header_before"], (0x08010400, 96))
            self.assertEqual(reads["header_after"], (0x08010400, 96))
            data = dict(header_before=b"h" * 96, header_after=bytes(96) if terminal_error else b"h" * 96,
                metrics=sample, published=struct.pack("<I", 853), guard=b"\x5a" * 32,
                stack=b"\xa5" * 4096 + bytes(4096), clock=struct.pack("<I", 288000000),
                systick=struct.pack("<3I", 7, 287999, 10), vtor=struct.pack("<I", 0x08010800),
                wdt=struct.pack("<2I", 6, 1561), tick0=struct.pack("<I", 123000), tick1=struct.pack("<I", 123100))
            self.assertEqual({key: len(value) for key, value in data.items()}, sizes)
            h.fresh(ram_out)
            for name, raw in data.items():
                h.raw(ram_out / (name + ".bin"), raw)
            observer.remaining(180, deadline)
            return data, "", ram_out

        observer.execute = Mock(side_effect=read_memory)
        mcu.transfer_snapshot.side_effect = observer.transfer_snapshot

        def rtt_bytes():
            if missing_metrics or now[0] < terminal_at:
                return b""
            path = out / "mcu/transfer.rtt"
            if not path.exists():
                h.raw(path, b"P34_METRICS " + sample.hex().encode("ascii") + b"\n")
            return path.read_bytes()

        mcu.start_logger.return_value.read_bytes.side_effect = rtt_bytes
        mcu.stop_logger.side_effect = lambda: event("stop-logger", logger_stop if mcu.stop_logger.call_count == 1 else 0)
        mcu.logger.alive.return_value = True
        network = Mock()
        network.start.return_value = "https://synthetic.example"
        network.tunnel.alive.side_effect = lambda: collector_exit is None or now[0] < collector_exit
        plan = dict(package=dict(sha256="a" * 64), sentinel="synthetic", ble_address="synthetic")
        args = SimpleNamespace(run_role="clean", checkpoint_kib=None, previous_cell=None,
            seconds=seconds, run_id="host-probe", baud=921600, timeout_ms=2000)
        epoch = 7 if metric_raw is None else struct.unpack_from("<I", sample, 15 * 4)[0]
        package_sha = "a" * 64 if metric_raw is None else sample[112:144].hex()
        plan["package"]["sha256"] = package_sha
        decoded = dict(epoch=epoch, total_len=1048576, package_sha256=package_sha, uart_baud_actual=921600, terminal=0)
        original_decoder = live.metrics.from_rtt

        def decode(data):
            event("decode")
            if decode_error is not None:
                raise decode_error
            return original_decoder(data) if real_decode else decoded

        decoder = Mock(side_effect=decode)
        error = None
        with ExitStack() as stack:
            for owner, name, replacement in (
                (live, "MCU", Mock(return_value=mcu)), (live, "Phone", Mock(return_value=phone)),
                (live, "Network", Mock(return_value=network)), (live, "config", Mock(return_value={})),
                (live.time, "monotonic", lambda: now[0]), (live.time, "sleep", advance),
                (live.metrics, "from_rtt", decoder),
                (live.observation_capture, "verify", Mock(return_value=(None, "x kind=begin_ack epoch=%d x" % epoch))),
                (h, "ROOT", out),
            ):
                stack.enter_context(patch.object(owner, name, replacement))
            try:
                with h.device_owner(out):
                    live.phone_cell(plan, out, args)
            except Exception as caught:
                error = caught
        phone.close.assert_called_once()
        network.close.assert_called_once()
        return SimpleNamespace(out=out, error=error, calls=calls, phone=phone, mcu=mcu,
            decoder=decoder, observer=observer, ram_out=ram_out,
            stopped_at=now[0], complete_at=complete_at, terminal_at=terminal_at,
            lock=out / ".cache/p34-live-device.lock")

    def assert_complete(self, case):
        self.assertIsNone(case.error, str(case.error))
        case.phone.finished.assert_called_once()
        case.phone.archive_capture.assert_called_once()
        case.phone.salvage.assert_not_called()
        case.mcu.transfer_snapshot.assert_called_once()
        case.observer.execute.assert_called_once()
        case.decoder.assert_called_once()
        self.assertGreaterEqual(dict(case.calls)["finished"], case.complete_at)
        self.assertGreaterEqual(dict(case.calls)["archive"], dict(case.calls)["finished"])
        self.assertTrue((case.out / "observations.json").is_file())
        self.assertFalse(case.lock.exists())

    def assert_failed(self, case, reason):
        self.assertIsNotNone(case.error)
        self.assertRegex(str(case.error), reason)
        self.assertTrue(case.lock.is_file())
        self.assertFalse((case.out / "observations.json").exists())
        case.phone.salvage.assert_called_once()
        self.assertEqual((case.phone.out / "salvage/original.jsonl").read_bytes(), b"synthetic partial original\n")

    def test_short_complete_control_flow(self):
        self.assert_complete(self.cell())

    def test_real_v11_decoder_runs_after_one_original_ram_snapshot(self):
        raw = metrics_fixture.v11_record()
        case = self.cell(metric_raw=raw, real_decode=True, terminal_read=12)
        self.assert_complete(case)
        self.assertEqual((case.ram_out / "metrics.bin").read_bytes(), raw)
        self.assertEqual([name for name, _ in case.calls if name in ("terminal-read", "decode")],
                         ["terminal-read", "decode"])
        self.assertEqual(dict(case.calls)["decode"], 112)
        self.assertEqual(case.mcu.transfer_snapshot.call_args.kwargs["deadline"], 520)
        print("TERMINAL_ORDER real_v11 read=100 decode=112 deadline=520 samples=1")

    def test_decoder_exception_preserves_real_snapshot_and_original_failure(self):
        error = ValueError("injected semantic rejection")
        case = self.cell(decode_error=error, terminal_read=12)
        self.assert_failed(case, "injected semantic rejection")
        self.assertIs(case.error, error)
        case.mcu.transfer_snapshot.assert_called_once()
        case.observer.execute.assert_called_once()
        case.decoder.assert_called_once()
        self.assertEqual((case.ram_out / "metrics.bin").read_bytes(), bytes(420))
        self.assertTrue((case.ram_out / "stack.bin").is_file())
        self.assertEqual(dict(case.calls)["terminal-read"], 100)
        self.assertEqual(dict(case.calls)["decode"], 112)
        self.assertEqual(h.read_json(case.out / "start-expired.json")["message"], str(error))
        drain = h.read_json(case.out / "start-drain.json")
        self.assertEqual(drain["terminal"], dict(attempted=True, captured=True))
        case.phone.finished.assert_not_called()
        case.phone.archive_capture.assert_not_called()
        print("TERMINAL_ORDER rejected read=100 decode=112 samples=1 original_error_preserved=true")

    def test_crc_rejection_keeps_original_rtt_and_ram_without_a_second_sample(self):
        raw = metrics_fixture.v11_record()
        damaged = raw[:-1] + bytes([raw[-1] ^ 1])
        case = self.cell(metric_raw=damaged, real_decode=True)
        self.assert_failed(case, "CRC/torn read")
        case.mcu.transfer_snapshot.assert_called_once()
        case.decoder.assert_called_once()
        self.assertEqual((case.ram_out / "metrics.bin").read_bytes(), damaged)
        self.assertEqual((case.out / "mcu/transfer.rtt").read_bytes(), b"P34_METRICS " + damaged.hex().encode() + b"\n")

    def test_failure_drain_decoder_error_cannot_restart_or_extend_terminal_capture(self):
        case = self.cell(user_delay=121, transfer=71, terminal_read=12,
                         decode_error=ValueError("drain semantic rejection"))
        self.assert_failed(case, "start phase deadline")
        case.mcu.transfer_snapshot.assert_called_once()
        case.decoder.assert_called_once()
        self.assertFalse((case.out / "phase-terminal.json").exists())
        self.assertEqual(case.mcu.transfer_snapshot.call_args.kwargs["deadline"], 420)
        drain = h.read_json(case.out / "start-drain.json")
        self.assertEqual(drain["deadline_monotonic"], 420)
        self.assertEqual(drain["terminal_error"], "drain semantic rejection")
        self.assertEqual(drain["terminal"], dict(attempted=True, captured=True))
        self.assertEqual((case.ram_out / "metrics.bin").read_bytes(), bytes(420))
        print("TERMINAL_DRAIN read=192 decode=204 deadline=420 samples=1 result=original_start_failure")

    def test_discovery_timestamp_precedes_blocking_logger_stop_and_ram_read(self):
        case = self.cell(user_delay=110, transfer=0, logger_stop=15, terminal_read=20)
        self.assert_complete(case)
        observed = h.read_json(case.out / "start-observed.json")
        self.assertEqual(observed["source"], "MCU terminal publication")
        self.assertEqual(observed["monotonic"], 110)
        self.assertTrue(observed["within_start_window"])
        self.assertEqual(dict(case.calls)["terminal-read"], 125)
        self.assertEqual(dict(case.calls)["decode"], 145)

    def test_expiry_during_logger_close_never_starts_or_retries_ram_read(self):
        for label, options in (("normal", dict(logger_stop=420)),
                               ("drain", dict(user_delay=121, transfer=298, logger_stop=1))):
            with self.subTest(label=label):
                case = self.cell(label, **options)
                self.assertIsNotNone(case.error)
                case.mcu.transfer_snapshot.assert_not_called()
                case.observer.execute.assert_not_called()
                case.decoder.assert_not_called()
                self.assertTrue(case.lock.is_file())
                self.assertFalse((case.out / "observations.json").exists())
                self.assertEqual(h.read_json(case.out / "start-drain.json")["terminal"],
                                 dict(attempted=True, captured=False))
                if label == "drain":
                    self.assertEqual(case.stopped_at, 420)
                    self.assertFalse((case.out / "phase-terminal.json").exists())

    def test_short_frame_fails_before_any_ram_read_and_is_not_retried(self):
        case = self.cell(metric_raw=bytes(419))
        self.assert_failed(case, "truncated/invalid MCU metrics record")
        case.mcu.transfer_snapshot.assert_not_called()
        case.decoder.assert_not_called()
        self.assertTrue((case.out / "mcu/transfer.rtt").is_file())

    def test_click_transfer_and_full_identity_window_do_not_share_300_seconds(self):
        case = self.cell(user_delay=25, transfer=110, reboot=170)
        self.assert_complete(case)
        self.assertEqual(case.stopped_at, 305)
        for phase, began in (("start", 0), ("transfer", 25), ("terminal", 135), ("snapshot", 305)):
            self.assertEqual(h.read_json(case.out / ("phase-" + phase + ".json"))["started_monotonic"], began)

    def test_slow_run_is_archived_without_claiming_a_throughput_pass(self):
        for seconds in (3390, 18000):
            with self.subTest(seconds=seconds):
                case = self.cell(str(seconds), transfer=140, seconds=seconds)
                self.assert_complete(case)
                self.assertEqual(case.stopped_at, 310)
                self.assertFalse(h.read_json(case.out / "observations.json")["independent_acceptance"])

    def test_full_readback_and_archive_keep_their_own_allowances(self):
        case = self.cell(user_delay=110, transfer=140, terminal_read=179,
                         snapshot_read=250, boot=290, readback=290, archive=250)
        self.assert_complete(case)
        self.assertGreater(case.stopped_at, 900)

    def test_preparation_exhaustion_never_invites_start(self):
        for name, kwargs in (("short-life", dict(seconds=900)), ("spent-life", dict(seconds=3100, prepare=500)),
                             ("prepare-timeout", dict(prepare=601))):
            with self.subTest(name=name):
                case = self.cell(name, **kwargs)
                self.assert_failed(case, "budget|deadline")
                self.assertFalse((case.out / "start-ready.json").exists())
                case.phone.finished.assert_not_called()
                case.phone.archive_capture.assert_not_called()

    def test_actual_phase_timeouts_fail_and_keep_originals_and_lock(self):
        for name, kwargs in (("download", dict(download=301)), ("start", dict(user_delay=121)),
                             ("transfer", dict(transfer=301)), ("terminal", dict(reboot=421)),
                             ("snapshot", dict(snapshot_read=301)), ("boot", dict(boot=346)),
                             ("readback", dict(readback=346)), ("archive", dict(archive=301))):
            with self.subTest(phase=name):
                case = self.cell(name, **kwargs)
                self.assert_failed(case, "deadline")

    def test_health_loss_and_error_cannot_become_complete(self):
        for error in ("lost", "io-health"):
            with self.subTest(error=error):
                case = self.cell(error, health_error=error)
                self.assert_failed(case, "observation failed")
                case.phone.finished.assert_not_called()

    def test_collector_death_at_terminal_is_not_hidden_by_completion(self):
        case = self.cell(collector_exit=270)
        self.assert_failed(case, "collector/service exited")
        case.phone.finished.assert_not_called()

    def test_nonzero_command_in_full_entry_preserves_exit_and_original_snapshot(self):
        case = self.cell(command_failure=True)
        self.assert_failed(case, "standard tool failed")
        self.assertEqual(h.read_json(case.out / "failed-read.closed.json")["exit_code"], 7)
        self.assertEqual((case.phone.out / "snapshot.jsonl").read_bytes(), b"synthetic sealed snapshot\n")
        case.phone.archive_capture.assert_not_called()

    def test_archive_error_cannot_emit_observations(self):
        self.assert_failed(self.cell(archive_error=True), "archive readback mismatch")

    def test_full_180_second_app_window_is_available(self):
        self.assert_complete(self.cell(user_delay=110, transfer=140, reboot=180))

    def test_missing_metrics_or_missed_preboot_capture_cannot_be_complete(self):
        for label, kwargs, reason in (("missing", dict(missing_metrics=True), "deadline"),
                                      ("missed", dict(terminal_error=True), "stack/clock window missed")):
            with self.subTest(label=label):
                case = self.cell(label, **kwargs)
                self.assert_failed(case, reason)
                case.phone.archive_capture.assert_not_called()

    def test_app_failure_stays_failure_even_with_complete_health_counts(self):
        case = self.cell(ota_success=False)
        self.assert_failed(case, "observed OTA failure")
        case.phone.archive_capture.assert_not_called()
        self.assertTrue((case.phone.out / "snapshot.jsonl").is_file())

    def test_close_error_is_propagated_and_retains_lock(self):
        case = self.cell(close_error=True)
        self.assertIsNotNone(case.error)
        self.assertIn("private ADB close failed", str(case.error))
        self.assertTrue(case.lock.exists())

    def test_late_start_is_drained_without_restarting_terminal_budget(self):
        case = self.cell(user_delay=121, transfer=71, reboot=170)
        self.assert_failed(case, "deadline")
        self.assertEqual(dict(case.calls)["terminal-read"], 192)
        self.assertTrue(h.read_json(case.out / "start-drain.json")["complete_observed"])
        self.assertTrue(h.read_json(case.out / "start-drain.json")["terminal"]["captured"])
        self.assertEqual(case.mcu.transfer_snapshot.call_args.kwargs["deadline"], 420)
        self.assertFalse((case.out / "phase-terminal.json").exists())
        self.assertTrue((case.out / "start-expired.json").is_file())
        case.phone.archive_capture.assert_not_called()
        case.mcu.wait_boot.assert_not_called()
        case.mcu.start_logger.assert_called_once()

    def test_start_in_last_drain_second_does_not_extend_or_cancel(self):
        case = self.cell(user_delay=419, transfer=71)
        self.assertIsNotNone(case.error)
        self.assertEqual(case.stopped_at, 420)
        drain = h.read_json(case.out / "start-drain.json")
        self.assertEqual(drain["last_health"]["upgradeStarts"], 1)
        self.assertEqual(drain["last_health"]["upgradeEnds"], 0)
        self.assertFalse(drain["complete_observed"])
        self.assertTrue(drain["pending_phone_retrieval"])
        case.phone.salvage.assert_not_called()
        case.phone.archive_capture.assert_not_called()
        case.phone.finished.assert_not_called()
        case.mcu.transfer_snapshot.assert_not_called()
        self.assertTrue(case.lock.exists())
        self.assertFalse((case.out / "observations.json").exists())

    def test_no_start_does_not_close_early_or_bulk_read_over_terminal_watch(self):
        case = self.cell(user_delay=10000)
        self.assertEqual(case.stopped_at, 420)
        case.phone.salvage.assert_not_called()
        self.assertFalse(h.read_json(case.out / "start-drain.json")["complete_observed"])
        self.assertTrue(case.lock.exists())

    def test_start_at_exact_boundary_is_not_admitted(self):
        case = self.cell(user_delay=120, transfer=71, reboot=170)
        self.assert_failed(case, "deadline")
        observed = h.read_json(case.out / "start-observed.json")
        self.assertFalse(observed["within_start_window"])
        self.assertEqual(h.read_json(case.out / "phase-salvage.json")["deadline_monotonic"], 420)

    def test_terminal_during_health_read_has_priority_in_normal_and_late_paths(self):
        for delay in (0, 121):
            with self.subTest(delay=delay):
                case = self.cell(str(delay), user_delay=delay, transfer=70, health_delay=10)
                case.mcu.transfer_snapshot.assert_called_once()
                self.assertLessEqual(dict(case.calls)["terminal-read"], case.terminal_at + 10)
                if delay:
                    self.assert_failed(case, "deadline")
                else:
                    self.assert_complete(case)

    def test_late_terminal_failure_is_not_retried_or_made_successful(self):
        case = self.cell(user_delay=121, transfer=71, terminal_error=True)
        self.assert_failed(case, "deadline")
        case.mcu.transfer_snapshot.assert_called_once()
        drain = h.read_json(case.out / "start-drain.json")
        self.assertIn("window missed", drain["terminal_error"])
        self.assertFalse(drain["terminal"]["captured"])
        self.assertTrue(drain["original_error_preserved"])

    def test_withdrawal_after_start_or_terminal_keeps_observing_until_end(self):
        for when in (.5, 110):
            with self.subTest(when=when):
                case = self.cell(str(when), withdraw_at=when)
                self.assert_failed(case, "withdrawn")
                case.mcu.transfer_snapshot.assert_called_once()
                self.assertEqual(dict(case.calls)["terminal-read"], 100)
                self.assertEqual(case.stopped_at, 270)
                drain = h.read_json(case.out / "start-drain.json")
                self.assertEqual(drain["deadline_monotonic"], when + 300)
                self.assertTrue(drain["complete_observed"])
                self.assertTrue(drain["terminal"]["captured"])
                case.phone.archive_capture.assert_not_called()


class StartNoticeTests(unittest.TestCase):
    def setUp(self):
        parent = h.checked(Path(os.environ.get("P34_HOST_TEST_OUT", ROOT / ".cache/p34-live-tests")))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="notice-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.now, self.sent = [0.0], []
        self.clock = patch.object(live.time, "monotonic", lambda: self.now[0])
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def notices(self, name="run", *, mutate=None, send=None, phase=None):
        out = h.fresh(self.out / name)
        h.raw(out / "phase-start.json", json.dumps(phase or
            dict(phase="start", started_monotonic=0, deadline_monotonic=120)).encode())
        runtime = h.raw(out / "phone/runtime.json", b"synthetic-runtime")
        package = h.raw(out / "phone/downloaded.etu", b"synthetic-package")
        state = dict(pid=123, capture="synthetic", run_id="case", upgradeStarts=0, upgradeEnds=0)
        ready = dict(pid=123, capture="synthetic", run_id="case", start_state=state,
            phase=h.record(out / "phase-start.json"), runtime=runtime, package=package,
            expires_at="2026-10-12T13:02:00+00:00")
        if mutate:
            mutate(ready)
        h.save(out / "start-ready.json", ready)
        def delivered(kind, body, seconds):
            self.sent.append((kind, body, seconds))
            return True
        return live.StartNotices(out, package, send or delivered)

    def test_fixed_deadline_explicit_message_and_once_only_withdrawal(self):
        notice = self.notices()
        notice.poll(owner_alive=True)
        self.assertIn("2026-10-12T13:02:00+00:00", self.sent[0][1])
        self.assertIn("120", self.sent[0][1])
        original = (notice.out / "start-ready.json").read_bytes()
        self.now[0] = 119
        notice.poll(owner_alive=True)
        self.assertEqual(len(self.sent), 1)
        self.now[0] = 120
        for _ in range(3):
            notice.poll(owner_alive=True)
        self.assertEqual([x[0] for x in self.sent], ["start", "expired"])
        self.assertEqual((notice.out / "start-ready.json").read_bytes(), original)
        self.assertIn("\u5df2\u7ecf\u5f00\u59cb", self.sent[-1][1])
        self.assertIn("\u4e0d\u8981\u53d6\u6d88", self.sent[-1][1])

    def test_expired_started_and_dead_owner_override_stale_ready(self):
        for state in ("start-observed.json", "start-expired.json", "failed.json", "dead"):
            with self.subTest(state=state):
                self.sent.clear()
                notice = self.notices(state)
                if state != "dead":
                    h.save(notice.out / state, dict(actual_state=state))
                notice.poll(owner_alive=state != "dead")
                self.assertNotIn("start", [x[0] for x in self.sent])
        notice = self.notices("started-and-failed")
        h.save(notice.out / "start-observed.json", {})
        h.save(notice.out / "failed.json", {})
        notice.poll(owner_alive=True)
        self.assertEqual(self.sent[-1][0], "expired")

    def test_expiry_during_delivery_revokes_without_repeating_start(self):
        def delayed(kind, body, seconds):
            self.sent.append((kind, body, seconds))
            if kind == "start":
                self.now[0] = 120
            return True
        notice = self.notices(send=delayed)
        notice.poll(owner_alive=True)
        notice.poll(owner_alive=True)
        self.assertEqual([x[0] for x in self.sent], ["start", "expired"])
        self.assertTrue((notice.out / "start-withdrawn.json").is_file())

    def test_unknown_send_is_not_retried_or_treated_as_delivery(self):
        def unknown(kind, body, seconds):
            self.sent.append((kind, body, seconds))
            if kind == "start":
                raise RuntimeError("unknown send result")
            return True
        notice = self.notices(send=unknown)
        for _ in range(3):
            notice.poll(owner_alive=True)
        self.assertIsNotNone(notice.error)
        self.assertEqual([x[0] for x in self.sent], ["start", "expired"])
        self.assertFalse((notice.out / "notice-start.sent.json").exists())
        self.assertTrue((notice.out / "notice-start.failed.json").is_file())

    def test_missing_or_mismatched_state_never_sends_start(self):
        mutations = [
            lambda r: r.pop("start_state"),
            lambda r: r["start_state"].update(capture="foreign"),
            lambda r: r["start_state"].update(upgradeStarts=False),
            lambda r: r.update(pid=True),
            lambda r: r["package"].update(sha256="0" * 64),
            lambda r: r.update(expires_at="2026-10-12T13:02:00"),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                self.sent.clear()
                notice = self.notices(str(i), mutate=mutate)
                notice.poll(owner_alive=True)
                self.assertIsNotNone(notice.error)
                self.assertEqual([x[0] for x in self.sent], ["expired"])

    def test_deadline_boolean_nan_and_cross_cell_phase_fail_closed(self):
        for i, deadline in enumerate((True, float("nan"), float("inf"), 0, 121)):
            with self.subTest(deadline=deadline):
                self.sent.clear()
                notice = self.notices(str(i), phase=dict(phase="start", started_monotonic=0,
                    deadline_monotonic=deadline))
                notice.poll(owner_alive=True)
                self.assertEqual([x[0] for x in self.sent], ["expired"])
        self.sent.clear()
        other = self.notices("other")
        notice = self.notices("foreign", mutate=lambda r: r.update(phase=h.record(other.out / "phase-start.json")))
        notice.poll(owner_alive=True)
        self.assertEqual([x[0] for x in self.sent], ["expired"])

    def test_restart_does_not_replay_an_unknown_notification_intent(self):
        notice = self.notices()
        h.save(notice.out / "notice-start.intent.json", dict(outcome="unknown"))
        notice.poll(owner_alive=True)
        self.assertIsNotNone(notice.error)
        self.assertEqual([x[0] for x in self.sent], ["expired"])

    def test_unknown_expiry_receipt_survives_notifier_restart_without_resend(self):
        notice = self.notices()
        h.save(notice.out / "start-expired.json", {})
        h.save(notice.out / "notice-expired.intent.json", dict(outcome="unknown"))
        notice.poll(owner_alive=True)
        self.assertIsNotNone(notice.error)
        self.assertEqual(self.sent, [])

    def test_deadline_is_rechecked_immediately_before_send(self):
        notice = self.notices()
        real_save = h.save
        def saving(path, value):
            result = real_save(path, value)
            if path.name == "notice-start.intent.json":
                self.now[0] = 120
            return result
        with patch.object(h, "save", side_effect=saving):
            notice.poll(owner_alive=True)
        self.assertEqual([x[0] for x in self.sent], ["expired"])

    def test_phase_budget_cannot_refresh_a_previously_entered_phase(self):
        out = h.fresh(self.out / "budgets")
        budget = live.PhoneBudget(SimpleNamespace(deadline=3390), out)
        budget.enter("start")
        original = (out / "phase-start.json").read_bytes()
        self.now[0] = 30
        with self.assertRaisesRegex(RuntimeError, "cannot be restarted"):
            budget.enter("start")
        self.assertEqual((out / "phase-start.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
