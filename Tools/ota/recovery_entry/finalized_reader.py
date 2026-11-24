"""Separate bounded finalized-App AP reader; never opens or resumes a target."""
import ctypes
import math
import struct
import time

from .native_probe import guarded
from .probe import require

DHCSR, VTOR = 0xe000edf0, 0xe000ed08
ORIGIN, LENGTH = 0x08010000, 619580


class Reader:
    def __init__(self, dap, emit, lease, *, connection_generation, boot_generation,
                 seconds=180, clock=time.monotonic, guard=guarded):
        require(type(connection_generation) is str and bool(connection_generation) and
                type(boot_generation) is int and boot_generation >= 0, 'fixed owner generations required')
        require(type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 300,
                'finite reader lifetime required')
        self.dap, self.emit, self.lease = dap, emit, lease
        self.connection_generation, self.boot_generation = connection_generation, boot_generation
        self.clock, self.guard = clock, guard
        self.started = self.previous = clock()
        require(type(self.started) in (int, float) and math.isfinite(self.started), 'invalid clock')
        self.deadline = self.started+seconds
        self.error, self.reset_seen = None, False
        self.api_reads = self.owner_samples = self.target_chunks = self.target_words = 0

    def _time(self, deadline):
        now = self.clock()
        require(type(now) in (int, float) and math.isfinite(now) and now >= self.previous and
                now < min(self.deadline, deadline), 'reader clock/deadline exhausted')
        self.previous = now
        return min(self.deadline, deadline)-now

    def _check(self, deadline):
        require(self.error is None and not self.reset_seen and self.dap.ready, 'reader failed/reset/unowned')
        self._time(deadline)
        state = self.lease()
        require(type(state) is dict, 'owner state missing')
        self.reset_seen |= state.get('reset_seen') is True
        require(state.get('owned') is True and state.get('reset_seen') is False and
                state.get('connection_generation') == self.connection_generation and
                type(state.get('boot_generation')) is int and state['boot_generation'] == self.boot_generation,
                'connection/boot generation or reset latch changed')
        require(self.dap.callback_error is None, 'native callback evidence error')
        return self._time(deadline)

    def _invoke(self, name, args, deadline):
        left = self._check(deadline)
        value = self.guard(getattr(self.dap.sdk, name), *args, seconds=min(5, left))
        require(type(value) is int and value >= 0, 'native read/setup return failed')
        self._check(deadline)
        return value

    def _reg(self, index, ap, deadline):
        value = ctypes.c_uint32()
        self._invoke('JLINKARM_CORESIGHT_ReadAPDPReg', (index, ap, ctypes.byref(value)), deadline)
        return value.value

    def _chunk(self, address, size, deadline):
        self._check(deadline)
        require(self._reg(0, 1, deadline) == self.dap.word_csw and self.dap.word_csw & 0x37 == 0x12,
                'word/increment AP format changed')
        self._invoke('JLINKARM_CORESIGHT_WriteAPDPReg', (1, 1, address), deadline)
        self.emit('finalized-read-attempt', address=address, bytes=size)
        def burst():
            word, values = ctypes.c_uint32(), []
            for _ in range(size//4):
                self._check(deadline)
                rc = self.dap.sdk.JLINKARM_CORESIGHT_ReadAPDPReg(3, 1, ctypes.byref(word))
                require(type(rc) is int and rc >= 0, 'native data read failed')
                require(self.dap.callback_error is None, 'native data callback failed')
                values.append(word.value)
            return struct.pack('<'+'I'*len(values), *values)
        raw = self.guard(burst, seconds=min(5, self._check(deadline)))
        self._check(deadline)
        dp = self._reg(1, 0, deadline)
        require(dp & 0xf0000000 == 0xf0000000 and dp & 0xb2 == 0, 'DP error; whole chunk rejected')
        self.target_chunks += 1; self.target_words += size//4
        if address == DHCSR: self.reset_seen |= bool(int.from_bytes(raw, 'little') & 0x02000000)
        self.emit('finalized-read-returned', address=address, data_hex=raw.hex())
        self._time(deadline)
        return raw

    def read(self, address, size, remaining_seconds):
        try:
            require(type(address) is int and type(size) is int and address % 4 == size % 4 == 0 and
                    0 < size <= 4096 and ((address in (DHCSR, VTOR) and size == 4) or
                    ORIGIN <= address < address+size <= ORIGIN+LENGTH), 'finalized read outside fixed scope')
            require(type(remaining_seconds) in (int, float) and math.isfinite(remaining_seconds) and
                    0 < remaining_seconds <= 300, 'invalid caller deadline')
            self._time(self.deadline)
            deadline = min(self.deadline, self.previous+remaining_seconds)
            self._check(deadline)
            self.api_reads += 1
            data = bytearray()
            while len(data) < size:
                a = address+len(data); take = min(size-len(data), 1024-a % 1024)
                data.extend(self._chunk(a, take, deadline))
            self._time(deadline)
            return bytes(data)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise

    def owner(self):
        try:
            self._check(self.deadline)
            raw = self._chunk(DHCSR, 4, self.deadline)
            require(int.from_bytes(raw, 'little') & 0x000a0000 == 0, 'halt/lockup during owner observation')
            self.owner_samples += 1
            return dict(owned=True, connection_generation=self.connection_generation,
                        boot_generation=self.boot_generation, reset_seen=self.reset_seen)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise
