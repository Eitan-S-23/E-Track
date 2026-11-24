"""Recovery-only controller transaction; no reset, unlock or status-write opcode."""
import ctypes
import hashlib
import struct
import time
import zlib

from . import host_nor as hn, host_nor_mapped as mapped, host_writer as hw
from .nor_profile import pinned as profile
from .native_probe import guarded
from .probe import require


class Port(mapped.Port):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.intent, self.intent_phase, self.tx_remaining = None, 0, 0

    def intent_for(self, kind, address, data):
        require(self.intent is None and kind in ('erase', 'program'), 'mutation intent already active')
        size = 4096 if kind == 'erase' else len(data)
        hw.scope(address, size)
        require((kind == 'erase' and address % 4096 == 0 and data == b'') or
                (kind == 'program' and isinstance(data, bytes) and 0 < size <= 256 and
                 address % 4 == size % 4 == 0 and address % 256+size <= 256), 'mutation alignment/size')
        self.intent, self.intent_phase = (kind, address, data), 0

    def mutation_command(self, opcode):
        require(self.intent is not None, 'no admitted address before WREN')
        kind, address, data = self.intent
        hw.scope(address, 4096 if kind == 'erase' else len(data))
        if opcode == 6:
            require(self.intent_phase == 0, 'WREN replay prohibited')
            words = (0, 0x1000000, 0, 0x06000002)
            self.intent_phase = 1
        else:
            require(self.intent_phase == 1 and opcode == (0x20 if kind == 'erase' else 2), 'wrong mutation command/order')
            words = (address, 0x1000003, 0 if kind == 'erase' else len(data), (opcode << 24) | 2)
            self.intent_phase = 2
            self.tx_remaining = len(data)
        for i, value in enumerate(words):
            self.owner()
            self.emit('nor-mutation-command-attempt', address=hn.BASE+4*i, value=value)
            self.apwrite(1, hn.BASE+4*i); self.apwrite(3, value)
            self.dap._power_ready()
            self.emit('nor-mutation-command-returned', address=hn.BASE+4*i, value=value)

    def tx(self, data):
        require(self.intent is not None and self.intent[0] == 'program' and self.intent_phase == 2 and
                isinstance(data, bytes) and 0 < len(data) <= 128 and len(data) % 4 == 0 and
                len(data) <= self.tx_remaining, 'bounded pending program FIFO only')
        source = self.intent[2]; offset = len(source)-self.tx_remaining
        require(data == source[offset:offset+len(data)], 'TX data differs from admitted page')
        self.owner()
        require(self.read(hn.FIFO) & 1 and self.read(hn.CMDSTS) == 0, 'TX not ready or command completed early')
        original = self.dap._read_reg(0, 1)
        require(original == self.dap.word_csw, 'TX AP format mismatch')
        self.saved_csw, self.ap_csw_restored = original, False
        fixed = (original & ~0x37) | 2
        self.apwrite(0, fixed)
        require(self.dap._read_reg(0, 1) == fixed, 'TX word/no-increment format mismatch')
        self.apwrite(1, hn.DT)
        self.emit('nor-tx-attempt', offset=offset, bytes=len(data), data_hex=data.hex(), csw=fixed)
        def burst():
            status = ctypes.c_uint32()
            for i in range(0, len(data), 4):
                require(self.dap.callback_error is None, 'TX callback failed')
                value = int.from_bytes(data[i:i+4], 'little')
                rc = self.dap.sdk.JLINKARM_CORESIGHT_WriteAPDPReg(3, 1, value)
                require(type(rc) is int and rc >= 0, 'TX word delivery uncertain')
                rc = self.dap.sdk.JLINKARM_CORESIGHT_ReadAPDPReg(1, 0, ctypes.byref(status))
                require(type(rc) is int and rc >= 0 and status.value & 0xf0000000 == 0xf0000000 and
                        status.value & 0xb2 == 0 and self.dap.callback_error is None, 'TX word DP/callback error')
                self.emit('nor-tx-word', offset=offset+i, value=value)
        guarded(burst)
        require(self.dap._read_reg(1, 1) == hn.DT, 'TX FIFO address incremented')
        self.restore_ap()
        self.tx_remaining -= len(data)
        self.emit('nor-tx-returned', bytes=len(data), remaining=self.tx_remaining)

    def internal(self, address, size):
        require(type(address) is int and type(size) is int and address % 4 == size % 4 == 0 and
                0 < size <= 1024 and address//1024 == (address+size-1)//1024 and
                (0x08000000 <= address < address+size <= 0x08010000 or
                 0x08010000 <= address < address+size <= 0x08010000+617588), 'original Boot/App read range')
        self.owner()
        require(self.dap._read_reg(0, 1) == self.dap.word_csw, 'internal read AP format')
        self.apwrite(1, address)
        def burst():
            word, values = ctypes.c_uint32(), []
            for _ in range(size//4):
                require(self.dap.callback_error is None, 'internal read callback failed')
                rc = self.dap.sdk.JLINKARM_CORESIGHT_ReadAPDPReg(3, 1, ctypes.byref(word))
                require(type(rc) is int and rc >= 0, 'internal flash read failed')
                values.append(word.value)
            return struct.pack('<'+'I'*len(values), *values)
        data = guarded(burst); self.dap._power_ready()
        self.emit('nor-internal-read-returned', address=address, data_hex=data.hex())
        return data


class Gate(hn.Status):
    def __init__(self, port, emit, *, clock=time.monotonic):
        # Independent long-cell lifetime, not a change to historical 60s readers.
        self.port, self.emit, self.clock = port, emit, clock
        self.start, self.seconds, self.error = clock(), 13800, None
        self.original, self.switched, self.restored, self.commands = None, False, False, 0

    def configuration(self):
        values = super().configuration()
        values['qspi_xip3_raw'] = values['qspi_xip3']
        values['qspi_xip3'] &= ~8
        return values


class Device:
    def __init__(self, port, emit, source, *, clock=time.monotonic):
        require(isinstance(source, bytes) and len(source) == hw.LENGTH and
                hashlib.sha256(source).hexdigest() == hw.PINNED, 'pinned recovery source required')
        self.port, self.emit, self.source, self.clock = port, emit, source, clock
        self.gate = Gate(port, emit, clock=clock)
        self.mode, self.profile, self.armed, self.index = None, None, False, 0
        self.actions = [('erase', hw.LOW, b'')]
        for offset in range(0, len(source), 4096):
            self.actions.append(('erase', hw.LOW+4096+offset, b''))
            block = source[offset:offset+4096]
            for page in range(0, len(block), 256):
                self.actions.append(('program', hw.LOW+4096+offset+page, block[page:page+256]))
        metadata = b'ETSL\x04\xff\xff\xff'+struct.pack('<III', hw.LENGTH, zlib.crc32(source), 30276)+source[0x428:0x430]
        require(len(metadata) == 28, 'metadata shape')
        self.actions.extend([('program', hw.LOW, metadata), ('program', hw.LOW+28, b'TMOC')])

    def check(self): self.gate.check()

    def _entry(self):
        self.check()
        require(self.gate.read(hn.CTRL) == hn.IDLE | 7 and self.gate.read(hn.CTRL2) == 0 and
                self.gate.read(hn.CMDSTS) == 0 and self.gate.read(hn.FIFO) == 1, 'unsettled command entry')

    def command_mode(self):
        self.check()
        if self.mode != 'command':
            require(self.mode == 'mapped', 'controller not initialized')
            self.gate.transition(7); self.mode = 'command'

    def complete(self):
        self.gate.wait(hn.CMDSTS, 1, 1)
        self.gate.write(hn.CMDSTS, 1)
        require(self.gate.read(hn.CMDSTS) == 0, 'completion acknowledgement failed')

    def status(self, opcode=5):
        require(opcode in (5, 0x35), 'status read only')
        self.command_mode(); self._entry()
        self.gate.commands += 1
        require(self.gate.commands <= 100000, 'status command budget')
        for i, value in enumerate((0, 0x1000000, 0, (opcode << 24) | 0xc)):
            self.gate.write(hn.BASE+4*i, value)
        self.gate.wait(hn.CMDSTS, 1, 1)
        value = self.gate.read(hn.RSTS) & 255
        self.gate.write(hn.CMDSTS, 1)
        require(self.gate.read(hn.CMDSTS) == 0, 'status completion uncleared')
        return value

    def identity(self):
        require(self.status() == 0 and self.status(0x35) == 2, 'NOR status/protection changed')
        self._entry()
        for i, value in enumerate((0, 0x1000000, 3, 0x9f000000)):
            self.gate.write(hn.BASE+4*i, value)
        self.gate.wait(hn.CMDSTS, 1, 1)
        identity = self.gate.call(self.port.rdid_bytes)
        self.gate.write(hn.CMDSTS, 1)
        require(identity == bytes.fromhex('ef4018'), 'physical identity changed')

    def open(self):
        self.gate.original = self.gate.configuration()
        require(all(self.gate.original[k] == v for k, v in hn.CONFIG.items()), 'original QSPI profile changed')
        self.gate.transition(hn.XIP | 7); self.gate.transition(7)
        self.mode, self.gate.switched = 'command', True
        self.identity()
        raw = b''
        for address in (0, 128):
            self._entry()
            self.gate.call(self.port.read_command, 0x5a, address, 128)
            self.gate.wait(hn.CMDSTS, 1, 1)
            raw += self.gate.call(self.port.fifo_words, 128)
            self.gate.write(hn.CMDSTS, 1)
        self.profile = profile(raw)
        self.gate.call(self.port.bypass, True)
        return self.profile

    def read(self, address, size):
        self.check()
        require(type(address) is int and type(size) is int and address % 4 == size % 4 == 0 and
                0 < size <= 4096 and 0 <= address < address+size <= 0x500000, 'named NOR read scope')
        if self.mode != 'mapped':
            require(self.mode == 'command' and self.port.intent is None, 'unfinished mutation before mapped read')
            self.gate.transition(hn.XIP | 7); self.mode = 'mapped'
        data = bytearray()
        while len(data) < size:
            start = address+len(data); take = min(size-len(data), 1024-start % 1024)
            data.extend(self.gate.call(self.port.mapped, start, take))
        return bytes(data)

    def arm(self, receipt):
        require(not self.armed and self.profile is not None and self.index == 0 and
                receipt.get('result') == 'RECOVERY_PREIMAGES_DURABLE' and
                receipt.get('recovery_range') == [hw.LOW, hw.HIGH] and receipt.get('bcb_pair_sha256') ==
                '72b8eb65d7a99b3c0a085b225dde0b6d7d680015b874366a97f1c36cbb89e049' and
                receipt.get('source_sha256') == hw.PINNED, 'durable preservation/BCB/source receipt required')
        self.identity()
        self.armed = True

    def mutate(self, kind, address, data):
        try:
            self.check()
            require(self.armed and self.index < len(self.actions) and
                    self.actions[self.index] == (kind, address, data), 'fixed recovery transaction order/data violated')
            self.command_mode()
            require(self.status() == 0 and self.status(0x35) == 2, 'NOR not ready before WREN')
            self.port.intent_for(kind, address, data)
            self.index += 1
            self.emit('nor-mutation-start', index=self.index, kind=kind, address=address, bytes=len(data))
            self._entry(); self.gate.call(self.port.mutation_command, 6); self.complete()
            require(self.status() == 2, 'WREN did not establish exact WEL')
            self._entry(); self.gate.call(self.port.mutation_command, 0x20 if kind == 'erase' else 2)
            if kind == 'program':
                for offset in range(0, len(data), 128): self.gate.call(self.port.tx, data[offset:offset+128])
            self.complete()
            started = self.clock(); limit = 3.0 if kind == 'erase' else 0.5
            while True:
                require(0 <= self.clock()-started < limit, 'NOR WIP settlement deadline')
                value = self.status()
                require(value & ~3 == 0, 'NOR status/protection drift during WIP')
                if not value & 1:
                    require(value == 0, 'ignored/protected mutation left WEL set')
                    break
            require(self.clock()-started < limit, 'NOR settlement returned after deadline')
            self.port.intent = None
            self.emit('nor-mutation-settled', index=self.index, elapsed_seconds=self.clock()-started)
            return 0
        except BaseException as error:
            if self.gate.error is None: self.gate.error = type(error).__name__+': '+str(error)
            raise

    def erase(self, address): return self.mutate('erase', address, b'')
    def program(self, address, data): return self.mutate('program', address, data)

    def finish(self):
        self.check()
        require(self.index == len(self.actions), 'incomplete recovery transaction cannot restore automatically')
        self.identity()
        self.gate.call(self.port.bypass, False)
        current = self.gate.configuration()
        require(all(current[k] == self.gate.original[k] for k in hn.PASSIVE), 'passive configuration changed')
        self.gate.transition(hn.XIP | 7); self.gate.transition(hn.XIP)
        after = self.gate.configuration()
        require(all(after[k] == self.gate.original[k] for k in hn.CONFIG), 'final configuration mismatch')
        self.mode, self.gate.restored = 'original', True
        return after
