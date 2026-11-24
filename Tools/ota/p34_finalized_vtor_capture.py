"""Host-only exact finalized R2 capture over a caller-owned reader and epoch latch.

No connection, native driver, reset, retry or operational-readiness authority is
provided. In particular, the old 30275-only DAP reader is not a qualified port.
"""
import hashlib
import math
import struct
import time

import p34_finalized_vtor as policy

DHCSR, VTOR = 0xe000edf0, 0xe000ed08
IMAGE_BYTES, CHUNK = 619580, 4096
MAX_READS = (IMAGE_BYTES+CHUNK-1)//CHUNK+5
PLANNED = {policy.IDENTITIES['r2-a.bin']: 30276, policy.IDENTITIES['r2-b.bin']: 30277}


class CaptureError(RuntimeError):
    def __init__(self, reason, reads, raw_reads):
        super().__init__(reason)
        self.reads = [dict(item) for item in reads]
        self.raw_reads = tuple(raw_reads)


def capture(reader, owner, *, image_sha256, version, connection_generation,
            boot_generation, seconds=180, clock=time.monotonic):
    """Read one planned image, never merely either admissible R2 image.

    reader(address, size, remaining_seconds) must return exact bytes and honor
    its own native timeout. owner() returns owned=True, the caller's connection
    and boot generations, and a persistent reset_seen latch. The caller must
    retain any consumed hardware reset indication. Matching VTOR endpoints do
    not supply that guarantee. A future finite native worker must enforce both
    callbacks' lifetimes; these host checks cannot interrupt a stuck callback.
    """
    reads, raw_reads = [], []
    def fail(reason): raise CaptureError(reason, reads, raw_reads)
    if (type(image_sha256) is not str or type(version) is not int or PLANNED.get(image_sha256) != version or
            type(connection_generation) is not str or not connection_generation or
            type(boot_generation) is not int or boot_generation < 0):
        fail('unbound planned image or ownership generation')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 300:
        fail('invalid finite capture deadline')
    started = previous = clock()
    if type(started) not in (int, float) or not math.isfinite(started): fail('invalid initial clock')

    def remaining():
        nonlocal previous
        now = clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < previous:
            fail('nonmonotonic/invalid clock')
        previous = now
        left = seconds-(now-started)
        if left <= 0: fail('capture deadline exceeded')
        return left

    def ownership():
        remaining()
        try: state = owner()
        except Exception as error:
            fail('owner callback failed: '+type(error).__name__)
        if (type(state) is not dict or state.get('owned') is not True or
                state.get('connection_generation') != connection_generation or
                type(state.get('boot_generation')) is not int or state['boot_generation'] != boot_generation or
                state.get('reset_seen') is not False):
            fail('owner/generation/reset latch changed')
        remaining()

    def read(address, size):
        ownership()
        if len(reads) >= MAX_READS: fail('capture read budget exceeded')
        entry = dict(address=address, bytes=size, status='started')
        reads.append(entry)
        try: data = reader(address, size, remaining())
        except Exception as error:
            entry.update(status='reader_failed', error_type=type(error).__name__)
            fail('reader failed; no automatic retry')
        if type(data) is not bytes or len(data) != size:
            entry['status'] = 'invalid_length_or_type'
            fail('short/non-byte read')
        raw_reads.append(data)
        entry.update(status='completed', sha256=hashlib.sha256(data).hexdigest())
        ownership()
        return data

    def word(address): return struct.unpack('<I', read(address, 4))[0]
    before_core = word(DHCSR)
    if before_core & 0x020a0000: fail('halt/reset/lockup before capture')
    before_vtor = word(VTOR)
    if before_vtor not in (policy.ORIGIN, policy.RUNTIME): fail('unbound initial VTOR')
    image = b''.join(read(policy.ORIGIN+offset, min(CHUNK, IMAGE_BYTES-offset))
                     for offset in range(0, IMAGE_BYTES, CHUNK))
    if hashlib.sha256(image).hexdigest() != image_sha256: fail('planned image digest mismatch')
    table = read(before_vtor, policy.TABLE)
    after_vtor, after_core = word(VTOR), word(DHCSR)
    if after_core & 0x020a0000: fail('halt/reset/lockup after capture')
    try:
        classified = policy.classify(image, before=before_vtor, after=after_vtor,
                                     table=table, dhcsr=before_core | after_core, halted=False)
    except (ValueError, KeyError, TypeError) as error:
        fail('finalized image/vector admission failed: '+str(error))
    ownership()
    return dict(schema='p34-finalized-vtor-capture/v1', result=classified, image_sha256=image_sha256,
                version=version, reads=reads, raw_reads=tuple(raw_reads), raw_image=image, raw_table=table,
                connection_generation=connection_generation, boot_generation=boot_generation,
                caller_owner_continuity_checked=True, physical_reset_continuity='CALLER_PROVIDED_NOT_INDEPENDENTLY_PROVEN',
                native_route_validated=False, operational_readiness='NOT_ESTABLISHED', elapsed_seconds=previous-started)
