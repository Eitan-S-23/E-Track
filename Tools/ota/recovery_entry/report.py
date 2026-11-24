"""Decode a bound diagnostic, never authorize a device action from its marker."""
import struct
import zlib

COMPLETE = 0x52454f42


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _valid(raw):
    return (struct.unpack_from("<I", raw)[0] == 0x43425445 and raw[4] == 1 and
            struct.unpack_from("<I", raw, 60)[0] == zlib.crc32(raw[:60]))


def _active(a, b):
    va, vb = _valid(a), _valid(b)
    if not va and not vb:
        return 0
    if va and not vb:
        return 1
    if vb and not va:
        return 2
    sa, sb = struct.unpack_from("<H", a, 8)[0], struct.unpack_from("<H", b, 8)[0]
    difference = (sa - sb) & 0xffff
    return 1 if difference == 0 or difference < 0x8000 else 2


def decode_bcb(raw, *, expected_epoch, expected_operation):
    require(type(expected_epoch) is int and 0 < expected_epoch <= 0xffffffff,
            "nonzero expected epoch required")
    require(isinstance(expected_operation, bytes) and len(expected_operation) == 32 and
            any(expected_operation), "nonzero expected operation required")
    require(isinstance(raw, bytes) and len(raw) == 316, "exact BCB report size")
    started, epoch, completed, result, stable, active, marker = struct.unpack_from("<7I", raw)
    require(started == 1 and marker == COMPLETE, "incomplete report")
    require(epoch == expected_epoch and raw[28:60] == expected_operation, "report binding mismatch")
    require(completed <= 4 and stable in (0, 1), "invalid capture counters")
    require(result in (0, 0xffffffff, 0xfffffffe), "unknown result code")
    require(active in (0, 1, 2, 0xffffffff), "unknown arbiter code")
    signed_result = result if result < 0x80000000 else result - 0x100000000
    if result:
        require(not stable and active == 0xffffffff, "failed report claims usable snapshot")
        return dict(capture_complete=False, bcb_admitted=False, result=signed_result,
                    completed=completed, next_action="RECONCILE_WITHOUT_RETRY", device_permission=False)
    require(completed == 4 and stable == 1, "success missing complete stable capture")
    first, second = raw[60:188], raw[188:316]
    require(first == second, "pair changed between passes")
    require(active == _active(first[:64], first[64:]), "arbiter result does not match raw bytes")
    return dict(capture_complete=True, bcb_admitted=active in (1, 2), result=0,
                active=active, pair_hex=first.hex(), device_permission=False,
                scope="raw pair validity only; plan/state/physical settlement are separate")
