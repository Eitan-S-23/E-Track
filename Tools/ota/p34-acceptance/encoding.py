"""Existing legal progressing PATCH size-search and validation algorithms."""
from __future__ import annotations
import hashlib
import json
import lzma
import secrets
import struct
import time

TARGET = 1048576
OUT = pack = unpack = save = save_json = None

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def strict_lzma(props: bytes, compressed: bytes, expected_size: int) -> bytes:
    decoder = lzma.LZMADecompressor(
        format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA1, "dict_size": int.from_bytes(props[1:], "little"),
                  "lc": 2, "lp": 0, "pb": 0}],
    )
    result = decoder.decompress(compressed, max_length=expected_size + 1)
    if len(result) != expected_size or not decoder.eof or decoder.unused_data:
        raise AssertionError("LZMA length/EOS/full-consumption check failed")
    return result

def signed_offset(value: int) -> bytes:
    if abs(value) >= 1 << 63:
        raise ValueError("Offset overflow")
    return struct.pack("<Q", abs(value) | (1 << 63 if value < 0 else 0))

def patch_stream(old: bytes, new: bytes, count: int, seed: int, salt: int) -> bytes:
    if not 0 <= count < len(new) or not 0 <= salt < 65536:
        raise ValueError("Count or salt out of range")
    oldpos = 0
    state = seed & 0xFFFFFFFF
    raw = bytearray()
    for index in range(count):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        nextpos = state % len(old)
        if salt and index >= max(0, count - 8):
            nextpos = (nextpos + salt * (index + 1) * 7919) % len(old)
        raw += signed_offset(1) + signed_offset(0) + signed_offset(nextpos - oldpos - 1)
        raw.append((new[index] - old[oldpos]) & 255)
        oldpos = nextpos
    # This final diff consumes the last seek; all earlier seeks affect actual data.
    raw += signed_offset(1) + signed_offset(len(new) - count - 1) + signed_offset(0)
    raw.append((new[count] - old[oldpos]) & 255)
    raw += new[count + 1:]
    assert len(raw) == len(new) + 24 * (count + 1)
    assert count + 1 <= len(new)
    return bytes(raw)

def encode(old: bytes, new: bytes, count: int, seed: int, salt: int):
    raw = patch_stream(old, new, count, seed, salt)
    alone = pack.lzma_alone_encode(raw, 16384)
    return raw, alone[:5], alone[13:]

def measurement(old: bytes, new: bytes, count: int, seed: int, salt: int):
    relative = f"logs/measure-{count}-{seed}-{salt}.json"
    path = OUT / relative
    if path.exists():
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["base_sha256"] != digest(old) or result["target_sha256"] != digest(new):
            raise AssertionError("Cached input identity differs")
        return result
    started = time.monotonic()
    raw, props, compressed = encode(old, new, count, seed, salt)
    result = {"count": count, "seed": seed, "salt": salt, "groups": count + 1,
              "base_sha256": digest(old), "target_sha256": digest(new),
              "decoded_bytes": len(raw), "compressed_bytes": len(compressed),
              "etu_bytes": 104 + len(compressed), "raw_sha256": digest(raw),
              "compressed_sha256": digest(compressed), "props_hex": props.hex(),
              "elapsed_seconds": round(time.monotonic() - started, 4)}
    save_json(relative, result)
    print(json.dumps(result), flush=True)
    return result

def search(old: bytes, new: bytes, seed: int, budget: int):
    seen = {}
    def sample(count, salt=0):
        key = (count, salt)
        if key not in seen:
            if len(seen) >= budget:
                raise RuntimeError("Bounded compression budget exhausted; no exact witness")
            seen[key] = measurement(old, new, count, seed, salt)
        return seen[key]
    low, high = 0, min(len(new) - 1, 262144)
    lo, hi = sample(low), sample(high)
    if not lo["etu_bytes"] < TARGET < hi["etu_bytes"]:
        raise RuntimeError("Initial sample bracket does not straddle target")
    while high - low > 1:
        middle = (low + high) // 2
        row = sample(middle)
        if row["etu_bytes"] == TARGET:
            return row
        if row["etu_bytes"] < TARGET:
            low = middle
        else:
            high = middle
    # Compression lengths need not be monotonic: explicitly inspect nearby encodings.
    nearest = sorted(seen.values(), key=lambda r: abs(r["etu_bytes"] - TARGET))[:2]
    counts = list(dict.fromkeys([r["count"] for r in nearest] + [low - 1, high + 1]))
    for salt in range(0, 65536):
        for count in counts:
            if not 0 <= count < len(new):
                continue
            row = sample(count, salt)
            if row["etu_bytes"] == TARGET:
                return row
    raise RuntimeError("No exact witness within bounded search")

def package_bytes(old: bytes, new: bytes, raw: bytes, *, declared_size=None,
                  compressed_tail=b"") -> bytes:
    alone = pack.lzma_alone_encode(raw, 16384)
    compressed = alone[13:] + compressed_tail
    native = bytearray(40)
    struct.pack_into(">I", native, 4, len(compressed))
    struct.pack_into("<II", native, 8, len(old), len(new))
    struct.pack_into(">II", native, 16, pack.crc32(old), pack.crc32(new))
    native[24:29] = alone[:5]
    struct.pack_into("<Q", native, 32, len(raw) if declared_size is None else declared_size)
    inner = pack.normalize_patch_header(bytes(native), len(compressed), old, new)
    nonce = secrets.token_bytes(16)
    payload = pack.aes_ctr_xcrypt(bytes.fromhex(unpack.DEFAULT_KEY_HEX), nonce,
                                inner + compressed, True)
    header = pack.build_etu_header(7, nonce, payload,
                                  struct.unpack_from("<I", new, 0x408)[0],
                                  struct.unpack_from("<I", old, 0x408)[0],
                                  hashlib.sha256(old).digest()[:8])
    pack.check_limits(len(new), len(header) + len(payload), "size-proof")
    return header + payload

def witness(old: bytes, new: bytes, row):
    raw, props, compressed = encode(old, new, row["count"], row["seed"], row["salt"])
    assert 104 + len(compressed) == TARGET
    assert strict_lzma(props, compressed, len(raw)) == raw
    assert unpack.bspatch_apply(old, len(new), raw) == new
    blob = package_bytes(old, new, raw)
    assert len(blob) == TARGET
    path = save("cases/reference-1MiB.etu", blob)
    save("cases/reference.raw-patch", raw)
    save("cases/reference.lzma", compressed)
    record = {**row, "path": str(path.relative_to(OUT)), "etu_sha256": digest(blob),
              "lzma_full_consumption": True, "bspatch_byte_identical": True,
              "nonce_policy": "fresh OS-random nonce; ciphertext hash changes on regeneration",
              "encoding": "deliberately non-minimal valid delta; not vendor bsdiff output",
              "hardware": "NOT_RUN", "independent_acceptance": "NOT_RUN"}
    save_json("proof/witness.json", record)
    print(json.dumps(record), flush=True)
