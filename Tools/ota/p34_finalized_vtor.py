"""Exact provisional finalized R2 observation policy; no device operations."""
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"Tools/ota"))
import p34_recovery_sources as sources

IDENTITIES = {
    "r2-a.bin": "7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf",
    "r2-b.bin": "e4737cfcbbb884c4a7fa407ea733486425674c7ed2723d0f8cf3263beb4e8802",
}
ORIGIN, RUNTIME, TABLE = 0x08010000, 0x08010800, 524


def classify(image, *, before, after, table, dhcsr, halted):
    require = sources.require
    digest = hashlib.sha256(image).hexdigest()
    require(len(image) == 619580 and digest in IDENTITIES.values(), "unbound finalized image")
    sources.verify(image)
    require(type(before) is int and type(after) is int and type(dhcsr) is int and
            type(halted) is bool and 0 <= dhcsr <= 0xffffffff, "observation types")
    require(not halted and not dhcsr & ((1 << 17) | (1 << 25)), "halt/reset observation")
    require(before == after and before in (ORIGIN, RUNTIME), "unstable or unrelated VTOR")
    require(type(table) is bytes and table == image[before-ORIGIN:before-ORIGIN+TABLE],
            "table mismatch")
    return dict(schema="p34-finalized-r2-observation/v1", image_sha256=digest,
                phase="app-early" if before == ORIGIN else "app-runtime",
                operational_readiness="NOT_ESTABLISHED", device_authorized=False)


def selftest():
    cases = 0
    for name in IDENTITIES:
        image = (ROOT/".cache/p34-recovery-sources1"/name).read_bytes()
        def fields(address):
            return dict(before=address, after=address, table=image[address-ORIGIN:address-ORIGIN+TABLE],
                        dhcsr=0, halted=False)
        for address in (ORIGIN, RUNTIME):
            result = classify(image, **fields(address))
            assert result["operational_readiness"] == "NOT_ESTABLISHED"
            cases += 1
        bad_fields = [dict(fields(RUNTIME), before=a, after=a) for a in
                      (0, 0x08000000, ORIGIN+0x400, RUNTIME+4, 0x20000000)]
        bad_fields += [dict(fields(RUNTIME), before=ORIGIN),
                       dict(fields(RUNTIME), table=b""),
                       dict(fields(RUNTIME), table=image[:TABLE]),
                       dict(fields(RUNTIME), dhcsr=1 << 17),
                       dict(fields(RUNTIME), dhcsr=1 << 25),
                       dict(fields(RUNTIME), halted=True),
                       dict(fields(RUNTIME), before=True)]
        for values in bad_fields:
            try:
                classify(image, **values)
            except ValueError:
                cases += 1
            else:
                raise AssertionError("invalid observation accepted")
        for changed in (image[:-1], image+b"x", image[:0x500]+bytes([image[0x500]^1])+image[0x501:]):
            try:
                classify(changed, **fields(RUNTIME))
            except ValueError:
                cases += 1
            else:
                raise AssertionError("unbound image accepted")
    print("FINALIZED_VTOR_POLICY_PASS cases="+str(cases))


if __name__ == "__main__":
    sources.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                    sys.dont_write_bytecode, "isolated root required")
    selftest()
