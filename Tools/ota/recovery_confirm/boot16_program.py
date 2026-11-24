"""Bounded Boot16 body on a caller-owned connection; no device/CLI ownership."""
import math
import time

from . import boot16, boot16_settle as settle, flash_port as flash
from .boot16_usb_entry import Control
from .boot16_entry import READS as CONTROL_READS, DCRSR, PAUSE, COMP, WFI_COMPARATOR, DHCSR, REGS
from .r2_paired_health import Monitor
from .native_io import Words, guarded

APP = 0x08010000
APP_BYTES = 619580
BLOCK = 32768
LOG_COUNT = 57
POST_RESERVE = 1500
SECTOR_RESERVE = 390
INTERNAL_READS = CONTROL_READS | settle.READS | set(range(boot16.START, APP+APP_BYTES, 4))
FIXED_META = {flash.IDCODE, flash.FSIZE, *flash.CONFIG, *flash.PROTECTION, *flash.CLOCK}
SELECTORS = [(DCRSR, value) for value in (15, 16, 17, 20)]


class Body:
    def __init__(self, dap, logs, remaining, archive, image, map_bytes, plan, *, direction='activate',
                 retained=None, checkpoint=None, clock=time.monotonic, sleep=time.sleep, guard=guarded):
        if type(plan) is not boot16.Plan or direction not in ('activate', 'restore'):
            raise ValueError('exact Boot16 plan/direction required')
        if (direction == 'restore') != (retained is not None):
            raise ValueError('restoration requires reconciled retained predecessor')
        if not callable(checkpoint): raise ValueError('durable prewrite checkpoint required')
        if len(logs.gate.paths) != LOG_COUNT or logs.gate.index != 1:
            raise ValueError('fixed setup/body/final log layout required')
        self.dap, self.logs, self.remaining, self.archive = dap, logs, remaining, archive
        self.image, self.map_bytes, self.plan, self.direction = image, map_bytes, plan, direction
        self.clock, self.sleep, self.guard = clock, sleep, guard
        self.retained = retained
        self.checkpoint = checkpoint
        self.active = self.used = self.held = self.boot_may_have_changed = self.post_verified = False
        self.release_started = False
        self.error = self.previous_left = self.phase_deadline = None
        self.phase = 'CREATED'
        self.results = {}
        self.control = self.monitor = self.sector = None
        self.meta = self.preimage = self.desired = None
        self.sectors = []

    def left(self):
        left = self.remaining()
        if (type(left) not in (int, float) or not math.isfinite(left) or not 0 < left <= 7200 or
                self.previous_left is not None and left > self.previous_left):
            raise ValueError('invalid global programming budget')
        self.previous_left = left
        return left

    def owner(self):
        return self.active and self.error is None and self.logs.target_allowed() and self.left() > 90

    def native(self, function, *args, seconds):
        if not self.owner(): raise ValueError('Boot16 owner/close reserve lost')
        limit = min(seconds, self.left()-90)
        if self.phase_deadline is not None: limit = min(limit, self.phase_deadline-self.clock())
        if limit <= 0: raise ValueError('Boot16 phase deadline expired')
        result = self.guard(function, *args, seconds=limit)
        if not self.owner() or self.phase_deadline is not None and self.clock() >= self.phase_deadline:
            raise ValueError('Boot16 phase/owner lost after operation')
        return result

    def phase_start(self, name, seconds):
        if not self.owner(): raise ValueError('phase without owner')
        self.phase = name
        self.phase_deadline = min(self.clock()+seconds, self.clock()+self.left()-90)
        self.logs.emit('boot16-program-phase', phase=name, remaining=self.left())

    def seal(self, reads, stores=()):
        # Switching intentionally inhibits target I/O, so use the outer guard.
        limit = min(90, self.left()-90)
        if self.phase_deadline is not None: limit = min(limit, self.phase_deadline-self.clock())
        if limit <= 0: raise ValueError('no phase allowance for log seal')
        return self.guard(lambda: self.logs.switch(read_allowed=lambda a: a in reads,
                          expected_stores=stores), seconds=limit)

    def entry(self):
        self.phase_start('ENTRY', 180)
        self.control = Control(self.dap, self.image, self.map_bytes, self.owner, self.logs.emit,
            seconds=min(7000, self.left()-90), clock=self.clock, sleep=self.sleep, guard=self.native)
        if self.direction == 'activate':
            result = self.control.acquire()
            stores = [(PAUSE, self.control.before['pause'] | 0x1000), (COMP, WFI_COMPARATOR)]
            stores += SELECTORS + [(COMP, 0)] + SELECTORS
        else:
            old = self.retained
            if (old.get('release_attempted') is not False or old.get('boot_may_have_changed') is not True or
                    old.get('phase') not in ('PROGRAM', 'POST_CAPTURE') or
                    not isinstance(old.get('before'), dict) or not isinstance(old.get('context'), dict)):
                raise ValueError('only a pre-release Boot-body failure can enter restoration')
            self.control.before = dict(old['before'])
            self.control.context_before = dict(old['context'])
            self.control.used = True
            self.control.identity(True)
            if self.control.context() != self.control.context_before: raise ValueError('retained CPU context differs')
            if (self.control.words.read32(0xe0002000) != self.control.before['fp'] or
                    [self.control.words.read32(COMP+4*i) for i in range(6)] != [0]*6 or
                    self.control.words.read32(REGS['demcr']) != self.control.before['demcr'] or
                    self.control.words.read32(REGS['dfsr']) != self.control.before['dfsr'] | 2):
                raise ValueError('retained debug ownership differs')
            samples = [self.control.media(True), self.control.media(True)]
            if samples[0]['epoch'] != samples[1]['epoch'] or self.control.context() != self.control.context_before:
                raise ValueError('retained media/context drift')
            self.control.acquired = True
            self.control.stage_deadline = None
            result = dict(result='R2_B_WFI_RETAINED', before=self.control.before,
                          context=self.control.context_before, media=samples)
            stores = SELECTORS*2
        self.held = True
        self.results['entry'] = result
        self.results['entry_trace'] = self.seal(CONTROL_READS, stores)

    def controller(self, *, pending=False):
        self.control.held()
        port = settle.LockOnly(self.dap, self.owner, self.logs.emit, clock=self.clock, guard=self.native)
        port.pause = self.control.before['pause'] | 0x1000
        values = port.snapshot()
        if not pending and any(values[c] != 0x80 for _, _, c, _ in flash.BANKS):
            raise ValueError('both Flash banks must be idle and locked')
        fixed = {a: values[a] for a in FIXED_META}
        if self.meta is None: self.meta = fixed
        if self.meta != fixed: raise ValueError('Flash configuration/protection drift')
        return values

    def settle_controller(self):
        self.phase_start('SETTLE', 90)
        if self.direction == 'restore':
            port = settle.LockOnly(self.dap, self.owner, self.logs.emit, clock=self.clock, guard=self.native)
            port.pause = self.control.before['pause'] | 0x1000
            result = port.run()
        else:
            result = dict(result='BOOT16_CONTROLLER_ALREADY_LOCKED', stores=[], before=self.controller())
        self.controller()
        self.results['settlement'] = result
        self.results['settlement_trace'] = self.seal(CONTROL_READS | settle.READS, result['stores'])

    def capture(self, label):
        self.phase_start('PRE_CAPTURE' if label == 'before' else 'POST_CAPTURE', 900)
        port = Words(self.dap, self.logs.emit, reads=INTERNAL_READS, write_allowed=lambda a, v: False,
                     seconds=min(900, self.left()-90), clock=self.clock, guard=self.native)
        boot_bytes = bytearray()
        pending = label == 'before' and self.direction == 'restore'
        for name, origin, expected in (
            ('boot', boot16.START, self.plan.original if label == 'before' and self.direction == 'activate' else
             None if label == 'before' else self.desired), ('app', APP, self.image)):
            size = 65536 if name == 'boot' else APP_BYTES
            for start in range(0, size, BLOCK):
                self.controller(pending=pending)
                data = bytearray()
                stop = min(size, start+BLOCK)
                for offset in range(start, stop, 1024):
                    self.control.held()
                    data.extend(port.read_bytes(origin+offset, min(1024, stop-offset)))
                    self.control.held()
                raw = bytes(data)
                self.native(self.archive, label+'-'+name, start, raw, seconds=30)
                if expected is not None and raw != expected[start:stop]:
                    raise ValueError('complete Boot/App physical identity differs')
                if name == 'boot': boot_bytes.extend(raw)
                self.controller(pending=pending)
                self.seal(INTERNAL_READS)
        if label == 'before':
            self.preimage = bytes(boot_bytes)
            self.desired = self.plan.desired(self.direction, self.preimage)
        else:
            if bytes(boot_bytes) != self.desired: raise ValueError('full Boot final archive differs')
            self.results['archives'] = self.native(self.archive.verify, 'after', self.desired,
                                                   self.image, seconds=30)
            self.post_verified = True

    def program(self):
        self.phase_start('PROGRAM', 8*SECTOR_RESERVE+120)
        if self.left() < 8*SECTOR_RESERVE+POST_RESERVE: raise ValueError('whole remaining write/verification allowance missing')
        self.native(self.checkpoint, self, seconds=30)
        self.logs.emit('boot16-prewrite-checkpoint-returned', direction=self.direction)
        for index in range(8):
            if self.left() < (8-index)*SECTOR_RESERVE+POST_RESERVE: raise ValueError('remaining sector/verification reserve lost')
            self.controller()
            start = index*2048
            desired = self.desired[start:start+2048]
            before = self.preimage[start:start+2048]
            self.sector = boot16.Sector(self.dap, self.plan, self.preimage, index, self.direction,
                self.owner, self.logs.emit, clock=self.clock, sleep=self.sleep, guard=self.native)
            if desired == before:
                if self.sector.read_sector() != before: raise ValueError('unchanged sector drift')
                result = dict(address=boot16.START+start, unchanged=True, programmed_words=0)
                stores = []
            else:
                self.boot_may_have_changed = True
                result = self.sector.run()
                stores = boot16.stores(self.plan, self.preimage, index, self.direction)
            self.controller()
            self.seal(CONTROL_READS | settle.READS | self.sector.words.reads, stores)
            self.sectors.append(dict(index=index, **result))
            self.logs.emit('boot16-sector-audited', **self.sectors[-1])

    def release(self):
        self.phase_start('RELEASE', 180)
        self.release_started = True
        def admit():
            if not self.post_verified or len(self.sectors) != 8 or not self.owner(): return False
            self.controller()
            return True
        self.results['release'] = self.control.release(admit)
        self.held = False
        stores = SELECTORS + ([] if self.control.before['dfsr'] & 2 else [(REGS['dfsr'], 2)]) + [(DHCSR, 0xa05f0001)]
        self.results['release_trace'] = self.seal(CONTROL_READS | settle.READS, stores)
        self.results['pause'] = self.control.restore_pause_running()
        self.results['pause_trace'] = self.seal(CONTROL_READS, [(PAUSE, self.control.before['pause'])])
        self.phase_start('HEALTH', 300)
        self.monitor = Monitor(self.dap, self.image, self.map_bytes, self.owner, self.logs, self.remaining,
            clock=self.clock, sleep=self.sleep, guard=self.native)
        self.results['health'] = self.monitor.run()

    def run(self):
        if self.used: raise ValueError('Boot16 body cannot replay')
        self.used = self.active = True
        try:
            self.entry()
            if self.direction == 'restore':
                self.capture('before')
                self.settle_controller()
            else:
                self.settle_controller()
                self.capture('before')
            self.program()
            self.capture('after')
            self.release()
            if self.logs.gate.index != LOG_COUNT-1: raise ValueError('body final log position differs')
            self.phase = 'READY_FOR_CLOSE'
            return dict(result='BOOT16_READY_FOR_NATIVE_CLOSE', direction=self.direction,
                        boot_executed=False, app_changed=False, eeprom_observed=False)
        except BaseException as error:
            self.error = type(error).__name__+': '+str(error)
            raise
        finally:
            self.active = False
