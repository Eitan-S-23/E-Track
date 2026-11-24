from dataclasses import replace
import hashlib
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
from recovery_entry.loader import BOOT_SHA, EntryContext, LoadSession, stage_elf


class Memory:
    def __init__(self, context):
        self.current = context
        self.ram = {}
        self.writes = 0
        self.short = self.corrupt = self.change = self.cross = False

    def context(self):
        return self.current

    def write(self, address, data):
        assert 0x20060000 <= address < address+len(data) <= 0x20062000
        self.writes += 1
        for i, byte in enumerate(data): self.ram[address+i] = byte
        if self.corrupt: self.ram[address] ^= 1
        if self.cross and self.writes == 4: self.ram[0x20060000] ^= 1
        if self.change: self.current = replace(self.current, epoch="changed")
        return len(data)-1 if self.short else len(data)

    def read(self, address, length):
        return bytes(self.ram.get(address+i, 0) for i in range(length))


class Loader(unittest.TestCase):
    def setUp(self):
        self.elf = (ROOT / ".cache/p34-entry-bcb4/entry.elf").read_bytes()
        self.digest = hashlib.sha256(self.elf).hexdigest()
        self.context = EntryContext("test-epoch", "test-board", "test-probe", BOOT_SHA,
            0x0800199c, 0, 0, 1, 0x20057f00, 0, 0x08000000, 0x01000000,
            True, True, True, True)
        self.io = Memory(self.context)
        self.session = LoadSession()

    def stage(self, **kwargs):
        return stage_elf(self.session, self.elf, expected_sha256=self.digest,
                         context=self.context, transport=self.io, capability="bcb", **kwargs)

    def test_actual_segments_only(self):
        r = self.stage()
        self.assertEqual(r["result"], "RAM_IMAGE_VERIFIED_NOT_EXECUTED")
        self.assertFalse(r["device_execute_ready"])
        self.assertFalse(any(a >= 0x20062000 for a in self.io.ram))
        self.assertNotIn(0x20060300, self.io.ram)
        old = self.io.writes
        with self.assertRaisesRegex(ValueError, "consumed"): self.stage()
        self.assertEqual(self.io.writes, old)

    def test_no_retry_after_success_or_failure(self):
        self.io.short = True
        with self.assertRaisesRegex(ValueError, "write"): self.stage()
        old = self.io.writes
        self.io.short = False
        with self.assertRaisesRegex(ValueError, "consumed"): self.stage()
        self.assertEqual(self.io.writes, old)

    def test_chunk_corruption(self):
        self.io.corrupt = True
        with self.assertRaisesRegex(ValueError, "chunk"): self.stage()
        self.assertEqual(self.io.writes, 1)

    def test_cross_chunk_corruption(self):
        self.io.cross = True
        with self.assertRaisesRegex(ValueError, "final segment"): self.stage()

    def test_context_change(self):
        self.io.change = True
        with self.assertRaisesRegex(ValueError, "context changed"): self.stage()
        self.assertEqual(self.io.writes, 1)

    def test_digest(self):
        self.digest = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest"): self.stage()
        self.assertEqual(self.io.writes, 0)

    def test_lma(self):
        data = bytearray(self.elf); ph = struct.unpack_from("<I", data, 28)[0]
        struct.pack_into("<I", data, ph+12, 0x08000000)
        self.elf = bytes(data); self.digest = hashlib.sha256(self.elf).hexdigest()
        with self.assertRaisesRegex(ValueError, "LMA"): self.stage()
        self.assertEqual(self.io.writes, 0)

    def test_unqualified_contexts(self):
        for field, value in (("power_qualified", False), ("halted", False), ("control", 2),
                             ("pc", 0x0800199e), ("xpsr", 0), ("xpsr", 0x01000003),
                             ("watchdog_qualified", False)):
            self.session = LoadSession()
            original = self.context
            self.context = replace(original, **{field: value})
            with self.assertRaisesRegex(ValueError, "unqualified"): self.stage()
            self.context = original
        self.assertEqual(self.io.writes, 0)

    def test_timeout(self):
        tick = iter(range(10000))
        with self.assertRaisesRegex(ValueError, "deadline"):
            self.stage(timeout_seconds=3, clock=lambda: next(tick))
        self.assertEqual(self.io.writes, 0)


if __name__ == "__main__":
    unittest.main()
