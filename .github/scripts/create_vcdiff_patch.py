#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

VCDIFF_MAGIC = b"\xd6\xc3\xc4\x00"
VCD_SECONDARY = 0x01
VCD_CODETABLE = 0x02
VCD_APPHEADER = 0x04


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_vcdiff_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        if offset >= len(data):
            raise ValueError("Truncated VCDIFF variable-length integer")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, offset


def _skip_vcdiff_block(data: bytes, offset: int) -> int:
    length, offset = _read_vcdiff_varint(data, offset)
    end = offset + length
    if end > len(data):
        raise ValueError("Truncated VCDIFF header block")
    return end


def strip_vcdiff_app_header(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 5 or data[:4] != VCDIFF_MAGIC:
        raise ValueError(f"{path} is not a VCDIFF file")

    header_indicator = data[4]
    if header_indicator & ~(VCD_SECONDARY | VCD_CODETABLE | VCD_APPHEADER):
        raise ValueError(
            f"{path} has unsupported VCDIFF header flags: 0x{header_indicator:02x}"
        )
    if not (header_indicator & VCD_APPHEADER):
        return

    offset = 5
    if header_indicator & VCD_SECONDARY:
        offset += 1
        if offset > len(data):
            raise ValueError("Truncated VCDIFF secondary compressor id")
    if header_indicator & VCD_CODETABLE:
        offset = _skip_vcdiff_block(data, offset)

    app_header_start = offset
    app_header_end = _skip_vcdiff_block(data, offset)

    stripped = bytearray()
    stripped.extend(data[:4])
    stripped.append(header_indicator & ~VCD_APPHEADER)
    stripped.extend(data[5:app_header_start])
    stripped.extend(data[app_header_end:])
    path.write_bytes(stripped)


def assert_vcdiff_without_app_header(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 5 or data[:4] != VCDIFF_MAGIC:
        raise ValueError(f"{path} is not a VCDIFF file")
    if data[4] & VCD_APPHEADER:
        raise ValueError("VCDIFF patch still contains VCD_APPHEADER")


def create_patch(
    old_path: Path,
    new_path: Path,
    output_path: Path,
    from_version_code: int,
    to_version_code: int,
) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "xdelta3",
            "-e",
            "-S",
            "none",
            "-s",
            str(old_path),
            str(new_path),
            str(output_path),
        ],
        check=True,
    )
    # xdelta3's CLI writes a file-name application header by default.
    # The Flutter vcdiff_decoder package rejects VCD_APPHEADER, so keep
    # generated patches within the decoder-supported RFC3284 subset.
    strip_vcdiff_app_header(output_path)
    assert_vcdiff_without_app_header(output_path)

    return {
        "assetName": output_path.name,
        "algorithm": "vcdiff",
        "patchFormat": "vcdiff",
        "fromVersionCode": from_version_code,
        "toVersionCode": to_version_code,
        "sha256": sha256_file(output_path),
        "size": output_path.stat().st_size,
        "oldSha256": sha256_file(old_path),
        "newSha256": sha256_file(new_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Trace VCDIFF APK patch with xdelta3")
    parser.add_argument("old_apk", type=Path)
    parser.add_argument("new_apk", type=Path)
    parser.add_argument("output_patch", type=Path)
    parser.add_argument("--from-version-code", type=int, required=True)
    parser.add_argument("--to-version-code", type=int, required=True)
    parser.add_argument("--metadata-output", type=Path)
    args = parser.parse_args()

    metadata = create_patch(
        args.old_apk,
        args.new_apk,
        args.output_patch,
        args.from_version_code,
        args.to_version_code,
    )
    if args.metadata_output:
        args.metadata_output.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
