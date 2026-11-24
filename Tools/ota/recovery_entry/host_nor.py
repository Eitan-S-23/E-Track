"""Halted-host QSPI status qualification. No NOR mutation opcode exists here."""
import time

from .probe import require
from .owner_probe import QSPI_REGS

BASE, CTRL, FIFO, CTRL2, CMDSTS, RSTS, DT = (
    0xa0001000, 0xa0001010, 0xa0001018, 0xa0001020,
    0xa0001024, 0xa0001028, 0xa0001100)
XIP, IDLE, ABORT = 0x100000, 0x80, 0x100
CLOCK = dict(crm_ctrl=0x3008e83, crm_pllcfg=0x11201,
             crm_cfg=0x900a, crm_misc1=0x7000, crm_misc2=0xd)
CONFIG = dict(qspi_ctrl=0x100080, qspi_ctrl2=0, qspi_cmdsts=0,
              qspi_fsize=0xf0000000, qspi_xip0=0x6b208,
              qspi_xip1=0x32200, qspi_xip2=2132803359,
              qspi_xip3=0, qspi_ctrl3=0x138, qspi_revision=66816,
              crm_ahben3=0x8002)
PASSIVE = tuple(k for k in CONFIG if k not in ('qspi_ctrl', 'qspi_cmdsts'))


def qualify_masters(sample):
    """AT32F435 AHB masters: halted M4, DMA1/2, EDMA; no EMAC on F435."""
    raw = sample['raw']
    require(all(raw[k] == v for k, v in CLOCK.items()), 'unqualified clock profile')
    names = [f'dma{unit}_{i}' for unit in (1, 2) for i in range(1, 8)]
    names += [f'edma_{i}' for i in range(1, 9)]
    enabled = {k for k in names if raw[k] & 1}
    require(enabled == {'dma1_3', 'dma2_4'} and raw['dma1_3'] == 0x1093 and
            raw['dma2_4'] == 0x2a81, 'unqualified DMA control/loop/M2M ownership')
    require(raw['display_dma_count'] == raw['sd_dma_count'] == 0 and
            raw['display_dma_peripheral'] == 0x4001300c and
            raw['sd_dma_peripheral'] == 0x50061080 and
            raw['display_dma_memory'] == 536888800 and
            raw['sd_dma_memory'] == 537210384, 'DMA endpoint/count changed')
    require(raw['debug_apb1_frz'] == 0x1000 and raw['qspi_ctrl2'] == 0 and
            sample['control_extra']['wwdt_ctrl'] == 0, 'WDT pause/QSPI DMA changed')
    require(sample['ble_state'] == sample['ble_isr_active'] == sample['overlay_owner'] == 0,
            'NOR software owner active')


class Port:
    """Dedicated MMIO capability. The existing read-only DAP is not widened."""
    def __init__(self, control, emit):
        self.control, self.dap, self.emit = control, control.dap, emit
        self.byte_csw = None
        self.saved_csw = None
        self.ap_csw_restored = False

    def owner(self):
        s = self.control.status()
        require(s['halted'] and not s['reset_sticky'] and not s['lockup'], 'NOR lost retained halt')
        require(self.control._read32(0xe0042008) == 0x1000, 'NOR lost WDT pause')

    def apwrite(self, index, value):
        rc = self.dap._call('JLINKARM_CORESIGHT_WriteAPDPReg', index, 1, value)
        require(type(rc) is int and rc >= 0, 'NOR AP write failed/uncertain')

    def read(self, address):
        require(address in QSPI_REGS.values() and self.dap.ready, 'NOR MMIO read scope')
        self.apwrite(1, address)
        value = self.dap._read_reg(3, 1)
        self.dap._power_ready()
        self.emit('nor-mmio-read', address=address, value=value)
        return value

    def write(self, address, value):
        require(type(value) is int and 0 <= value <= 0xffffffff and self.dap.ready,
                'NOR MMIO integer scope')
        require((address == CTRL and value in (0, 7, XIP, XIP | 7)) or
                (address == CMDSTS and value == 1) or
                (address == BASE and value == 0) or
                (address == BASE+4 and value in (0x1000000, 0x1000003)) or
                (address == BASE+8 and value in (0, 3)) or
                (address == BASE+12 and value in (0x0500000c, 0x3500000c, 0x9f000000)),
                'NOR status-only MMIO write scope')
        self.owner()
        self.emit('nor-mmio-write-attempt', address=address, value=value)
        self.apwrite(1, address)
        self.apwrite(3, value)
        self.dap._power_ready()
        self.emit('nor-mmio-write-returned', address=address, value=value)

    def rdid_bytes(self):
        self.owner()
        require(self.read(FIFO) & 2, 'RDID RX FIFO not ready')
        original = self.dap._read_reg(0, 1)
        require(original == self.dap.word_csw, 'unexpected AP CSW before byte drain')
        self.saved_csw = original
        self.ap_csw_restored = False
        self.byte_csw = original & ~0x37  # Byte, no increment, always DT lane zero.
        self.emit('nor-fifo-read-attempt', address=DT, bytes=3, csw=self.byte_csw)
        self.apwrite(0, self.byte_csw)
        require(self.dap._read_reg(0, 1) == self.byte_csw, 'byte/no-increment CSW mismatch')
        self.apwrite(1, DT)
        values = bytearray()
        for _ in range(3):
            values.append(self.dap._read_reg(3, 1) & 0xff)
            # A sticky bus error can accompany a nominally successful SDK call.
            # Stop before consuming another byte, not after draining the FIFO.
            self.dap._power_ready()
        require(self.dap._read_reg(1, 1) == DT, 'FIFO TAR incremented')
        self.apwrite(0, original)
        require(self.dap._read_reg(0, 1) == original, 'FIFO CSW restore mismatch')
        self.ap_csw_restored = True
        self.emit('nor-fifo-read-returned', data_hex=values.hex())
        return bytes(values)

    def restore_ap(self):
        """Debugger-register cleanup only; no target bus or FIFO access."""
        if self.saved_csw is None or self.ap_csw_restored:
            return
        self.emit('nor-ap-csw-restore-attempt', value=self.saved_csw)
        # Do not repair sticky errors. If AP access is uncertain, close reports
        # that fact instead of falsely claiming an exact debugger restoration.
        self.dap._power_ready()
        self.apwrite(0, self.saved_csw)
        require(self.dap._read_reg(0, 1) == self.saved_csw, 'AP-only CSW cleanup mismatch')
        self.ap_csw_restored = True
        self.emit('nor-ap-csw-restored', value=self.saved_csw)


class Status:
    def __init__(self, port, emit, *, seconds=60, clock=time.monotonic):
        require(0 < seconds <= 60, 'finite status deadline required')
        self.port, self.emit, self.clock = port, emit, clock
        self.start, self.seconds, self.error = clock(), seconds, None
        self.original, self.switched, self.restored, self.commands = None, False, False, 0

    def check(self):
        require(self.error is None, 'NOR fault latched: ' + str(self.error))
        require(0 <= self.clock()-self.start < self.seconds, 'NOR status deadline expired')

    def call(self, operation, *args):
        self.check()
        try:
            value = operation(*args)
            self.check()
            return value
        except BaseException as error:
            self.error = type(error).__name__ + ': ' + str(error)
            raise

    def read(self, address): return self.call(self.port.read, address)
    def write(self, address, value): return self.call(self.port.write, address, value)

    def wait(self, address, mask, expected):
        for _ in range(32):
            value = self.read(address)
            if value & mask == expected: return value
        raise ValueError('NOR bounded controller wait exhausted')

    def configuration(self):
        return {k: self.read(a) for k, a in QSPI_REGS.items()}

    def transition(self, value):
        require(self.read(CTRL) & (IDLE | ABORT) == IDLE, 'XIP not idle before transition')
        require(self.read(CTRL2) == 0, 'QSPI DMA/IRQ unexpectedly enabled')
        self.write(CTRL, value)
        self.wait(CTRL, ABORT | XIP | 7, value)
        require(self.read(CTRL) & IDLE, 'XIP not idle after transition')

    def command(self, opcode):
        require(opcode in (5, 0x35, 0x9f) and self.switched and not self.restored,
                'status opcode/phase scope')
        require(self.commands < 6, 'fixed status command budget exhausted')
        require(self.read(CTRL) == IDLE | 7 and self.read(CTRL2) == 0,
                'command clock/mode changed')
        require(self.read(CMDSTS) == 0 and self.read(FIFO) == 1,
                'stale completion or unconsumed FIFO before command')
        self.commands += 1
        self.emit('nor-command-start', sequence=self.commands, opcode=opcode)
        words = (0, 0x1000000, 3 if opcode == 0x9f else 0,
                 (opcode << 24) | (0 if opcode == 0x9f else 0xc))
        for i, value in enumerate(words): self.write(BASE + 4*i, value)
        self.wait(CMDSTS, 1, 1)
        if opcode == 0x9f:
            result = self.call(self.port.rdid_bytes)
        else:
            result = self.read(RSTS) & 0xff
        self.write(CMDSTS, 1)
        require(self.read(CMDSTS) == 0 and self.read(FIFO) == 1,
                'command completion/FIFO not consumed exactly')
        self.emit('nor-command-complete', sequence=self.commands, opcode=opcode,
                  value=result.hex() if isinstance(result, bytes) else result)
        return result

    def execute(self):
        try:
            return self._execute()
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__ + ': ' + str(error)
            raise

    def _execute(self):
        self.original = self.configuration()
        require(all(self.original[k] == v for k, v in CONFIG.items()), 'unqualified QSPI configuration')
        require([self.original[f'qspi_cmd{i}'] for i in range(4)] == [0, 0x1000003, 0, 0],
                'unexpected initial command descriptor')
        self.call(self.port.owner)
        self.transition(XIP | 7)
        self.transition(7)
        self.switched = True
        samples = []
        for _ in range(2):
            sr1, sr2 = self.command(5), self.command(0x35)
            require(sr1 & 3 == 0 and sr2 & 0x80 == 0, 'NOR WIP/WEL/SUS not clear; retain')
            identity = self.command(0x9f)
            samples.append(dict(sr1=sr1, sr2=sr2, jedec=identity.hex()))
            require(identity == bytes.fromhex('ef4018'), 'unexpected fresh NOR identity')
        require(samples[0] == samples[1], 'NOR identity/status changed between samples')
        require(samples[0]['sr2'] & 2, 'QE not set for saved quad XIP')
        before_restore = self.configuration()
        require(all(before_restore[k] == self.original[k] for k in PASSIVE),
                'passive QSPI configuration changed')
        # CMD/RSTS/FIFO are transaction state, not passive configuration.
        # In particular, replaying the saved CMD_W3 would launch a command.
        self.transition(XIP | 7)
        self.transition(XIP)
        after = self.configuration()
        require(all(after[k] == self.original[k] for k in CONFIG), 'QSPI restore mismatch')
        self.call(self.port.owner)
        self.restored = True
        return dict(samples=samples, after=after, command_count=self.commands,
                    configuration_restored=True, command_trigger_restored=False,
                    nor_write_admitted=False, physical_variant_proven=False,
                    command_clock_hz_nominal=24000000, flash_payload_bytes_written=0)
