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

def measurement(old: bytes, new: bytes, count: int, seed: int, salt: int, *, strict_cache=False):
    relative = f"logs/measure-{count}-{seed}-{salt}.json"
    path = OUT / relative
    if path.exists():
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["base_sha256"] != digest(old) or result["target_sha256"] != digest(new):
            raise AssertionError("Cached input identity differs")
        if strict_cache:
            expected = {"count": count, "seed": seed, "salt": salt, "groups": count + 1,
                        "decoded_bytes": len(new) + 24 * (count + 1), "props_hex": "0200400000"}
            if any(result.get(k) != v or type(result.get(k)) is not type(v) for k, v in expected.items()):
                raise AssertionError("Cached encoding identity differs")
            if (type(result.get("compressed_bytes")) is not int or result["compressed_bytes"] <= 0
                    or result.get("etu_bytes") != 104 + result["compressed_bytes"]
                    or any(not isinstance(result.get(k), str) or len(result[k]) != 64
                           or any(c not in "0123456789abcdef" for c in result[k])
                           for k in ("raw_sha256", "compressed_sha256"))):
                raise AssertionError("Cached encoding receipt invalid")
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

class ReferenceSearchExhausted(RuntimeError):
    """Safe, typed failure for the explicit new-source search only."""
    def __init__(self, measurements, budget):
        super().__init__("Reference search budget exhausted; no exact witness")
        self.measurements = measurements
        self.budget = budget

def search_adaptive(old: bytes, new: bytes, seed: int, budget: int):
    """Recenter each salted stream; fine compression lengths are not monotonic."""
    if (not old or not new or type(seed) is not int or not 0 <= seed <= 0xffffffff
            or type(budget) is not int or not 2 <= budget <= 256):
        raise ValueError("Invalid adaptive reference search inputs")
    seen = {}
    main_seen = {}
    expanded = set()
    neighbor_measurements = 0
    neighbor_limit = (budget + 9) // 10
    def report(outcome):
        value = dict(strategy="isolated-frontier-count-salt-seed-v4", outcome=outcome,
                     measurements=len(seen), budget=budget, targetBytes=TARGET,
                     neighborMeasurements=neighbor_measurements, neighborLimit=neighbor_limit,
                     mainMeasurements=len(main_seen), mainSamples=list(main_seen.values()),
                     baseSha256=digest(old), targetSha256=digest(new), samples=list(seen.values()))
        save_json("search-report.json", value)
        return value
    def witness(row, found_by="main"):
        report("exact-witness")
        return dict(row, strategy="isolated-frontier-count-salt-seed-v4", measurements=len(seen), budget=budget,
                    neighborMeasurements=neighbor_measurements, mainMeasurements=len(main_seen), foundBy=found_by)
    def sample(count, salt, stream_seed=seed):
        key = (count, stream_seed, salt)
        if key not in seen:
            if len(seen) >= budget:
                report("budget-exhausted")
                raise ReferenceSearchExhausted(len(seen), budget)
            seen[key] = measurement(old, new, count, stream_seed, salt, strict_cache=True)
        return seen[key]

    def main_sample(count, salt, stream_seed=seed):
        row = sample(count, salt, stream_seed)
        main_seen[(count, stream_seed, salt)] = row
        return row

    def explore(stream_seed):
        nonlocal neighbor_measurements
        # A close count is not a monotonic root. Explore a bounded best-first
        # frontier before abandoning that salt; newly close neighbors join it.
        while neighbor_measurements < neighbor_limit and len(seen) < budget:
            near = [r for r in seen.values() if r['seed'] == stream_seed
                    and abs(r['etu_bytes'] - TARGET) <= 8
                    and (r['count'], r['seed'], r['salt']) not in expanded]
            if not near:
                break
            anchor = min(near, key=lambda r: abs(r['etu_bytes'] - TARGET))
            expanded.add((anchor['count'], anchor['seed'], anchor['salt']))
            for delta in (1, -1, 2, -2):
                count = anchor['count'] + delta
                if neighbor_measurements >= neighbor_limit or len(seen) >= budget:
                    break
                if not 0 <= count < len(new) or (count, stream_seed, anchor['salt']) in seen:
                    continue
                row = sample(count, anchor['salt'], stream_seed)
                neighbor_measurements += 1
                if row['etu_bytes'] == TARGET:
                    return row
        return None

    low, high = 0, min(len(new) - 1, 262144)
    lo, hi = main_sample(low, 0), main_sample(high, 0)
    for row in (lo, hi):
        if row["etu_bytes"] == TARGET:
            return witness(row)
    if not lo["etu_bytes"] < TARGET < hi["etu_bytes"]:
        report("initial-bracket-miss")
        raise RuntimeError("Initial sample bracket does not straddle target")
    # The coarse slope is stable enough for a proposal, not a monotonicity claim.
    slope = (hi["etu_bytes"] - lo["etu_bytes"]) / (high - low)
    while high - low > 1:
        middle = (low + high) // 2
        row = main_sample(middle, 0)
        if row["etu_bytes"] == TARGET:
            return witness(row)
        if row["etu_bytes"] < TARGET:
            low = middle
        else:
            high = middle

    # Keep v2's logical seed quotas. Both beams share one physical encoding budget;
    # a frontier point later requested by the main beam is not charged twice.
    # The main beam retains v2's proposals, anchor history and logical seed quota.
    # Frontier results share the global budget/cache, never its proposal history.
    primary_limit = max(len(main_seen), budget - budget // 4)
    for stream_seed, first_salt, limit in ((seed, 1, primary_limit), ((seed + 1) & 0xffffffff, 0, budget)):
        row = explore(stream_seed)
        if row is not None:
            return witness(row, "frontier")
        for salt in range(first_salt, 65536):
            if len(main_seen) >= limit:
                break
            stream_rows = [r for r in main_seen.values() if r["seed"] == stream_seed]
            anchor = min(stream_rows or list(main_seen.values()), key=lambda r: abs(r["etu_bytes"] - TARGET))
            count = anchor["count"]
            # Bound each salt's work so one noisy local neighborhood cannot monopolize it.
            for _ in range(4):
                if len(main_seen) >= limit:
                    break
                row = main_sample(count, salt, stream_seed)
                error = TARGET - row["etu_bytes"]
                if error == 0:
                    return witness(row)
                nearby = explore(stream_seed)
                if nearby is not None:
                    return witness(nearby, "frontier")
                proposal = max(0, min(len(new) - 1, count + round(error / slope)))
                if (proposal, stream_seed, salt) in main_seen or proposal == count:
                    candidates = (count + delta for radius in range(1, 5) for delta in (radius, -radius))
                    proposal = next((c for c in candidates if 0 <= c < len(new) and (c, stream_seed, salt) not in main_seen), None)
                    if proposal is None:
                        break
                count = proposal
    if len(seen) >= budget:
        report("budget-exhausted")
        raise ReferenceSearchExhausted(len(seen), budget)
    report("parameter-space-exhausted")
    raise RuntimeError("Reference search parameter space exhausted")

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
