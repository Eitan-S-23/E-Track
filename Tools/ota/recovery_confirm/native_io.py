"""Bounded AP word I/O for injected, already-owned connections. No connect/reset."""
import ctypes
import math
import struct
import time

from recovery_entry.native_probe import guarded


class Budget:
    def __init__(self, seconds, clock=time.monotonic):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 14400:
            raise ValueError('finite recovery-port budget required')
        self.clock = clock
        self.previous = clock()
        if type(self.previous) not in (int, float) or not math.isfinite(self.previous):
            raise ValueError('invalid initial clock')
        self.end = self.previous + seconds
        self.failed = False

    def now(self):
        if self.failed:
            raise ValueError('clock failure latched')
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now) or not self.previous <= now < self.end:
            self.failed = True
            raise ValueError('recovery-port clock/deadline exhausted')
        self.previous = now
        return now

    def left(self):
        return self.end-self.now()


class Words:
    def __init__(self, dap, emit, *, reads, write_allowed, seconds, clock=time.monotonic, guard=guarded):
        self.dap, self.emit, self.reads, self.write_allowed = dap, emit, frozenset(reads), write_allowed
        self.budget, self.guard = Budget(seconds, clock), guard
        self.error = None
        self.writes = self.read_count = 0

    def check(self):
        if self.error is not None or not self.dap.ready or self.dap.callback_error is not None:
            raise ValueError('native port failed/unowned')
        return self.budget.left()

    def call(self, name, *args):
        result = self.guard(getattr(self.dap.sdk, name), *args, seconds=min(5, self.check()))
        self.check()
        if type(result) is not int or result < 0:
            raise OSError('native AP operation returned failure')
        return result

    def reg(self, index, ap):
        data = ctypes.c_uint32()
        self.call('JLINKARM_CORESIGHT_ReadAPDPReg', index, ap, ctypes.byref(data))
        return data.value

    def status(self):
        dp = self.reg(1, 0)
        if dp & 0xf0000000 != 0xf0000000 or dp & 0xb2:
            raise OSError('DP power/sticky error; no error clear')

    def access(self, address, value=None):
        try:
            self.check()
            if type(address) is not int or address % 4:
                raise ValueError('aligned word address required')
            if value is None:
                if address not in self.reads:
                    raise ValueError('read outside exact port scope')
            elif type(value) is not int or not 0 <= value <= 0xffffffff or not self.write_allowed(address, value):
                raise ValueError('write outside exact port scope')
            csw = self.reg(0, 1)
            if csw != self.dap.word_csw or csw & 0x37 != 0x12:
                raise OSError('AP word/increment format changed')
            self.status()
            self.call('JLINKARM_CORESIGHT_WriteAPDPReg', 1, 1, address)
            if value is None:
                result = self.reg(3, 1)
                self.status()
                self.read_count += 1
                self.emit('recovery-word-read', address=address, value=result)
            else:
                self.emit('recovery-word-write-attempt', address=address, value=value)
                self.check()
                self.writes += 1
                self.call('JLINKARM_CORESIGHT_WriteAPDPReg', 3, 1, value)
                self.status()
                self.emit('recovery-word-write-returned', address=address, value=value)
                result = None
            self.check()
            return result
        except BaseException as error:
            if self.error is None:
                self.error = type(error).__name__+': '+str(error)
            raise

    def read32(self, address):
        return self.access(address)

    def write32(self, address, value):
        return self.access(address, value)

    def read_bytes(self, address, size):
        try:
            self.check()
            if type(address) is not int or type(size) is not int or address % 4 or size % 4 or not 0 < size <= 1024:
                raise ValueError('bounded aligned read chunk required')
            if address//1024 != (address+size-1)//1024 or any(a not in self.reads for a in range(address,address+size,4)):
                raise ValueError('chunk outside read scope/TAR boundary')
            if self.reg(0,1) != self.dap.word_csw or self.dap.word_csw & 0x37 != 0x12:
                raise OSError('AP format changed')
            self.status()
            self.call('JLINKARM_CORESIGHT_WriteAPDPReg',1,1,address)
            self.emit('recovery-chunk-read-attempt',address=address,bytes=size)
            self.check()
            def burst():
                values, word = [], ctypes.c_uint32()
                for _ in range(size//4):
                    self.check()
                    rc = self.dap.sdk.JLINKARM_CORESIGHT_ReadAPDPReg(3,1,ctypes.byref(word))
                    if type(rc) is not int or rc < 0:
                        raise OSError('native burst returned failure')
                    values.append(word.value)
                return struct.pack('<'+'I'*len(values),*values)
            raw = self.guard(burst,seconds=min(5,self.check()))
            self.status()
            self.read_count += size//4
            self.emit('recovery-chunk-read-returned',address=address,data_hex=raw.hex())
            self.check()
            return raw
        except BaseException as error:
            if self.error is None:
                self.error = type(error).__name__+': '+str(error)
            raise
