#!/usr/bin/env python3
import argparse
import hashlib
import json
import struct
from pathlib import Path


MAGIC = b"TRACEPATCH1\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_operation(operations: list[dict], data_stream: bytearray, op: dict, data: bytes | None = None) -> None:
    if operations and operations[-1]["op"] == op["op"]:
        previous = operations[-1]
        if op["op"] == "copy" and previous["offset"] + previous["length"] == op["offset"]:
            previous["length"] += op["length"]
            return
        if op["op"] == "data":
            previous["length"] += op["length"]
            if data:
                data_stream.extend(data)
            return

    operations.append(op)
    if data:
        data_stream.extend(data)


def create_patch(old_path: Path, new_path: Path, output_path: Path, from_version_code: int, to_version_code: int, block_size: int) -> dict:
    old_bytes = old_path.read_bytes()
    new_bytes = new_path.read_bytes()

    old_blocks: dict[tuple[int, str], list[int]] = {}
    for offset in range(0, len(old_bytes), block_size):
        block = old_bytes[offset : offset + block_size]
        old_blocks.setdefault((len(block), sha256_bytes(block)), []).append(offset)

    operations: list[dict] = []
    data_stream = bytearray()

    for offset in range(0, len(new_bytes), block_size):
        block = new_bytes[offset : offset + block_size]
        candidates = old_blocks.get((len(block), sha256_bytes(block)), [])
        match_offset = None
        for candidate in candidates:
            if old_bytes[candidate : candidate + len(block)] == block:
                match_offset = candidate
                break

        if match_offset is None:
            append_operation(
                operations,
                data_stream,
                {"op": "data", "length": len(block)},
                block,
            )
        else:
            append_operation(
                operations,
                data_stream,
                {"op": "copy", "offset": match_offset, "length": len(block)},
            )

    manifest = {
        "format": "trace-apk-incremental-patch",
        "schemaVersion": 1,
        "fromVersionCode": from_version_code,
        "toVersionCode": to_version_code,
        "oldSize": len(old_bytes),
        "newSize": len(new_bytes),
        "oldSha256": sha256_file(old_path),
        "newSha256": sha256_file(new_path),
        "blockSize": block_size,
        "operations": operations,
    }
    manifest_bytes = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<I", len(manifest_bytes)))
        f.write(manifest_bytes)
        f.write(data_stream)

    return {
        "assetName": output_path.name,
        "algorithm": "tracepatch",
        "patchFormat": "tracepatch",
        "fromVersionCode": from_version_code,
        "toVersionCode": to_version_code,
        "sha256": sha256_file(output_path),
        "size": output_path.stat().st_size,
        "oldSha256": manifest["oldSha256"],
        "newSha256": manifest["newSha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Trace APK incremental patch")
    parser.add_argument("old_apk", type=Path)
    parser.add_argument("new_apk", type=Path)
    parser.add_argument("output_patch", type=Path)
    parser.add_argument("--from-version-code", type=int, required=True)
    parser.add_argument("--to-version-code", type=int, required=True)
    parser.add_argument("--block-size", type=int, default=65536)
    parser.add_argument("--metadata-output", type=Path)
    args = parser.parse_args()

    metadata = create_patch(
        args.old_apk,
        args.new_apk,
        args.output_patch,
        args.from_version_code,
        args.to_version_code,
        args.block_size,
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
