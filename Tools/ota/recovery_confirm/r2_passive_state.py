"""R2 passive state only: no mapped NOR, FIFO, mutation, connection or Close."""
import hashlib
import time

import p34_finalized_vtor_capture as binding
from recovery_entry.owner_probe import QSPI_REGS
from recovery_entry.host_nor import CONFIG, CLOCK
from .native_io import Words, guarded
from . import r2_health as health

FIELDS = dict(session=0x20052a54, isr_active=0x20052b34, epoch=0x20052bc8,
    overlay=0x20053acc, disabled=0x2000017c, jedec=0x20053558,
    retained=0x20052658, boot_baud=0x2005265c, retention_error=0x20052654,
    core_clock=0x20000110, baud_divider=0x40011008, uart_ctrl1=0x4001100c,
    uart_ctrl2=0x40011010, uart_ctrl3=0x40011014)
CLOCK_ADDR = dict(crm_ctrl=0x40023800, crm_pllcfg=0x40023804, crm_cfg=0x40023808,
                  crm_misc1=0x400238a0, crm_misc2=0x400238a4)
# Only passive QSPI configuration/status registers, never DT/FIFO or command words.
QSPI = {key: QSPI_REGS[key] for key in CONFIG}
READS = {health.DHCSR, health.VTOR, *FIELDS.values(), *CLOCK_ADDR.values(), *QSPI.values(),
         *range(0x08010400, 0x08010460, 4), *range(health.RUNTIME, health.RUNTIME + 524, 4)}


def decode(row):
    values, qspi, clocks = row['fields'], row['qspi'], row['clocks']
    for actual, wanted in ((values, FIELDS), (qspi, QSPI), (clocks, CLOCK_ADDR)):
        if set(actual) != set(wanted) or any(type(v) is not int or not 0 <= v <= 0xffffffff for v in actual.values()):
            raise ValueError('invalid passive snapshot fields')
    disabled = (values['disabled'] >> 8) & 255
    idle = values['session'] & 255 == 0 and values['isr_active'] & 255 == 0 and values['overlay'] & 255 == 0
    known_clock = clocks == CLOCK and values['core_clock'] == 288000000
    divider = values['baud_divider'] & 0xffff
    actual = 144000000 // divider if known_clock and divider else None
    retained = values['retained'] == 0x5034f708 and values['boot_baud'] == 921600 and values['retention_error'] == 0
    qspi = dict(qspi, qspi_xip3=qspi['qspi_xip3'] & ~8)
    return dict(idle_observed=idle, ble_epoch=values['epoch'], retained_921600=retained,
        actual_uart_baud=actual, nominal_clock_profile_matched=known_clock,
        actual_uart_matches_requested=actual is not None and 921600-921600//33 <= actual <= 921600+921600//33,
        qspi_config_matches_prior=qspi == CONFIG, ota_flash_gate=disabled == 0 and values['jedec'] == 0xef4018,
        live_mapping_qualified=False, other_nor_writers_excluded=False, ota_ready=False)


class Probe:
    def __init__(self, dap, logs, image, map_bytes, owner, remaining, *, clock=time.monotonic,
                 sleep=time.sleep, guard=guarded):
        digest = hashlib.sha256(image).hexdigest() if type(image) is bytes else None
        if digest not in binding.PLANNED or len(image) != binding.IMAGE_BYTES:
            raise ValueError('exact R2 A/B image required')
        health.verify_map(map_bytes)
        self.dap, self.logs, self.image, self.owner, self.remaining = dap, logs, image, owner, remaining
        self.sleep, self.guard = sleep, guard
        self.index = logs.gate.index
        self.used = self.active = self.reset_seen = False
        self.error = None
        self.previous_left = None
        self.words = Words(dap, logs.emit, reads=READS, write_allowed=lambda a, v: False,
                           seconds=60, clock=clock, guard=self.native)
        self.check()
        if self.index <= 0 or len(logs.gate.paths) - self.index != 2:
            raise ValueError('passive state needs sealed setup and separate final Close log')
        self.guard(logs.verify_head, seconds=min(30, self.remaining()-60))

    def check(self):
        left = self.remaining()
        if (self.error is not None or self.reset_seen or self.owner() is not True or
            self.logs.dap is not self.dap or not self.logs.target_allowed() or
            self.logs.gate.index != self.index or type(left) not in (int, float) or not 60 < left <= 900 or
            self.previous_left is not None and left > self.previous_left):
            raise ValueError('passive state owner/reset/reserve lost')
        self.previous_left = left
        self.words.check()

    def native(self, fn, *args, seconds):
        self.check()
        if not self.active: raise ValueError('passive state inactive')
        result = self.guard(fn, *args, seconds=min(seconds, self.remaining()-60))
        self.check()
        return result

    def running(self):
        status = self.words.read32(health.DHCSR)
        self.reset_seen |= bool(status & 0x02000000)
        if self.reset_seen or status & 0x000a0000 or self.words.read32(health.VTOR) != health.RUNTIME:
            raise ValueError('passive state running epoch changed')

    def identity(self):
        self.running()
        if (self.words.read_bytes(0x08010400, 96) != self.image[0x400:0x460] or
            self.words.read_bytes(health.RUNTIME, 524) != self.image[0x800:0xa0c]):
            raise ValueError('passive R2 identity differs')
        self.running()

    def sample(self):
        self.running()
        row = dict(started=self.words.budget.now())
        for label, fields in (('fields', FIELDS), ('clocks', CLOCK_ADDR), ('qspi', QSPI)):
            row[label] = {key: self.words.read32(address) for key, address in fields.items()}
        self.running()
        row['ended'] = self.words.budget.now()
        self.logs.emit('r2-passive-state-sample', **row)
        return row

    def run(self):
        if self.used: raise ValueError('passive state cannot replay')
        self.used = self.active = True
        try:
            self.identity()
            before = self.sample()
            self.native(self.sleep, 1., seconds=2)
            after = self.sample()
            self.identity()
            a, b = decode(before), decode(after)
            self.active = False
            trace = self.guard(lambda: self.logs.switch(read_allowed=lambda a: a in READS, expected_stores=[]),
                               seconds=min(30, self.remaining()-60))
            self.index += 1
            self.check()
            if trace['target_writes'] or trace['native_close']:
                raise ValueError('passive state log is not read-only')
            return dict(result='R2_PASSIVE_STATE_OBSERVED', before=a, after=b,
                sampled_epoch_stable=a['ble_epoch'] == b['ble_epoch'], full_image_verified=False,
                native_close_audited=False, reset_seen=False, nor_bytes_read=0, ota_ready=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__ + ': ' + str(error)
            raise
        finally:
            self.active = False
