"""Offline design model, NOT a device writer or a Boot admission validator.

Synthetic payload/header oracle exercises ordering and byte-prefix tears only.
No files, peripherals, subprocesses or production modules are modified.
"""
import hashlib
import struct
import unittest
import zlib

BASE = 0x200000
LIMIT = 0x300000
SECTOR = 4096
PAGE = 256
MARKER = b"TMOC"


class Interrupted(Exception):
    pass


def header(payload):
    # Synthetic identity: deliberately not claimed to be ETFW double-zero SHA.
    return (b"ETSL\x04\xff\xff\xff" +
            struct.pack("<III", len(payload), zlib.crc32(payload), 30276) +
            hashlib.sha256(payload).digest()[:8])


class Nor:
    def __init__(self, initial=None, fault=None):
        self.data = bytearray(initial if initial is not None else b"\xff" * (LIMIT-BASE))
        self.fault = fault
        self.trace = []

    def mutate(self, kind, address, data):
        size = len(data)
        if not (BASE <= address < LIMIT and 0 < size <= LIMIT-address):
            raise ValueError("outside recovery slot")
        if kind == "erase":
            if size != SECTOR or address % SECTOR or data != b"\xff" * SECTOR:
                raise ValueError("invalid erase")
        elif kind == "program":
            if size > PAGE or address // PAGE != (address+size-1) // PAGE:
                raise ValueError("invalid page")
        else:
            raise ValueError("invalid operation")
        event = len(self.trace)
        self.trace.append((kind, address, size))
        take = size
        if self.fault is not None and event == self.fault[0]:
            take = self.fault[1]
            if not 0 <= take <= size:
                raise ValueError("invalid injected prefix")
        offset = address-BASE
        for i in range(take):
            self.data[offset+i] = (data[i] if kind == "erase"
                                   else self.data[offset+i] & data[i])
        if self.fault is not None and event == self.fault[0]:
            # Includes full physical completion followed by a failed return.
            raise Interrupted()


def admitted(raw, expected):
    """Independent storage oracle for this synthetic transaction model only."""
    if raw[:8] != b"ETSL\x04\xff\xff\xff" or raw[28:32] != MARKER:
        return False
    length, crc, version = struct.unpack("<III", raw[8:20])
    if length != len(expected) or version != 30276:
        return False
    actual = bytes(raw[SECTOR:SECTOR+length])
    return (actual == expected and zlib.crc32(actual) == crc and
            raw[20:28] == hashlib.sha256(actual).digest()[:8])


def provision(nor, source, pinned_sha, *, base=BASE, kind=4):
    # Real implementation must additionally run the existing full Boot ETFW
    # validator before first erase and again before committing the marker.
    if (base != BASE or kind != 4 or not 0 < len(source) <= 0xF0000 or
            hashlib.sha256(source).hexdigest() != pinned_sha):
        raise ValueError("preflight")
    nor.mutate("erase", BASE, b"\xff" * SECTOR)
    if nor.data[:SECTOR] != b"\xff" * SECTOR:
        raise Interrupted()
    end = SECTOR + len(source)
    for offset in range(SECTOR, (end+SECTOR-1)//SECTOR*SECTOR, SECTOR):
        nor.mutate("erase", BASE+offset, b"\xff" * SECTOR)
        if nor.data[offset:offset+SECTOR] != b"\xff" * SECTOR:
            raise Interrupted()
    for offset in range(0, len(source), PAGE):
        part = source[offset:offset+PAGE]
        nor.mutate("program", BASE+SECTOR+offset, part)
        if nor.data[SECTOR+offset:SECTOR+offset+len(part)] != part:
            raise Interrupted()
    if nor.data[SECTOR:end] != source:
        raise Interrupted()
    nor.mutate("program", BASE, header(source))
    if nor.data[:28] != header(source) or nor.data[28:32] != b"\xff" * 4:
        raise Interrupted()
    nor.mutate("program", BASE+28, MARKER)
    if not admitted(nor.data, source):
        raise Interrupted()


class TransactionTests(unittest.TestCase):
    source = bytes((i*31+7) % 256 for i in range(4096+19))

    def run_model(self, nor, **kwargs):
        provision(nor, self.source, hashlib.sha256(self.source).hexdigest(), **kwargs)

    def test_valid_and_invalid_sources(self):
        nor = Nor()
        for source, digest, args in (
                (b"", hashlib.sha256(b"").hexdigest(), {}),
                (self.source, "0"*64, {}),
                (self.source, hashlib.sha256(self.source).hexdigest(), {"base": BASE-1}),
                (self.source, hashlib.sha256(self.source).hexdigest(), {"kind": 2})):
            with self.assertRaises(ValueError):
                provision(nor, source, digest, **args)
            self.assertEqual(nor.trace, [])
        self.run_model(nor)
        self.assertTrue(admitted(nor.data, self.source))

    def test_low_level_boundary(self):
        nor = Nor()
        for address, data in ((BASE-1, b"x"), (LIMIT, b"x"),
                              (LIMIT-1, b"xx"), (BASE+255, b"xx")):
            with self.assertRaises(ValueError):
                nor.mutate("program", address, data)
        self.assertEqual(nor.trace, [])

    def test_tears_and_retry(self):
        complete = Nor()
        self.run_model(complete)
        cases = 0
        # Both invalid stored contents and a previously committed valid image.
        for initial in (bytes([0xA5])*(LIMIT-BASE), bytes(complete.data)):
            for index, (kind, address, size) in enumerate(complete.trace):
                prefixes = (0, 1, 27, 28, 29, 31, 32, 255, 4095, 4096) if kind == "erase" else range(size+1)
                for prefix in prefixes:
                    with self.subTest(event=index, prefix=prefix, kind=kind):
                        nor = Nor(initial, (index, prefix))
                        with self.assertRaises(Interrupted):
                            self.run_model(nor)
                        self.assertEqual(len(nor.trace), index+1)
                        # A surviving old valid image or fully committed new
                        # image may remain admissible despite an error return.
                        if nor.data[28:32] == MARKER and nor.data[:28] == header(self.source):
                            self.assertTrue(admitted(nor.data, self.source))
                        untouched = (SECTOR+len(self.source)+SECTOR-1)//SECTOR*SECTOR
                        self.assertEqual(nor.data[untouched:], initial[untouched:])
                        nor.fault = None
                        self.run_model(nor)
                        self.assertTrue(admitted(nor.data, self.source))
                        self.assertTrue(all(BASE <= a and a+n <= LIMIT for _, a, n in nor.trace))
                        cases += 1
        print("RECOVERY_MODEL_PREFIX_CASES", cases)

    def test_oracle_rejects_corruption(self):
        nor = Nor()
        self.run_model(nor)
        for offset in (0, 4, 8, 12, 16, 20, 28, SECTOR, SECTOR+len(self.source)-1):
            changed = bytearray(nor.data)
            changed[offset] ^= 1
            self.assertFalse(admitted(changed, self.source))


if __name__ == "__main__":
    unittest.main(verbosity=2)
