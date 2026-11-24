"""Offline-only, exact-R2 VTOR classification. Does not authorize device use."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_fault_validate as validate

SCHEMA = "p34-r2-dual-vectors/v1"
SHA256 = "387a48705d81941834b6644d22da9573df3160b1717e56338cd86cdf948bcdb3"
ORIGIN, RUNTIME, TABLE_BYTES = 0x08010000, 0x08010800, 524


def require(ok, message):
    if not ok:
        raise ValueError(message)


def profile(raw, symbols, entries):
    require(hashlib.sha256(raw).hexdigest() == SHA256, "not the reviewed raw R2 image")
    tables = validate.tables(raw, symbols, entries)
    require(tables["runtime_address"] == RUNTIME, "unreviewed runtime address")
    return dict(schema=SCHEMA, image_sha256=SHA256, image_bytes=len(raw),
                primary=ORIGIN, runtime=RUNTIME,
                primary_table=raw[:TABLE_BYTES].hex(),
                runtime_table=raw[RUNTIME-ORIGIN:RUNTIME-ORIGIN+TABLE_BYTES].hex(),
                artifact_kind="unfinalized-isolated-App-BIN", device_authorized=False)


def classify(p, raw_image, *, vtor_before, vtor_after, table, dhcsr, halted):
    require(p["schema"] == SCHEMA and p["image_sha256"] == SHA256 and
            (p["primary"], p["runtime"]) == (ORIGIN, RUNTIME), "unreviewed vector profile")
    require(len(raw_image) == p["image_bytes"] and hashlib.sha256(raw_image).hexdigest() == SHA256,
            "full image identity mismatch; finalized headers need a new reviewed profile")
    require(type(vtor_before) is int and type(vtor_after) is int and
            type(dhcsr) is int and 0 <= dhcsr <= 0xffffffff and type(halted) is bool,
            "invalid observation fields")
    require(not halted and not dhcsr & ((1 << 17) | (1 << 25)), "halt/reset sample is not stable App evidence")
    require(vtor_before == vtor_after, "VTOR changed during sample")
    require(vtor_before in (ORIGIN, RUNTIME), "unbound App vector address")
    offset = vtor_before-ORIGIN
    expected = raw_image[offset:offset+TABLE_BYTES]
    key = "primary_table" if vtor_before == ORIGIN else "runtime_table"
    require(p[key] == expected.hex(), "profile/table identity mismatch")
    require(type(table) is bytes and table == expected, "observed vector table mismatch or short read")
    return dict(phase="app-early" if vtor_before == ORIGIN else "app-runtime",
                runtime_vectors_active=vtor_before == RUNTIME,
                operational_readiness="NOT_ESTABLISHED", image_sha256=SHA256,
                scope="stable image/table snapshot only, not reset-generation or OTA-success proof")


def selftest():
    area = ROOT / ".cache/p34-early-usb-r2"
    raw = (area / "on/b/app-gcc/X-Track-App-GCC.bin").read_bytes()
    p = profile(raw, validate.parse_symbols((area / "on/symbols.log").read_text()),
                json.loads((area / "prepared.json").read_text())["entries"])
    cases = 0
    def sample(address):
        return dict(vtor_before=address, vtor_after=address,
                    table=raw[address-ORIGIN:address-ORIGIN+TABLE_BYTES], dhcsr=0, halted=False)
    for address, phase in ((ORIGIN, "app-early"), (RUNTIME, "app-runtime")):
        value = classify(p, raw, **sample(address))
        assert value["phase"] == phase and value["operational_readiness"] == "NOT_ESTABLISHED"
        cases += 1
    bad = [dict(sample(RUNTIME), vtor_before=a, vtor_after=a)
           for a in (0, 0x08000000, 0x08010400, RUNTIME+4, 0x20000000)]
    bad += [dict(sample(RUNTIME), vtor_before=ORIGIN), dict(sample(RUNTIME), table=bytes(TABLE_BYTES)),
            dict(sample(RUNTIME), table=raw[:TABLE_BYTES]), dict(sample(RUNTIME), table=b""),
            dict(sample(RUNTIME), dhcsr=1 << 25), dict(sample(RUNTIME), dhcsr=1 << 17),
            dict(sample(RUNTIME), halted=True)]
    for fields in bad:
        try:
            classify(p, raw, **fields)
        except ValueError:
            cases += 1
        else:
            raise AssertionError("bad vector observation accepted")
    altered = bytearray(raw)
    altered[0x408] ^= 1
    for image in (raw[:-1], bytes(altered), bytes(len(raw))):
        try:
            classify(p, image, **sample(RUNTIME))
        except ValueError:
            cases += 1
        else:
            raise AssertionError("different image/header accepted")
    for bad_profile in (dict(p, schema="future"), dict(p, runtime=RUNTIME+1024),
                        dict(p, runtime_table=raw[:TABLE_BYTES].hex())):
        try:
            classify(bad_profile, raw, **sample(RUNTIME))
        except ValueError:
            cases += 1
        else:
            raise AssertionError("changed profile accepted")
    # Preserve the historical collector's strict behavior; do not broaden it in place.
    import p34_full_trace as legacy
    assert legacy.phase(ORIGIN, 0, False) == "app"
    cases += 1
    try:
        legacy.phase(RUNTIME, 0, False)
    except RuntimeError:
        cases += 1
    else:
        raise AssertionError("legacy collector unexpectedly accepts the new table")
    print("R2_VTOR_POLICY_PASS cases=" + str(cases))


if __name__ == "__main__":
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "isolated project root required")
    require(sys.argv[1:] == ["--selftest"], "only offline selftest is supported")
    selftest()
