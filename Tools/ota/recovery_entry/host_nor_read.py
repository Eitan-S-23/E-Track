"""Bounded SFDP/03h reads through fixed-address, word/no-increment FIFO access."""
import ctypes
import struct
import time

from . import host_nor as hn
from .native_probe import guarded
from .probe import require


class Port(hn.Port):
    def read_command(self, opcode, address, size):
        require(type(address) is int and type(size) is int and 0 < size <= 128 and size % 4 == 0,
                'bounded whole-word read command required')
        require((opcode == 0x5a and address in (0, 128) and size == 128) or
                (opcode == 3 and 0 <= address < address+size <= 0x1000000),
                '03h/SFDP-only command scope')
        words = (address, 0x1080003 if opcode == 0x5a else 0x1000003, size, opcode << 24)
        for i, value in enumerate(words):
            self.owner()
            target = hn.BASE+4*i
            self.emit('nor-read-command-write-attempt', address=target, value=value)
            self.apwrite(1, target)
            self.apwrite(3, value)
            self.dap._power_ready()
            self.emit('nor-read-command-write-returned', address=target, value=value)

    def fifo_words(self, size):
        require(type(size) is int and 0 < size <= 128 and size % 4 == 0, 'fixed FIFO burst scope')
        self.owner()
        require(self.read(hn.CMDSTS) == 1 and self.read(hn.FIFO) == 3, 'completed RX FIFO required')
        original = self.dap._read_reg(0, 1)
        require(original == self.dap.word_csw, 'unexpected AP word CSW')
        self.saved_csw, self.ap_csw_restored = original, False
        fixed = (original & ~0x37) | 2
        self.emit('nor-fifo-burst-attempt', address=hn.DT, bytes=size, csw=fixed)
        self.apwrite(0, fixed)
        require(self.dap._read_reg(0, 1) == fixed, 'word/no-increment CSW mismatch')
        self.apwrite(1, hn.DT)
        def burst():
            words = []
            data, dp = ctypes.c_uint32(), ctypes.c_uint32()
            for index in range(size//4):
                require(self.dap.callback_error is None, 'native callback failed')
                rc = self.dap.sdk.JLINKARM_CORESIGHT_ReadAPDPReg(3, 1, ctypes.byref(data))
                require(type(rc) is int and rc >= 0, 'FIFO word read failed/uncertain')
                rc = self.dap.sdk.JLINKARM_CORESIGHT_ReadAPDPReg(1, 0, ctypes.byref(dp))
                require(type(rc) is int and rc >= 0 and dp.value & 0xf0000000 == 0xf0000000 and
                        dp.value & 0xb2 == 0 and self.dap.callback_error is None, 'FIFO word DP/callback error')
                words.append(data.value)
                self.emit('nor-fifo-word', index=index, value=data.value)
            return struct.pack('<'+'I'*len(words), *words)
        data = guarded(burst)
        require(self.dap._read_reg(1, 1) == hn.DT, 'FIFO address incremented')
        self.restore_ap()
        self.emit('nor-fifo-burst-returned', bytes=size, data_hex=data.hex())
        return data


class Reader(hn.Status):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_commands, self.identity = 0, None

    def open(self):
        try:
            self.original = self.configuration()
            require(all(self.original[k] == v for k, v in hn.CONFIG.items()), 'unqualified QSPI baseline')
            self.call(self.port.owner)
            self.transition(hn.XIP | 7)
            self.transition(7)
            self.switched = True
            self.identity = self.identify()
            return self.identity
        except BaseException as error:
            self.error = type(error).__name__+': '+str(error)
            raise

    def identify(self):
        sr1, sr2 = self.command(5), self.command(0x35)
        require(sr1 == 0 and sr2 == 2, 'exact idle unprotected quad status required for reads')
        jedec = self.command(0x9f)
        require(jedec.hex() == 'ef4018', 'fresh Winbond identity mismatch')
        return dict(sr1=sr1, sr2=sr2, jedec=jedec.hex())

    def data(self, opcode, address, size):
        try:
            self.check()
            require(self.switched and not self.restored and self.read_commands < 36, 'read cell phase/budget')
            require(self.read(hn.CTRL) == hn.IDLE | 7 and self.read(hn.CTRL2) == 0 and
                    self.read(hn.CMDSTS) == 0 and self.read(hn.FIFO) == 1, 'unsettled read command entry')
            self.read_commands += 1
            self.call(self.port.read_command, opcode, address, size)
            self.wait(hn.CMDSTS, 1, 1)
            data = self.call(self.port.fifo_words, size)
            self.write(hn.CMDSTS, 1)
            require(self.read(hn.CMDSTS) == 0 and self.read(hn.FIFO) == 1, 'read not consumed exactly')
            return data
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise

    def finish(self):
        try:
            self.check()
            require(self.identify() == self.identity, 'NOR changed during read cell')
            current = self.configuration()
            require(all(current[k] == self.original[k] for k in hn.PASSIVE), 'passive configuration changed')
            self.transition(hn.XIP | 7)
            self.transition(hn.XIP)
            after = self.configuration()
            require(all(after[k] == self.original[k] for k in hn.CONFIG), 'read-cell restoration mismatch')
            self.call(self.port.owner)
            self.restored = True
            return after
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise


def collect(reader):
    identity = reader.open()
    sfdp = b''.join(reader.data(0x5a, a, 128) for a in (0, 128))
    started = time.monotonic()
    candidate = b''.join(reader.data(3, 0x1000+a, 128) for a in range(0, 4096, 128))
    seconds = time.monotonic()-started
    recovery = reader.data(3, 0x200000, 128)
    boundary = reader.data(3, 0x299000, 128)
    after = reader.finish()
    return dict(identity=identity, sfdp_hex=sfdp.hex(), candidate_prefix_hex=candidate.hex(),
                recovery_prefix_hex=recovery.hex(), preserved_boundary_hex=boundary.hex(),
                candidate_read_seconds=seconds, read_commands=reader.read_commands, after=after,
                nor_payload_bytes_written=0, nor_write_admitted=False)
