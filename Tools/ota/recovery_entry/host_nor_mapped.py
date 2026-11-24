"""Fresh, bypassed-cache XIP reads, without widening the existing DAP reader."""
import ctypes
import struct
import time

from . import host_nor as hn, host_nor_read as nr
from .native_probe import guarded
from .probe import require

XIP3, MAPPED = 0xa000103c, 0x90000000


class Port(nr.Port):
    def bypass(self, enabled):
        require(type(enabled) is bool, 'explicit cache bypass state required')
        self.owner()
        require(self.read(hn.CTRL) == hn.IDLE | 7 and self.read(hn.CMDSTS) == 0 and
                self.read(hn.CTRL2) == 0, 'change bypass only in settled command mode')
        old = self.read(XIP3)
        require(old & ~8 == int(not enabled), 'unexpected cache configuration')
        self.emit('nor-cache-bypass-attempt', value=int(enabled))
        self.apwrite(1, XIP3)
        self.apwrite(3, int(enabled))
        self.dap._power_ready()
        require(self.read(XIP3) & ~8 == int(enabled), 'cache bypass readback mismatch')
        self.emit('nor-cache-bypass-returned', value=int(enabled))

    def mapped(self, address, size):
        require(type(address) is int and type(size) is int and address % 4 == size % 4 == 0 and
                0 < size <= 1024 and 0 <= address < address+size <= 0x1000000 and
                address//1024 == (address+size-1)//1024, 'mapped NOR/TAR boundary scope')
        self.owner()
        require(self.read(hn.CTRL) == hn.XIP | hn.IDLE | 7 and self.read(hn.CTRL2) == 0 and
                self.read(XIP3) & ~8 == 1, 'fresh bypassed-cache XIP /12 required')
        require(self.dap._read_reg(0, 1) == self.dap.word_csw, 'mapped word/increment CSW mismatch')
        self.apwrite(1, MAPPED+address)
        self.emit('nor-mapped-read-attempt', address=address, bytes=size)
        def burst():
            data, values = ctypes.c_uint32(), []
            for _ in range(size//4):
                require(self.dap.callback_error is None, 'mapped SDK callback failed')
                rc = self.dap.sdk.JLINKARM_CORESIGHT_ReadAPDPReg(3, 1, ctypes.byref(data))
                require(type(rc) is int and rc >= 0, 'mapped native read failed')
                values.append(data.value)
            return struct.pack('<'+'I'*len(values), *values)
        data = guarded(burst)
        # Non-consuming memory reads may check the DP at the chunk boundary.
        # Reject the entire chunk before handing any bytes to a hash/archive.
        self.dap._power_ready()
        self.emit('nor-mapped-read-returned', address=address, data_hex=data.hex())
        return data


class Reader(nr.Reader):
    def configuration(self):
        values = super().configuration()
        values['qspi_xip3_raw'] = values['qspi_xip3']
        # CSTS is read-only cache-valid state, not a configurable restore bit.
        values['qspi_xip3'] &= ~8
        return values


def collect(reader):
    identity = reader.open()
    reader.call(reader.port.bypass, True)
    reader.transition(hn.XIP | 7)
    started = time.monotonic()
    candidate = b''.join(reader.call(reader.port.mapped, 0x1000+a, 1024) for a in range(0, 4096, 1024))
    seconds = time.monotonic()-started
    recovery = reader.call(reader.port.mapped, 0x200000, 128)
    boundary = reader.call(reader.port.mapped, 0x299000, 128)
    reader.transition(7)
    reader.call(reader.port.bypass, False)
    after = reader.finish()
    return dict(identity=identity, candidate_prefix_hex=candidate.hex(), recovery_prefix_hex=recovery.hex(),
                preserved_boundary_hex=boundary.hex(), candidate_read_seconds=seconds, after=after,
                nor_payload_bytes_written=0, nor_write_admitted=False, cache_bypassed_during_read=True)
