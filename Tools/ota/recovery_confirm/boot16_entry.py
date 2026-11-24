"""R2-B-only WFI stop and same-context release. No Flash/reset/device entry."""
import hashlib
import time
from types import SimpleNamespace

from .native_io import Words, guarded
from . import r2_health as health, r2_passive_state as passive, r2_ui_binding as ui
from .r2_mapped_backup import DMA, ENDPOINTS
from .r2_mapped_backup_byte import qualify as qualify_dma
from recovery_entry import state_probe, rendezvous, app_resume

IMAGE_SHA = 'e4737cfcbbb884c4a7fa407ea733486425674c7ed2723d0f8cf3263beb4e8802'
WFI, WFI_COMPARATOR = 0x080461c0, 0x480461c1
WFI_BYTES = bytes.fromhex('30bfa9e7')
DHCSR, DCRSR, DCRDR = 0xe000edf0, 0xe000edf4, 0xe000edf8
PAUSE, COMP, FPCTRL = 0xe0042008, 0xe0002008, 0xe0002000
USB_CONNECTION, USB_BOT = 0x20053538, 0x200007e8
REGS = dict(app_resume.REGISTERS)
EXTRA = {DCRDR, PAUSE, FPCTRL, *range(COMP, COMP+24, 4), 0xe000ed00,
         0xe000ef34, 0x40002c00, WFI}
READS = (set(REGS.values()) | EXTRA | passive.READS | state_probe.STATE_WORDS |
         set(range(ui.SRAM_START, ui.SRAM_END, 4)) | set(DMA.values()) | set(ENDPOINTS.values()))


def verify(image, map_bytes):
    if (type(image) is not bytes or len(image) != 619580 or
            hashlib.sha256(image).hexdigest() != IMAGE_SHA):
        raise ValueError('exact R2-B image required')
    ui.verify(image, map_bytes)
    if image[WFI-health.PRIMARY:WFI-health.PRIMARY+4] != WFI_BYTES:
        raise ValueError('R2 main-loop WFI bytes differ')


def context_ok(context):
    return (context['pc'] == WFI and context['xpsr'] & 0x010001ff == 0x01000000 and
            context['special'] in (0, 4 << 24) and context['msp'] % 8 == 0 and
            0x20056000 < context['msp'] <= 0x20058000 and not context['fpccr'] & 1)


def resume_ok(row, vectors):
    if row['dhcsr'] & 0x020affff != 0x20003 or row['vtor'] != health.RUNTIME:
        raise ValueError('R2 held runtime epoch required')
    if (row['icsr'] & 0x900001ff or row['shcsr'] & 0xfd8b or row['demcr'] & 0x60001 or
            row['cfsr'] or row['hfsr']):
        raise ValueError('active/pending fault/debug/reset hazard')
    if (row['systick_ctrl'] & 7 != 7 or row['systick_load'] != 287999 or
            row['systick_value'] > 287999 or row['shpr3'] >> 24 != 0 or row['scr'] & 6):
        raise ValueError('R2 SysTick wake profile differs')
    if len(vectors) != 524 or int.from_bytes(vectors[60:64], 'little') != 0x08018191:
        raise ValueError('exact R2 SysTick vector required')
    for bank in range(4):
        pending = row['iser%d' % bank] & row['ispr%d' % bank]
        for bit in range(32):
            if not pending & (1 << bit): continue
            at = (16+bank*32+bit)*4
            handler = int.from_bytes(vectors[at:at+4], 'little')
            if at+4 > len(vectors) or not handler & 1 or handler in (0xffffffff, 0x0801bf29, 0x0801bf2b):
                raise ValueError('pending IRQ has no qualified R2 handler')


class Control:
    def __init__(self, dap, image, map_bytes, owner, emit, *, seconds=120,
                 clock=time.monotonic, sleep=time.sleep, guard=guarded):
        verify(image, map_bytes)
        self.image, self.owner, self.emit, self.clock, self.sleep, self.guard = image, owner, emit, clock, sleep, guard
        self.expected = None
        self.error = None
        self.reset_seen = self.mutation_attempted = self.release_attempted = self.release_returned = False
        self.acquired = self.used = False
        self.restoring_pause = self.pause_restored = False
        self.stage_deadline = clock()+120
        self.before = self.context_before = None
        self.words = Words(dap, emit, reads=READS, write_allowed=self.allowed,
                           seconds=seconds, clock=clock, guard=self.native)
        self.view = ui.View(image, map_bytes, self.words.read32, self.check)

    def check(self):
        if self.error is not None or self.reset_seen or self.owner() is not True:
            raise ValueError('R2 control owner/error/reset lost')
        if self.stage_deadline is not None and self.clock() >= self.stage_deadline:
            raise ValueError('R2 control stage deadline expired')
        self.words.check()
        return True

    def native(self, function, *args, seconds):
        self.check()
        result = self.guard(function, *args, seconds=seconds)
        self.check()
        return result

    def allowed(self, address, value):
        if self.expected != (address, value) or self.error is not None or self.reset_seen:
            return False
        if address == PAUSE:
            return self.before is not None and value == (self.before['pause'] if self.restoring_pause
                                                        else self.before['pause'] | 0x1000)
        if address == REGS['dfsr']:
            return self.acquired and not self.release_attempted and self.before['dfsr'] & 2 == 0 and value == 2
        if address == COMP: return value in (WFI_COMPARATOR, 0) and not self.release_attempted
        if address == DCRSR: return value in (15, 16, 17, 20) and not self.release_attempted
        if address == DHCSR: return self.acquired and self.release_attempted and value == 0xa05f0001
        return False

    def write(self, address, value):
        self.check()
        self.mutation_attempted = True
        self.expected = (address, value)
        try: self.words.write32(address, value)
        finally: self.expected = None

    def status(self, halted):
        self.check()
        value = self.words.read32(DHCSR)
        self.reset_seen |= bool(value & 0x02000000)
        if self.reset_seen or value & 0x80000 or value & 0xffff != (3 if halted else 1):
            raise ValueError('R2 core reset/lockup/debug controls differ')
        if bool(value & 0x20000) != halted or self.words.read32(health.VTOR) != health.RUNTIME:
            raise ValueError('R2 halt/runtime VTOR differs')
        if self.words.read32(health.CFSR) or self.words.read32(health.HFSR):
            raise ValueError('R2 fault status not clear')
        return value

    def held(self):
        status = self.status(True)
        if self.before is None or self.words.read32(PAUSE) != self.before['pause'] | 0x1000:
            raise ValueError('R2 watchdog halt pause lost')
        return status

    def identity(self, halted):
        self.status(halted)
        for address, expected in ((health.PRIMARY+0x400, self.image[0x400:0x460]),
                                  (health.RUNTIME, self.image[0x800:0xa0c]), (WFI, WFI_BYTES)):
            if self.words.read_bytes(address, len(expected)) != expected:
                raise ValueError('fresh R2 header/vector/WFI differs')
        self.status(halted)

    def context(self):
        self.held()
        values = []
        for selector in (15, 16, 17, 20):
            self.write(DCRSR, selector)
            for _ in range(16):
                if self.held() & 0x10000: break
            else: raise ValueError('core selector timeout')
            values.append(self.words.read32(DCRDR))
        result = dict(zip(('pc', 'xpsr', 'msp', 'special'), values))
        result['fpccr'] = self.words.read32(0xe000ef34)
        if not context_ok(result): raise ValueError('not exact qualified R2 main WFI context')
        self.held()
        return result

    def media(self, halted):
        self.status(halted)
        def read(op, address, size):
            if op != 'read' or size != 4: raise ValueError('state word only')
            return self.words.read32(address).to_bytes(4, 'little')
        sample = state_probe.sample(SimpleNamespace(_call=read, emit=self.emit))
        row = {label: {key: self.words.read32(addr) for key, addr in fields.items()}
               for label, fields in (('fields', passive.FIELDS), ('clocks', passive.CLOCK_ADDR),
                                     ('qspi', passive.QSPI))}
        view = self.view.sample() if self.view.attempted else self.view.locate()
        dma = {name: self.words.read32(addr) for name, addr in DMA.items()}
        endpoints = {name: self.words.read32(addr) for name, addr in ENDPOINTS.items()}
        epoch = qualify_dma(row, view, dma, endpoints)
        raw = sample['raw']
        if (raw['display_dma_count'] or raw['sd_dma_count'] or raw['sdio2_dtcnt'] or
                self.words.read32(0x40002c00) != 0):
            raise ValueError('active storage/display transfer or WWDT prevents long halt')
        # Normal noncircular DMA and the SD data state machine may retain EN
        # after count exhaustion. Stream/read-wait/SDIO modes are not admitted.
        if raw['sdio2_dtctrl'] not in (0, 0x98, 0x99, 0x9a, 0x9b):
            raise ValueError('unqualified SDIO2 data mode')
        usb = dict(connection=self.words.read32(USB_CONNECTION) & 255,
                   bot=self.words.read32(USB_BOT) & 0xffff)
        if usb['connection'] not in (0, 1) or usb['bot'] not in (0, 7):
            raise ValueError('USB connection/BOT transaction prevents long halt')
        blockers = rendezvous.stopped_media_observation([sample, sample])['observed_blockers']
        if blockers: raise ValueError('R2 media not settled: '+','.join(blockers))
        if self.words.read32(health.FLAGS) & 0xffffff != 0x010104 or self.words.read32(health.HEALTH+32) != 1:
            raise ValueError('R2 confirmation completion/health readiness absent')
        self.status(halted)
        result = dict(state=sample, passive=row, ui=view, dma=dma, endpoints=endpoints, epoch=epoch, usb=usb)
        self.emit('boot16-media', halted=halted, **result)
        return result

    def acquire(self):
        if self.used: raise ValueError('R2 rendezvous cannot replay')
        self.used = True
        try:
            self.identity(False)
            if self.words.read32(0xe000ed00) != 0x410fc241: raise ValueError('CPU differs')
            self.before = dict(pause=self.words.read32(PAUSE), fp=self.words.read32(FPCTRL),
                comparators=[self.words.read32(COMP+4*i) for i in range(6)],
                dfsr=self.words.read32(REGS['dfsr']), demcr=self.words.read32(REGS['demcr']))
            if self.before['fp'] != 0x261 or self.before['comparators'] != [0]*6 or self.before['demcr'] & 1:
                raise ValueError('unowned FPB/reset vector catch')
            self.media(False)
            self.write(PAUSE, self.before['pause'] | 0x1000)
            if self.words.read32(PAUSE) != self.before['pause'] | 0x1000:
                raise ValueError('watchdog pause readback differs')
            self.status(False)
            if self.words.read32(COMP): raise ValueError('FPB ownership changed')
            self.write(COMP, WFI_COMPARATOR)
            if self.words.read32(COMP) != WFI_COMPARATOR: raise ValueError('FPB arm differs')
            deadline = min(self.words.budget.end, self.clock()+15)
            while True:
                value = self.words.read32(DHCSR)
                self.reset_seen |= bool(value & 0x02000000)
                if self.reset_seen or value & 0x80000 or self.clock() >= deadline:
                    raise ValueError('WFI halt unresolved; retain without automatic resume')
                if value & 0x20000: break
                self.native(self.sleep, .01, seconds=1)
            self.context_before = self.context()
            self.write(COMP, 0)
            if self.words.read32(COMP): raise ValueError('owned FPB disarm failed')
            self.identity(True)
            samples = [self.media(True), self.media(True)]
            if samples[0]['epoch'] != samples[1]['epoch'] or self.context() != self.context_before:
                raise ValueError('R2 held epoch/context changed')
            self.acquired = True
            self.stage_deadline = None
            return dict(result='R2_B_WFI_HELD', before=self.before, context=self.context_before, media=samples)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise

    def release(self, admit):
        if not self.acquired or self.release_attempted: raise ValueError('qualified unused R2 release required')
        try:
            self.stage_deadline = self.clock()+120
            if admit() is not True: raise ValueError('complete Boot/App preservation proof missing')
            self.identity(True)
            self.media(True)
            if self.context() != self.context_before: raise ValueError('original CPU context differs')
            if (self.words.read32(FPCTRL) != self.before['fp'] or
                    [self.words.read32(COMP+4*i) for i in range(6)] != [0]*6 or
                    self.words.read32(REGS['demcr']) != self.before['demcr']):
                raise ValueError('debug ownership changed before release')
            for _ in range(2):
                row = {key: self.words.read32(addr) for key, addr in REGS.items()}
                resume_ok(row, self.image[0x800:0xa0c])
            dfsr = self.words.read32(REGS['dfsr'])
            if dfsr != self.before['dfsr'] | 2:
                raise ValueError('unowned debug fault status appeared')
            if self.before['dfsr'] & 2 == 0:
                self.write(REGS['dfsr'], 2)
                if self.words.read32(REGS['dfsr']) != self.before['dfsr']:
                    raise ValueError('owned breakpoint status did not clear')
            self.held()
            if admit() is not True: raise ValueError('final release admission lost')
            self.release_attempted = True
            self.write(DHCSR, 0xa05f0001)
            self.release_returned = True
            return dict(result='R2_RELEASE_STORE_RETURNED', reset_performed=False,
                        boot_executed=False, runtime_health_verified=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise

    def restore_pause_running(self):
        if not self.release_returned or self.pause_restored or self.restoring_pause:
            raise ValueError('one returned release required for pause restoration')
        try:
            self.status(False)
            self.restoring_pause = True
            self.write(PAUSE, self.before['pause'])
            if self.words.read32(PAUSE) != self.before['pause']:
                raise ValueError('original watchdog halt-freeze value not restored')
            self.status(False)
            self.pause_restored = True
            return dict(result='R2_RUNNING_PAUSE_RESTORED', original_pause=self.before['pause'])
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise
