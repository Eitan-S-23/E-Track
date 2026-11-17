"""Independent raw-LZMA vectors for the App generator and real Java decoder."""
import hashlib
import lzma
import os
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
CODEC = runpy.run_path(str(ROOT / ".github/scripts/create_bsdiff_lzma_patch.py"))


def offset(value):
    return (abs(value) | ((1 << 63) if value < 0 else 0)).to_bytes(8, "little")


def control(diff, extra, seek):
    return b"".join(offset(value) for value in (diff, extra, seek))


def header_crc(data):
    data = bytearray(data)
    struct.pack_into(">I", data, 0, zlib.crc32(bytes(4) + data[4:40]))
    return bytes(data)


def pack(old, new, stream):
    compressed = lzma.compress(stream, format=lzma.FORMAT_RAW,
        filters=[dict(id=lzma.FILTER_LZMA1, dict_size=4096, lc=3, lp=0, pb=2)])
    header = bytearray(40)
    struct.pack_into(">I", header, 4, len(compressed))
    struct.pack_into("<II", header, 8, len(old), len(new))
    struct.pack_into(">II", header, 16, zlib.crc32(old), zlib.crc32(new))
    header[24] = 93
    struct.pack_into("<I", header, 25, 4096)
    struct.pack_into("<Q", header, 32, len(stream))
    return header_crc(header) + compressed


def vectors():
    old = bytes(range(256)) * 512
    new = bytearray(old)
    for i in range(0, len(new), 4096):
        new[i] ^= 0x71
    new = bytes(new) + b"new-footer"
    stream = control(len(old), 10, 0) + bytes((b - a) & 255 for a, b in zip(old, new)) + new[-10:]
    valid = pack(old, new, stream)
    yield "basic", old, new, valid, "ok"
    bordered = bytes(3) + old + bytes(3)
    yield "negative-seek", old, bordered, pack(old, bordered,
        control(0, 0, -3) + control(len(bordered), 0, 0) + bytes(len(bordered))), "ok"
    yield "literal", old, new, pack(old, new, control(0, len(new), 0) + new), "ok"
    yield "short-header", old, new, valid[:10], "failure"
    corrupt = bytearray(valid)
    corrupt[0] ^= 1
    yield "header-crc", old, new, bytes(corrupt), "failure"
    for name, position, value in [("padding", 29, 1), ("properties", 24, 255)]:
        corrupt = bytearray(valid)
        corrupt[position] = value
        yield name, old, new, header_crc(corrupt), "failure"
    for name, position, value, endian in [("dictionary", 25, 1 << 30, "<"),
            ("compressed-size", 4, len(valid), ">"), ("target-crc", 20, 0, ">"),
            ("base-size", 8, 1, "<"), ("target-size", 12, 1, "<")]:
        corrupt = bytearray(valid)
        struct.pack_into(endian + "I", corrupt, position, value)
        yield name, old, new, header_crc(corrupt), "failure"
    corrupt = bytearray(valid)
    struct.pack_into("<Q", corrupt, 32, 1 << 62)
    yield "expanded-limit", old, new, header_crc(corrupt), "failure"
    for name, data in [("truncated", valid[:-4]), ("trailing", valid + b"garbage")]:
        corrupt = bytearray(data)
        struct.pack_into(">I", corrupt, 4, len(data) - 40)
        yield name, old, new, header_crc(corrupt), "failure"
    for name, bad in [("zero-control", control(0, 0, 0)),
            ("negative-diff", control(-1, 0, 0)), ("oversized-diff", control(len(new) + 1, 0, 0)),
            ("offset-overflow", control(0, 0, (1 << 63) - 1) + control(1, 0, 1) + b"x"),
            ("short-control", control(0, len(new), 0)[:-1]),
            ("extra-control", stream + control(0, 0, 1))]:
        yield name, old, new, pack(old, new, bad), "failure"
    yield "wrong-base", bytes([old[0] ^ 1]) + old[1:], new, valid, "failure"
    for name in ("patch-sha", "target-sha", "expected-size", "cancel-before", "cancel-during", "existing"):
        yield name, old, new, valid, name


def write_fixtures(directory):
    directory = CODEC["checked_output"](directory)
    directory.mkdir()
    lines = []
    for name, old, new, patch, expected in vectors():
        for suffix, data in [("old", old), ("new", new), ("patch", patch)]:
            with (directory / f"{name}.{suffix}").open("xb") as output:
                output.write(data)
        hashes = [hashlib.sha256(data).hexdigest() for data in (old, patch, new)]
        lines.append("\t".join([name, expected, *hashes, str(len(new))]))
    with (directory / "cases.tsv").open("x", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")
    return len(lines)


class CodecTests(unittest.TestCase):
    def setUp(self):
        parent = CODEC["checked_output"](ROOT / ".cache/app-codec-tests")
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_reference_vectors(self):
        for name, old, new, patch, expected in vectors():
            if expected not in ("ok", "failure"):
                continue
            with self.subTest(name=name):
                base, packed, target = [self.directory / (name + ext) for ext in (".old", ".patch", ".output")]
                base.write_bytes(old)
                packed.write_bytes(patch)
                if expected == "ok":
                    CODEC["apply_patch"](base, packed, target)
                    self.assertEqual(target.read_bytes(), new)
                else:
                    with self.assertRaises((ValueError, lzma.LZMAError)):
                        CODEC["apply_patch"](base, packed, target)
                    self.assertFalse(target.exists())
                self.assertEqual(base.read_bytes(), old)
                self.assertEqual(packed.read_bytes(), patch)

    def test_existing_output_and_source_boundary(self):
        name, old, new, patch, _ = next(vectors())
        base, target, packed, output = [self.directory / value for value in ("old", "new", "patch", "output")]
        base.write_bytes(old)
        target.write_bytes(new)
        packed.write_bytes(patch)
        output.write_bytes(b"keep")
        with self.assertRaises(ValueError):
            CODEC["apply_patch"](base, packed, output)
        self.assertEqual(output.read_bytes(), b"keep")
        with self.assertRaises(ValueError):
            CODEC["create_patch"](base, target, output, 106, 107, "unused")
        with self.assertRaises(ValueError):
            CODEC["create_patch"](base, target, output, 107, 107, "unused")

    @unittest.skipUnless(os.environ.get("BSDIFF_EXE"), "Existing vendor tool not supplied")
    def test_real_vendor_generator_and_reference_reconstruction(self):
        _, old, new, _, _ = next(vectors())
        base, target, patch, restored = [self.directory / name for name in ("base", "target", "patch", "restored")]
        base.write_bytes(old)
        target.write_bytes(new)
        result = CODEC["create_patch"](base, target, patch, 107, 108, os.environ["BSDIFF_EXE"])
        self.assertEqual(result["algorithm"], "bsdiff-lzma-v1")
        CODEC["apply_patch"](base, patch, restored)
        self.assertEqual(restored.read_bytes(), new)
        self.assertFalse((self.directory / "temp_diff.data").exists())


if __name__ == "__main__":
    unittest.main()
