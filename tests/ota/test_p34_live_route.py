"""Finite live-adapter host tests. Synthetic device bytes are never hardware PASS."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "Tools/ota/p34-acceptance"), str(ROOT / "tests/ota")]
import live
import live_host as h
import live_mcu as m
import live_phone as p
import test_p34_acceptance_stats as stats_fixture
import test_p34_service_patch as service_fixture


class LiveRouteTests(unittest.TestCase):
    def setUp(self):
        parent = h.checked(ROOT / ".cache/p34-live-tests")
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

    def test_standard_process_binary_streams_exit_and_timeout_are_preserved(self):
        env = h.environment(self.out)
        result = h.command(self.out, "binary", [sys.executable, "-I", "-S", "-B", "-c",
            "import sys;sys.stdout.buffer.write(b'\\x00\\xff');sys.stderr.write('diagnostic')"], env, seconds=10)
        self.assertEqual(result, b"\x00\xff")
        payload = b"runtime\x00\xff\n"
        copied = h.command(self.out, "stdin", [sys.executable, "-I", "-S", "-B", "-c",
            "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"], env, seconds=10, stdin=payload)
        self.assertEqual(copied, payload)
        self.assertEqual((self.out / "binary.stderr").read_bytes(), b"diagnostic")
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            h.command(self.out, "binary", [sys.executable], env, seconds=1)
        with self.assertRaisesRegex(RuntimeError, "standard tool failed"):
            h.command(self.out, "nonzero", [sys.executable, "-I", "-S", "-B", "-c", "raise SystemExit(7)"], env, seconds=10)
        self.assertEqual(h.read_json(self.out / "nonzero.closed.json")["exit_code"], 7)
        with self.assertRaisesRegex(RuntimeError, "timeout"):
            h.command(self.out, "timeout", [sys.executable, "-I", "-S", "-B", "-c", "import time;time.sleep(30)"], env, seconds=.2)
        receipt = h.read_json(self.out / "timeout.closed.json")
        self.assertEqual(receipt["reason"], "timeout_outcome_unknown")
        self.assertTrue(receipt["stopped_while_running"])

    def test_isolated_real_cli_imports_without_cwd_on_sys_path(self):
        text = h.command(self.out, "help", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
            ROOT / "Tools/ota/p34-acceptance/live.py", "--help"], h.environment(self.out), seconds=15)
        self.assertIn(b"--previous-cell", text)
        self.assertIn(b"--contract", text)

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
        with patch.object(phone, "health", return_value=dict(upgradeStarts=0)), patch.object(phone, "exists", return_value=True), \
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
        with patch.object(phone, "health", return_value=dict(upgradeStarts=1, upgradeEnds=1)), \
             patch.object(phone, "cmd", return_value=b"events.jsonl\nsnapshot-1.jsonl\n"), \
             patch.object(phone, "file", return_value=raw):
            value = phone.finished(phone.pid, phone.capture, cfg)
            self.assertTrue(value["success"])
        self.assertEqual((phone.out / "snapshot.jsonl").read_bytes(), raw)
        self.assertEqual(value["initialDurable"], 0)

    def test_wrong_runtime_stamp_keeps_snapshot_and_cannot_be_archived(self):
        phone = self.phone()
        raw, cfg = self.snapshot(phone, wrong_stamp=True)
        with patch.object(phone, "health", return_value=dict(upgradeStarts=1, upgradeEnds=1)), \
             patch.object(phone, "cmd", return_value=b"snapshot-1.jsonl\n"), patch.object(phone, "file", return_value=raw):
            with self.assertRaisesRegex(RuntimeError, "runtime config"):
                phone.finished(phone.pid, phone.capture, cfg)
        self.assertEqual((phone.out / "snapshot.jsonl").read_bytes(), raw)
        with self.assertRaisesRegex(RuntimeError, "unverified capture"):
            phone.archive_capture()

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
