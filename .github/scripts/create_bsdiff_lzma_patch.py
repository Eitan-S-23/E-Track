"""App bsdiff-lzma-v1 adapter for the existing MCU encoder, without ETU/AES."""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

FORMAT = "bsdiff-lzma-v1"
MIN_SOURCE = 107
MAX_FILE = 256 * 1024 * 1024
MAX_CONTROLS = 1_000_000
CHUNK = 65536
ROOT = Path(__file__).resolve().parents[2]


def checked_output(value):
    path = Path(os.path.abspath(value))
    path.relative_to(ROOT)
    path.resolve().relative_to(ROOT.resolve())
    for item in (path, *path.parents):
        if item.exists() and (item.is_symlink() or getattr(item.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Redirected output")
    return path


def sha256_file(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def crc32_file(path):
    crc = 0
    with Path(path).open("rb") as source:
        for data in iter(lambda: source.read(CHUNK), b""):
            crc = zlib.crc32(data, crc)
    return crc


def header_info(header, length):
    if len(header) != 40 or not 40 < length <= MAX_FILE:
        raise ValueError("Invalid patch size/header")
    hcrc, compressed = struct.unpack_from(">II", header)
    old_size, new_size = struct.unpack_from("<II", header, 8)
    old_crc, new_crc = struct.unpack_from(">II", header, 16)
    dictionary = struct.unpack_from("<I", header, 25)[0]
    expanded = struct.unpack_from("<Q", header, 32)[0]
    props = header[24]
    lc, lp, pb = props % 9, props // 9 % 5, props // 45
    if hcrc != zlib.crc32(bytes(4) + header[4:]) or header[29:32] != bytes(3):
        raise ValueError("Header CRC/padding mismatch")
    if compressed != length - 40 or not 0 < old_size <= MAX_FILE or not 0 < new_size <= MAX_FILE:
        raise ValueError("Header size mismatch")
    if not 4096 <= dictionary <= 8 * 1024 * 1024 or pb > 4 or lc + lp > 4:
        raise ValueError("LZMA properties/memory limit")
    if not 24 <= expanded <= new_size + 24 * MAX_CONTROLS:
        raise ValueError("Expanded stream limit")
    return dict(old_size=old_size, new_size=new_size, old_crc=old_crc, new_crc=new_crc,
                expanded=expanded, filters=[dict(id=lzma.FILTER_LZMA1, dict_size=dictionary, lc=lc, lp=lp, pb=pb)])


class PatchStream:
    def __init__(self, source, info):
        self.source = source
        self.decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=info["filters"])
        self.limit = info["expanded"]
        self.consumed = 0

    def read(self, count):
        result = bytearray()
        while len(result) < count and not self.decoder.eof:
            data = self.source.read(CHUNK) if self.decoder.needs_input else b""
            if self.decoder.needs_input and not data:
                raise ValueError("Truncated LZMA data")
            result.extend(self.decoder.decompress(data, max_length=count - len(result)))
        self.consumed += len(result)
        if self.consumed > self.limit:
            raise ValueError("Expanded stream exceeds declared size")
        return result

    def exact(self, count):
        data = self.read(count)
        if len(data) != count:
            raise ValueError("Truncated control/data stream")
        return data

    def finish(self):
        if self.consumed != self.limit or self.read(1) or not self.decoder.eof:
            raise ValueError("Expanded length/EOS mismatch")
        if self.decoder.unused_data or self.source.read(1):
            raise ValueError("Trailing compressed bytes")


def signed_offset(data):
    value = int.from_bytes(data, "little")
    return -(value & ((1 << 63) - 1)) if value >> 63 else value


def apply_patch(old_path, patch_path, output_path):
    """Independent liblzma/file-backed reconstruction used by CI before signing."""
    output = checked_output(output_path)
    old_path, patch_path = Path(old_path), Path(patch_path)
    if output.exists() or output == old_path.resolve() or output == patch_path.resolve():
        raise ValueError("Output must be new and distinct")
    created = False
    try:
        with old_path.open("rb") as old, patch_path.open("rb") as patch:
            info = header_info(patch.read(40), patch_path.stat().st_size)
            if old_path.stat().st_size != info["old_size"] or crc32_file(old_path) != info["old_crc"]:
                raise ValueError("Base identity mismatch")
            stream = PatchStream(patch, info)
            old_pos = new_pos = controls = new_crc = 0
            with output.open("xb") as target:
                created = True
                while new_pos < info["new_size"]:
                    controls += 1
                    if controls > MAX_CONTROLS:
                        raise ValueError("Control limit")
                    control = stream.exact(24)
                    diff, extra, seek = (signed_offset(control[i:i + 8]) for i in (0, 8, 16))
                    if diff < 0 or extra < 0 or new_pos + diff + extra > info["new_size"] or not (diff or extra or seek):
                        raise ValueError("Invalid control")
                    for mode, remaining in enumerate((diff, extra)):
                        while remaining:
                            count = min(CHUNK, remaining)
                            data = stream.exact(count)
                            if mode == 0:
                                start, end = max(0, old_pos), min(info["old_size"], old_pos + count)
                                if start < end:
                                    old.seek(start)
                                    original = old.read(end - start)
                                    if len(original) != end - start:
                                        raise ValueError("Truncated base")
                                    for i, value in enumerate(original, start - old_pos):
                                        data[i] = (data[i] + value) & 255
                                old_pos += count
                            target.write(data)
                            new_crc = zlib.crc32(data, new_crc)
                            new_pos += count
                            remaining -= count
                    old_pos += seek
                    if not -(1 << 63) <= old_pos < (1 << 63):
                        raise ValueError("Base offset overflow")
                stream.finish()
                if new_crc != info["new_crc"]:
                    raise ValueError("Target CRC mismatch")
                target.flush()
                os.fsync(target.fileno())
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def create_patch(old_path, new_path, output_path, from_version_code, to_version_code, bsdiff_exe):
    output = checked_output(output_path)
    old_path, new_path = Path(old_path).resolve(), Path(new_path).resolve()
    if from_version_code < MIN_SOURCE or to_version_code <= from_version_code:
        raise ValueError("Source decoder/version is not compatible")
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Output must be new in an existing project directory")
    for value in (old_path, new_path):
        if not value.is_file() or not 0 < value.stat().st_size <= MAX_FILE:
            raise ValueError("Missing/oversized original APK")
    before = [sha256_file(old_path), sha256_file(new_path)]
    # The vendor writes temp_diff.data into cwd; isolate this exact invocation.
    with tempfile.TemporaryDirectory(prefix="app-bsdiff-", dir=output.parent) as work:
        work = checked_output(work)
        raw, restored = checked_output(work / "raw.patch"), checked_output(work / "restored.apk")
        subprocess.run([str(Path(bsdiff_exe).resolve()), str(old_path), str(new_path), str(raw), "-aes", "0", "-eos", "1"],
                       cwd=work, timeout=360, check=True)
        with raw.open("r+b") as file:
            header = bytearray(file.read(40))
            header_info(header, raw.stat().st_size)
            header[29:32] = bytes(3)
            struct.pack_into(">I", header, 0, zlib.crc32(bytes(4) + header[4:]))
            file.seek(0)
            file.write(header)
        apply_patch(old_path, raw, restored)
        if sha256_file(restored) != before[1] or restored.stat().st_size != new_path.stat().st_size:
            raise ValueError("Reconstruction SHA/size mismatch")
        if before != [sha256_file(old_path), sha256_file(new_path)]:
            raise ValueError("Original bytes changed")
        with raw.open("rb") as source, output.open("xb") as target:
            for chunk in iter(lambda: source.read(CHUNK), b""):
                target.write(chunk)
    return dict(assetName=output.name, algorithm=FORMAT, patchFormat=FORMAT,
                fromVersionCode=from_version_code, toVersionCode=to_version_code,
                sha256=sha256_file(output), size=output.stat().st_size,
                oldSha256=before[0], newSha256=before[1])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        if len(sys.argv) != 5:
            raise ValueError("apply requires base, patch and output")
        apply_patch(*sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_apk", type=Path)
    parser.add_argument("new_apk", type=Path)
    parser.add_argument("output_patch", type=Path)
    parser.add_argument("--from-version-code", type=int, required=True)
    parser.add_argument("--to-version-code", type=int, required=True)
    parser.add_argument("--bsdiff-exe", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path)
    args = parser.parse_args()
    metadata_path = checked_output(args.metadata_output) if args.metadata_output else None
    if metadata_path and metadata_path.exists():
        raise ValueError("Metadata already exists")
    metadata = create_patch(args.old_apk, args.new_apk, args.output_patch,
                            args.from_version_code, args.to_version_code, args.bsdiff_exe)
    if metadata_path:
        with metadata_path.open("x", encoding="utf-8") as target:
            json.dump(metadata, target, indent=2)
    else:
        print(json.dumps(metadata))


if __name__ == "__main__":
    main()
