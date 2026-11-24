"""Read-only R2 admission capture over an already-owned, timeout-aware reader.

The caller owns connection lifetime, native read deadlines and reset generation.
This module never connects, retries, resets, halts, writes or grants readiness.
"""
import hashlib
import math
import struct
import time

import p34_r2_vtor_policy as policy

DHCSR, VTOR = 0xE000EDF0, 0xE000ED08
IMAGE_BYTES, CHUNK = 619580, 4096
MAX_READS = (IMAGE_BYTES + CHUNK - 1) // CHUNK + 5


class CaptureError(RuntimeError):
    def __init__(self, reason, reads):
        super().__init__(reason)
        self.reads = [dict(r) for r in reads]


def capture(reader, profile, *, seconds=60, clock=time.monotonic):
    """reader(address, length, remaining_seconds) must honor each deadline.

    Full-image reads are for finite admission, not high-frequency speed polling.
    Equal endpoint VTORs do not independently establish an unchanged boot epoch.
    """
    reads = []
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 120:
        raise CaptureError("invalid capture deadline", reads)
    if (profile.get("schema") != policy.SCHEMA or profile.get("image_sha256") != policy.SHA256 or
            type(profile.get("image_bytes")) is not int or profile["image_bytes"] != IMAGE_BYTES or
            (profile.get("primary"), profile.get("runtime")) != (policy.ORIGIN, policy.RUNTIME)):
        raise CaptureError("unreviewed capture profile", reads)
    started = clock()
    previous = started
    if type(started) not in (int, float) or not math.isfinite(started):
        raise CaptureError("invalid capture clock", reads)

    def remaining():
        nonlocal previous
        now = clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < previous:
            raise CaptureError("invalid/nonmonotonic capture clock", reads)
        previous = now
        left = seconds-(now-started)
        if left <= 0:
            raise CaptureError("capture deadline exceeded", reads)
        return left

    def read(address, length):
        left = remaining()
        if len(reads) >= MAX_READS:
            raise CaptureError("capture read budget exceeded", reads)
        entry = dict(address=address, bytes=length, status="started")
        reads.append(entry)
        try:
            data = reader(address, length, left)
        except Exception as error:
            entry["status"] = "reader_failed"
            entry["error_type"] = type(error).__name__
            raise CaptureError("reader failed; no automatic retry", reads) from error
        if type(data) is not bytes or len(data) != length:
            entry["status"] = "invalid_length_or_type"
            raise CaptureError("short or non-byte memory read", reads)
        entry.update(status="completed", sha256=hashlib.sha256(data).hexdigest())
        remaining()
        return data

    def word(address):
        return struct.unpack("<I", read(address, 4))[0]

    before_core = word(DHCSR)
    if before_core & ((1 << 17) | (1 << 25)):
        raise CaptureError("halt/reset before capture", reads)
    before_vtor = word(VTOR)
    if before_vtor not in (policy.ORIGIN, policy.RUNTIME):
        raise CaptureError("unbound App VTOR before capture", reads)
    image = b"".join(read(policy.ORIGIN+off, min(CHUNK, IMAGE_BYTES-off))
                     for off in range(0, IMAGE_BYTES, CHUNK))
    table = read(before_vtor, policy.TABLE_BYTES)
    after_vtor = word(VTOR)
    after_core = word(DHCSR)
    try:
        result = policy.classify(profile, image, vtor_before=before_vtor, vtor_after=after_vtor,
                                 table=table, dhcsr=before_core | after_core, halted=False)
    except (ValueError, KeyError, TypeError) as error:
        raise CaptureError("image/vector admission rejected: " + str(error), reads) from error
    remaining()
    return dict(result=result, reads=reads, raw_image=image, raw_table=table,
                vtor_before=before_vtor, vtor_after=after_vtor,
                dhcsr_before=before_core, dhcsr_after=after_core,
                boot_generation="NOT_ESTABLISHED", native_route_validated=False,
                elapsed_seconds=previous-started)
