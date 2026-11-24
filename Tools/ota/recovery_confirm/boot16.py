"""Exact Boot first16KiB ports on an already-qualified halt. No device entry."""
from dataclasses import dataclass
import hashlib
import time

from . import flash_port as old
from .flash_remainder import ObservedSector
from .native_io import Words, guarded

START, END, WHOLE = 0x08000000, 0x08004000, 65536
UNIT = 2048
ORIGINAL_SHA = 'a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4'
CANDIDATE_SHA = '2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80'


def exact(data, size, digest):
    if type(data) is not bytes or len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('exact immutable Boot asset required')


@dataclass(frozen=True)
class Plan:
    original: bytes
    candidate: bytes

    def __post_init__(self):
        exact(self.original, WHOLE, ORIGINAL_SHA)
        exact(self.candidate, 14800, CANDIDATE_SHA)
        if self.original[14780:END-START] != b'\xff' * 1604:
            raise ValueError('original first16KiB padding differs')

    @property
    def activated(self):
        return self.candidate + b'\xff' * (END-START-len(self.candidate)) + self.original[END-START:]

    def desired(self, direction, preimage):
        if type(preimage) is not bytes or len(preimage) != WHOLE:
            raise ValueError('complete physical Boot preimage required')
        if preimage[END-START:] != self.original[END-START:]:
            raise ValueError('preserved Boot suffix differs; never repair beyond authorization')
        if direction == 'activate':
            if preimage != self.original:
                raise ValueError('activation requires exact original Boot')
            return self.activated
        if direction == 'restore':
            return self.original
        raise ValueError('unknown Boot direction')


class Sector(ObservedSector):
    """Reuse controller sequence, but not the historical App geometry/identity."""
    def __init__(self, dap, plan, preimage, index, direction, owner, emit, *,
                 seconds=300, clock=time.monotonic, sleep=time.sleep, guard=guarded):
        if type(plan) is not Plan:
            raise ValueError('exact Boot plan type required')
        desired = plan.desired(direction, preimage)
        if type(index) is not int or not 0 <= index < 8:
            raise ValueError('only eight first16KiB sectors allowed')
        self.address = START + index * UNIT
        self.key, self.status_reg, self.ctrl, self.addr = old.BANKS[0]
        offset = index * UNIT
        self.before, self.after = preimage[offset:offset+UNIT], desired[offset:offset+UNIT]
        self.bank = 1
        self.owner, self.emit, self.sleep = owner, emit, sleep
        self.expected_write = None
        reads = {old.DHCSR, old.PAUSE, old.IDCODE, old.FSIZE, *old.CLOCK, *old.CONFIG,
                 *old.PROTECTION, *range(self.address, self.address+UNIT, 4)}
        reads.update(a for _, status, ctrl, _ in old.BANKS for a in (status, ctrl))
        self.words = Words(dap, emit, reads=reads, write_allowed=self.allowed,
                           seconds=seconds, clock=clock, guard=guard)
        self.config = None
        self.used = self.done = self.erased = False
        self.error = None
        self.programmed_words = 0


def stores(plan, preimage, index, direction):
    """Independent ordered success oracle, never built from observed writes."""
    if type(plan) is not Plan or type(index) is not int or not 0 <= index < 8:
        raise ValueError('Boot write-oracle scope')
    desired = plan.desired(direction, preimage)
    address = START + index * UNIT
    key, status, ctrl, addr = old.BANKS[0]
    result = [(key, old.KEY1), (key, old.KEY2), (status, 0x34), (ctrl, 2),
              (addr, address), (ctrl, 0x42), (ctrl, 0), (ctrl, 0x80)]
    data = desired[index*UNIT:(index+1)*UNIT]
    words = [(address+i, int.from_bytes(data[i:i+4], 'little'))
             for i in range(0, UNIT, 4) if data[i:i+4] != b'\xff'*4]
    if words:
        result += [(key, old.KEY1), (key, old.KEY2), (ctrl, 1)]
        for item in words:
            result += [(status, 0x34), item]
        result += [(ctrl, 0), (ctrl, 0x80)]
    return tuple(result)
