"""No-hardware tests using actual image maps and simulated reset epochs."""
import copy
import argparse
import importlib.util
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("baud_mcu_tested", Path(__file__).with_name("baud_mcu.py"))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def profile_bytes(**changes):
    header = dict.fromkeys(m.HEADERS, 0)
    header.update(magic=0x50334250, schema=1, size=288, ready=1, run=1, clock_hz=288000000,
        clock_ok=1, uart_baud_actual=921600, retained_baud=921600, total_len=290619,
        rx_session_bytes=300000, pump_entries=30)
    header.update(changes)
    phases = [1, 0, 64, 400, 0, 400] * 8
    return struct.pack("<72I", *[header[key] for key in m.HEADERS], *phases)


class ProfileTests(unittest.TestCase):
    def test_integer_uart_divider_is_reported_not_normalized_away(self):
        value = m.decode_profile(profile_bytes(uart_baud_actual=923076), 921600, 290619)
        self.assertEqual(value["uart_baud_actual"], 923076)
        self.assertGreater(value["uart_divider_error_ppm"], 0)

    def test_retained_word_and_actual_baud_bounds(self):
        self.assertEqual(m.baud_word(115200), 0x5034FA05)
        self.assertEqual(m.baud_word(921600), 0x5034F708)
        self.assertFalse(m.actual_baud_matches(921600, 115200))
        self.assertFalse(m.actual_baud_matches(921600, 1000000))
        self.assertFalse(m.actual_baud_matches(True, 115200))
    def test_success(self):
        value = m.decode_profile(profile_bytes(), 921600, 290619)
        self.assertTrue(value["clean_counters"])
        self.assertEqual(value["phases"]["ack_write_call"]["cycles"], 400)

    def test_wrong_baud_or_package(self):
        for field, value in (("uart_baud_actual", 115200), ("retained_baud", 460800), ("total_len", 290618)):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                m.decode_profile(profile_bytes(**{field: value}), 921600, 290619)

    def test_unfrozen_or_wrong_schema(self):
        for field, value in (("ready", 0), ("active", 1), ("terminal", 1), ("schema", 2), ("magic", 0), ("run", 0)):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                m.decode_profile(profile_bytes(**{field: value}), 921600, 290619)

    def test_bad_clock(self):
        for field, value in (("clock_ok", 0), ("clock_hz", 0), ("clock_hz", 144000000)):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                m.decode_profile(profile_bytes(**{field: value}), 921600, 290619)

    def test_zero_timing_rejected(self):
        data = bytearray(profile_bytes())
        data[96:] = bytes(192)
        with self.assertRaises(RuntimeError):
            m.decode_profile(data, 921600, 290619)

    def test_counters_are_not_discarded(self):
        value = m.decode_profile(profile_bytes(hw_buffer_dropped=1, uart_error_events=2), 921600, 290619)
        self.assertFalse(value["clean_counters"])
        self.assertEqual(value["hw_buffer_dropped"], 1)

    def test_short_or_extra_payload(self):
        for data in (profile_bytes()[:-1], profile_bytes() + bytes(4)):
            with self.assertRaises(RuntimeError):
                m.decode_profile(data, 921600, 290619)

    def test_inconsistent_phase(self):
        data = bytearray(profile_bytes())
        struct.pack_into("<I", data, 100, 2)
        with self.assertRaises(RuntimeError):
            m.decode_profile(data, 921600, 290619)


class StateTests(unittest.TestCase):
    def test_real_constructor_is_pending_not_failed(self):
        value = m.CaptureState(30208, 30209).snapshot()
        self.assertIsNone(value["epoch"])
        self.assertFalse(value["ready_to_begin"])

    def test_complete_confirmation_and_new_epoch_required(self):
        state = m.CaptureState(30208, 30209)
        state.observe(dict(sample=dict(epoch=0), lines=["OTA: BCB already CONFIRMED vcode=30208\n"]))
        self.assertTrue(state.can_begin())
        state.reserve()
        self.assertFalse(state.can_begin())
        state.observe(None)
        self.assertFalse(state.can_finish())
        state.observe(dict(sample=dict(epoch=1), lines=["OTA: TEST_BOOT confirmed vcode=30209\n"]))
        self.assertTrue(state.can_finish())

    def test_incomplete_and_wrong_version_not_accepted(self):
        state = m.CaptureState(30208, 30209)
        for line in ("OTA: BCB already CONFIRMED vcode=30208", "OTA: BCB already CONFIRMED vcode=30207\n"):
            state.observe(dict(sample=dict(epoch=0), lines=[line]))
            self.assertFalse(state.can_begin())

    def test_conflicting_epoch_fails(self):
        state = m.CaptureState(30208, 30209)
        with self.assertRaises(RuntimeError):
            state.observe(dict(sample=dict(epoch=0), lines=["OTA: BCB already CONFIRMED vcode=30208\n",
                                                           "OTA: TEST_BOOT confirmed vcode=30209\n"]))


class Clock:
    now = 0.0
    def __call__(self):
        return self.now


class FakeLink:
    def __init__(self, profile):
        self.profile = profile
        self.ram_reads, self.ram_writes, self.addresses = [], [], []
        self.rtt_address = None
        self.boot = False
        self.halted = False
        self.tick = 1000

    def running(self):
        if self.halted:
            raise RuntimeError("MCU halted")
        if self.boot:
            raise m.passive.Transition("Boot")

    def read(self, address, size):
        self.addresses.append(address)
        if address == m.c.APP:
            return bytes.fromhex(self.profile["prefix"])
        values = {self.profile["symbols"]["tick"]: self.tick,
                  self.profile["symbols"]["core_clock"]: 288000000,
                  self.profile["symbols"]["systick_reload"]: 287999}
        return struct.pack("<I", values[address])


class FakeChannel:
    def __init__(self, link, index, profile):
        self.partial = bytearray(b"unfinished")
        self.raw = io.BytesIO()
        self.lines = []
        self.profile = profile

    def pump(self):
        self.lines.append("OTA: BCB already CONFIRMED vcode=%d\n" % self.profile["identity"]["version_code"])


class EpochTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = m.load_bindings()["profiles"]

    def make_reader(self, code="30207"):
        link, clock = FakeLink(self.profiles[code]), Clock()
        reader = m.ImageReader(link, self.profiles, gate=m.epoch.AppEpochGate(clock=clock), channel_factory=FakeChannel)
        return reader, link, clock

    def ready(self, reader, link, clock):
        self.assertIsNone(reader.poll())
        clock.now += .1
        link.tick += 100
        return reader.poll()

    def test_maps_match_actual_images(self):
        for code, value in self.profiles.items():
            self.assertEqual(m.bind_map(Path(value["map"]["path"]).read_text(encoding="utf-8"),
                Path(value["image"]["path"]).read_bytes(), code != "30207"), value["symbols"])

    def test_old_to_new_uses_new_tick_and_clears_partial(self):
        reader, link, clock = self.make_reader()
        first = self.ready(reader, link, clock)
        old_channel = reader.channel
        link.profile = self.profiles["30208"]
        second = self.ready(reader, link, clock)
        self.assertTrue(old_channel.raw.closed)
        self.assertEqual(reader.discarded_partial_bytes, len(b"unfinished"))
        self.assertGreater(second["sample"]["epoch"], first["sample"]["epoch"])
        self.assertEqual(second["version"], 30208)
        self.assertIn(self.profiles["30208"]["symbols"]["tick"], link.addresses)

    def test_boot_closes_reader_before_ram_read(self):
        reader, link, clock = self.make_reader()
        self.ready(reader, link, clock)
        old = reader.channel
        link.addresses.clear()
        link.boot = True
        self.assertIsNone(reader.poll())
        self.assertTrue(old.raw.closed)
        self.assertEqual(link.addresses, [])
        self.assertEqual(link.ram_writes, [])

    def test_unknown_header_fails_closed(self):
        reader, link, clock = self.make_reader()
        self.ready(reader, link, clock)
        link.profile = copy.deepcopy(link.profile)
        link.profile["prefix"] = "ff" * 0x460
        with self.assertRaises(RuntimeError):
            reader.poll()
        self.assertIsNone(reader.channel)

    def final_header_read(self, link, action, content=None):
        original, calls = link.read, 0

        def read(address, size):
            nonlocal calls
            if address == m.c.APP:
                calls += 1
                if calls == 2:
                    action()
                    if content is not None:
                        link.addresses.append(address)
                        return content
            return original(address, size)

        return mock.patch.object(link, "read", side_effect=read)

    def assert_invalidated(self, reader, old_channel):
        self.assertIsNone(reader.channel)
        self.assertTrue(old_channel.raw.closed)
        self.assertFalse(reader.gate.ready)
        self.assertIsNone(reader.channel_epoch)
        self.assertIsNone(reader.link.rtt_address)
        self.assertEqual(reader.link.ram_writes, [])
        self.assertEqual(reader.discarded_partial_bytes, len(b"unfinished"))

    def test_boot_during_final_header_read_discards_unknown_prefix(self):
        reader, link, clock = self.make_reader()
        self.ready(reader, link, clock)
        old = reader.channel
        with self.final_header_read(link, lambda: setattr(link, "boot", True), bytes(0x460)):
            self.assertIsNone(reader.poll())
        self.assert_invalidated(reader, old)

    def test_boot_during_final_header_read_discards_even_matching_prefix(self):
        reader, link, clock = self.make_reader()
        self.ready(reader, link, clock)
        old = reader.channel
        with self.final_header_read(link, lambda: setattr(link, "boot", True)):
            self.assertIsNone(reader.poll())
        self.assert_invalidated(reader, old)

    def test_mapped_transition_during_sample_requires_new_epoch_confirmation(self):
        reader, link, clock = self.make_reader()
        state = m.CaptureState(30207, 30208)
        first = self.ready(reader, link, clock)
        state.observe(first)
        state.reserve()
        old = reader.channel
        with self.final_header_read(link, lambda: setattr(link, "profile", self.profiles["30208"])):
            observation = reader.poll()
        self.assertIsNone(observation)
        self.assert_invalidated(reader, old)
        state.observe(observation)
        self.assertFalse(state.can_finish())
        self.assertEqual(reader.channel_count, 1)
        current = self.ready(reader, link, clock)
        state.observe(current)
        self.assertGreater(current["sample"]["epoch"], first["sample"]["epoch"])
        self.assertEqual(current["version"], 30208)
        self.assertEqual(reader.channel_count, 2)
        self.assertTrue(state.can_finish())

    def test_unknown_final_header_without_transition_still_fails(self):
        reader, link, clock = self.make_reader()
        self.ready(reader, link, clock)
        old = reader.channel
        with self.final_header_read(link, lambda: None, bytes(0x460)):
            with self.assertRaisesRegex(RuntimeError, "App changed during RTT sample"):
                reader.poll()
        self.assert_invalidated(reader, old)

    def test_ambiguous_final_header_is_not_a_proven_transition(self):
        reader, link, clock = self.make_reader()
        reader.profiles = dict(self.profiles, duplicate=copy.deepcopy(self.profiles["30208"]))
        self.ready(reader, link, clock)
        old = reader.channel
        with self.final_header_read(link, lambda: setattr(link, "profile", self.profiles["30208"])):
            with self.assertRaisesRegex(RuntimeError, "App changed during RTT sample"):
                reader.poll()
        self.assert_invalidated(reader, old)

    def test_halt_during_final_header_read_is_not_a_transition(self):
        reader, link, clock = self.make_reader()
        self.ready(reader, link, clock)
        old = reader.channel
        with self.final_header_read(link, lambda: setattr(link, "halted", True)):
            with self.assertRaisesRegex(RuntimeError, "MCU halted"):
                reader.poll()
        self.assert_invalidated(reader, old)

    def test_final_header_io_error_stays_fatal(self):
        reader, link, clock = self.make_reader()
        self.ready(reader, link, clock)
        old = reader.channel

        def failure():
            raise OSError("device read failed")

        with self.final_header_read(link, failure):
            with self.assertRaisesRegex(OSError, "device read failed"):
                reader.poll()
        self.assert_invalidated(reader, old)

    def test_unchanged_final_header_keeps_current_channel(self):
        reader, link, clock = self.make_reader()
        first = self.ready(reader, link, clock)
        old = reader.channel
        clock.now += .1
        link.tick += 100
        current = reader.poll()
        self.assertEqual(current["sample"]["epoch"], first["sample"]["epoch"])
        self.assertIs(reader.channel, old)
        self.assertFalse(old.raw.closed)
        self.assertEqual(reader.discarded_partial_bytes, 0)

    def test_ambiguous_map_and_wrong_systick_rejected(self):
        value = self.profiles["30208"]
        text = Path(value["map"]["path"]).read_text(encoding="utf-8")
        data = bytearray(Path(value["image"]["path"]).read_bytes())
        with self.assertRaises(RuntimeError):
            m.map_symbol(text + "\n0x2005487c _SEGGER_RTT\n", "_SEGGER_RTT")
        data[value["symbols"]["handler"] - m.c.APP] ^= 1
        with self.assertRaises(RuntimeError):
            m.bind_map(text, data, True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    m.b.require(Path.cwd().resolve() == m.b.ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit project execution required")
    out = m.b.checked(m.b.OUT / ("host-tests-mcu-%03d" % args.generation))
    m.b.require(not out.exists(), "preserve previous tests")
    m.b.checked(out / "result.json")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    m.b.io.write_json(m.b.ROOT, out / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), source=m.b.record(Path(__file__)),
        tested_source=m.b.record(Path(m.__file__)), hardware=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
