"""Finite passive state window on an existing owner; no reconnect or mutation."""
import math
import time

from .native_io import Words, guarded
from recovery_entry.state_probe import STATE_WORDS, sample


class Window:
    def __init__(self, dap, emit, owner, remaining, *, seconds=30, clock=time.monotonic, guard=None):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 60:
            raise ValueError('finite short state window required')
        left = remaining()
        if type(left) not in (int, float) or not math.isfinite(left) or left <= 0:
            raise ValueError('live coordinator allowance required')
        self.emit, self.owner, self.remaining = emit, owner, remaining
        self.previous_left = left
        self.error = None
        self.used = False
        self.native_guard = guarded if guard is None else guard
        self.words = Words(dap, emit, reads=STATE_WORDS, write_allowed=lambda a,v:False,
                           seconds=min(seconds, left), clock=clock, guard=self.bounded_call)

    def check(self):
        if self.error is not None:
            raise ValueError('state window failed')
        self.words.check()
        now = self.words.budget.now()
        left = self.remaining()
        if (type(left) not in (int, float) or not math.isfinite(left) or
                not 0 < left <= self.previous_left or self.owner() is not True):
            raise ValueError('state owner/global deadline changed')
        self.previous_left = left
        self.words.budget.end = min(self.words.budget.end, now+left)
        return self.words.check()

    def bounded_call(self, function, *args, seconds):
        limit = min(seconds, self.check())
        result = self.native_guard(function, *args, seconds=limit)
        self.check()
        return result

    def _call(self, name, address, size):
        try:
            self.check()
            if name != 'read' or type(address) is not int or address not in STATE_WORDS or type(size) is not int or size != 4:
                raise ValueError('only exact passive state word reads are available')
            value = self.words.read32(address)
            self.check()
            return value.to_bytes(4, 'little')
        except BaseException as error:
            if self.error is None:
                self.error = type(error).__name__+': '+str(error)
            raise

    def capture(self):
        try:
            if self.used:
                raise ValueError('state window capture cannot replay')
            self.used = True
            self.check()
            result = sample(self)
            self.check()
            return result
        except BaseException as error:
            if self.error is None:
                self.error = type(error).__name__+': '+str(error)
            raise
