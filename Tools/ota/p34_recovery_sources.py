"""Prepare provisional R2 finalized files offline, without importing device code."""
import ast
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".agents/skills/e-track-flutter-debug/scripts"))
from host_io import checked_output


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify(image):
    require(0x460 <= len(image) <= 0xF0000, "length")
    hdr = image[0x400:0x460]
    require(hdr[:4] == b"ETFW", "magic")
    require(struct.unpack_from("<I", hdr, 36)[0] == len(image), "exact length")
    require(zlib.crc32(hdr[:92]) == struct.unpack_from("<I", hdr, 92)[0], "CRC")
    masked = bytearray(image)
    masked[0x428:0x448] = bytes(32)
    masked[0x45c:0x460] = bytes(4)
    require(hashlib.sha256(masked).digest() == hdr[40:72], "image SHA")
    return hdr


def record(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
            sys.dont_write_bytecode, "isolated project-root execution required")
    out = checked_output(ROOT, ".cache/p34-recovery-sources1")
    names = ["r2-a.bin", "r2-b.bin", "result.json"]
    outputs = {name: checked_output(ROOT, out/name) for name in names}
    require(not out.exists(), "preserve prior evidence")
    pack = ROOT / "Tools/etu_pack.py"
    tree = ast.parse(pack.read_text(encoding="utf-8-sig"))
    functions = {"crc32", "sha256", "parse_version_name", "build_fw_header"}
    constants = {"FW_HEADER_OFFSET", "FW_HEADER_SIZE", "FW_HEADER_PAD_OFF",
                 "FW_HEADER_PAD_LEN", "FW_HEADER_CRC_OFF", "MAX_IMAGE_LEN"}
    selected = [node for node in tree.body if
                isinstance(node, ast.FunctionDef) and node.name in functions or
                isinstance(node, ast.Assign) and len(node.targets) == 1 and
                isinstance(node.targets[0], ast.Name) and node.targets[0].id in constants]
    require(len(selected) == 10, "finalizer extraction changed")
    ns = dict(struct=struct, hashlib=hashlib, zlib=zlib)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(pack), "exec"), ns)
    area = ROOT / ".cache/p34-early-usb-r2/on/b/app-gcc"
    raw_path = area / "X-Track-App-GCC.bin"
    raw = raw_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() ==
            "387a48705d81941834b6644d22da9573df3160b1717e56338cd86cdf948bcdb3",
            "reviewed raw R2 drift")
    images = []
    negatives = 0
    prepared = []
    for name, version in (("r2-a.bin", "3.2.76-r2a"), ("r2-b.bin", "3.2.77-r2b")):
        image = bytearray(raw)
        image[0x400:0x460] = ns["build_fw_header"](raw, version, 1786320000)
        image = bytes(image)
        hdr = verify(image)
        require(image[:0x400] == raw[:0x400] and image[0x460:] == raw[0x460:],
                "non-header bytes changed")
        for bad in (image[:-1], image+b"TRAILER!",
                    image[:0x500]+bytes([image[0x500]^1])+image[0x501:],
                    image[:0x408]+bytes([image[0x408]^1])+image[0x409:]):
            try:
                verify(bad)
            except ValueError:
                negatives += 1
            else:
                raise AssertionError("invalid finalized file accepted")
        chunks = [hashlib.sha256(image[i:i+4096]).hexdigest()
                  for i in range(0, len(image), 4096)]
        prepared.append((name, image))
        images.append(dict(file=name, version_name=version,
            version_code=struct.unpack_from("<I", hdr, 8)[0],
            sha256=hashlib.sha256(image).hexdigest(), bytes=len(image),
            stored_image_sha256=hdr[40:72].hex(), payload_crc32=zlib.crc32(image),
            chunk_size=4096, chunk_sha256=chunks, manifest_bytes=len(chunks)*32,
            primary_address=0x08010000, runtime_address=0x08010800,
            primary_table=image[:524].hex(), runtime_table=image[0x800:0x800+524].hex(),
            vector_binding="identical bytes to reviewed raw R2; not a live collector profile",
            full_boot_admission="NOT_RUN", provisional_version=True))
    inputs = [record(p) for p in (Path(__file__), pack, raw_path,
              area/"X-Track-App-GCC.elf", area/"X-Track-App-GCC.map")]
    # Complete source validation and every output preflight before first write.
    out.mkdir()
    for name, image in prepared:
        with outputs[name].open("xb") as stream:
            stream.write(image)
    result = dict(scope="offline finalized source preparation only", inputs=inputs,
                  images=images, negative_cases=negatives, hardware=False,
                  full_boot_admission=False, live_profile_ready=False,
                  production_version_reservation=False,
                  outputs=[record(outputs[name]) for name, _ in prepared])
    with outputs["result.json"].open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print("R2_FINALIZED_PROVISIONAL sources=2 identity_negatives=" + str(negatives))
    for item in images:
        print(item["file"], item["bytes"], item["sha256"])


if __name__ == "__main__":
    main()
