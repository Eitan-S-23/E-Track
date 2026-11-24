"""Complete-state body on one prepared connection; no standalone device CLI.

The caller owns native setup/close, durable archives and source-bound admission.
This body never resumes the captured original-App context, even on failure.
"""
import hashlib
import math
import time

from recovery_entry import control_probe, rendezvous, owner_probe
from . import install_entry
from recovery_entry.state_probe import STATE_WORDS
from . import gpio_page as gpio, flash_port as flash
from .native_io import Words, guarded
from .held_window import Window
from .read_pair import ReadPair
from .flash_plan import APP_START, geometry
from .flash_sequence import Sequence, PREIMAGE_SHA
from .eeprom_sequence import Wire, stores as eeprom_stores
from .confirm_io import draft, observe, Transaction
from .nor_capture import Capture, REGIONS, BLOCK
from .boot_exit import Exit, BOOT_SHA, READS as EXIT_READS, DFSR, DEMCR, AIRCR, DCRSR, DHCSR
from .r2_health import Monitor, verify_map

OLD_APP_SHA = '4d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6'
BCB_SHA = '57282afe19792eb1bd4774b20253947d9ff3badf78d95052abb62183b57bec4f'
META = (flash.IDCODE,flash.FSIZE,*flash.CLOCK,*flash.CONFIG,*flash.PROTECTION,
        *(address for _,status,control,_ in flash.BANKS for address in (status,control)))
INTERNAL_READS = {flash.DHCSR,flash.PAUSE,*META,*range(0x08000000,0x080a7800,4)}
STATE_EXTRA = (flash.DHCSR,flash.PAUSE,0x40002c00)
BODY_SEGMENTS = 719


class Install:
    def __init__(self,dap,observation,logs,remaining,archive,assets,function,*,
                 clock=time.monotonic,sleep=time.sleep,guard=guarded,retained_entry=None):
        required = {'boot','old_app','image','envelope','bcb','map',*REGIONS}
        if set(assets)!=required or any(type(raw) is not bytes for raw in assets.values()):
            raise ValueError('exact immutable installation assets required')
        self.assets = dict(assets)
        for name,size,digest in (('boot',65536,BOOT_SHA),('old_app',617588,OLD_APP_SHA),
                                 ('envelope',620544,PREIMAGE_SHA)):
            if len(assets[name])!=size or hashlib.sha256(assets[name]).hexdigest()!=digest:
                raise ValueError('retained asset differs: '+name)
        geometry(assets['image'])
        verify_map(assets['map'])
        if assets['envelope'][:617588]!=assets['old_app']:
            raise ValueError('original App/envelope mismatch')
        if (len(assets['bcb'])!=256 or assets['bcb'][:128]!=assets['bcb'][128:] or
                hashlib.sha256(assets['bcb']).hexdigest()!=BCB_SHA):
            raise ValueError('historical complete pair binding required')
        for name,(start,end,digest) in REGIONS.items():
            if len(assets[name])!=end-start or hashlib.sha256(assets[name]).hexdigest()!=digest:
                raise ValueError('retained NOR binding differs: '+name)
        self.dap,self.observation,self.logs,self.remaining = dap,observation,logs,remaining
        self.archive,self.function,self.clock,self.sleep,self.native_guard = archive,function,clock,sleep,guard
        self.index = logs.gate.index
        if logs.dap is not dap or self.index!=1 or len(logs.gate.paths)!=BODY_SEGMENTS+2:
            raise ValueError('single separately sealed setup and exact body/final logs required')
        self.used = self.active = self.held = self.app_may_have_changed = False
        self.delegating = False
        self.after_app = self.released = False
        self.final_confirmed = False
        self.boot_used = False
        self.error = None
        self.previous_left = None
        self.phase = 'PREPARED'
        self.results = {}
        self.retained_entry = retained_entry
        self.control = control_probe.Control(dap,observation,logs.emit,assets['old_app'][0x400:0x460],
                                             retained=retained_entry is not None)
        self.flash_sequence = self.eeprom_wire = self.exit_port = None
        self.plan = self.pin_config = self.config_before = None
        self.check()
        self.native_guard(logs.verify_head,seconds=min(60,self.left()-90))

    def left(self):
        value = self.remaining()
        if (type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=28800 or
                self.previous_left is not None and value>self.previous_left):
            raise ValueError('complete-install global allowance invalid/nonmonotonic')
        self.previous_left = value
        return value

    def check(self,reserve=90):
        if (self.error is not None or self.dap is not self.logs.dap or not self.logs.target_allowed() or
                not self.delegating and self.logs.gate.index!=self.index or self.left()<=reserve):
            raise ValueError('complete-install owner/log/reserve lost')

    def owner(self):
        self.check()
        return self.active and self.held and not self.released and not self.control.reset_seen

    def component(self,operation):
        self.check()
        if self.delegating: raise ValueError('nested component delegation')
        self.delegating = True
        try:
            return operation()
        finally:
            self.index = self.logs.gate.index
            self.delegating = False

    def guard_for(self,port,reserve=90):
        def call(function,*args,seconds):
            if not self.owner(): raise ValueError('held installation owner missing')
            port.budget.end = min(port.budget.end,port.budget.now()+self.left()-reserve)
            result = self.native_guard(function,*args,seconds=min(seconds,port.budget.left()))
            self.check(reserve)
            return result
        return call

    def words(self,reads,seconds,reserve=90,write_allowed=lambda a,v:False):
        port = Words(self.dap,self.logs.emit,reads=reads,write_allowed=lambda a,v:self.owner() and write_allowed(a,v),
                     seconds=seconds,clock=self.clock)
        port.guard = self.guard_for(port,reserve)
        return port

    def save(self,name,offset,raw):
        self.check()
        self.native_guard(self.archive,name,offset,raw,seconds=min(300,self.left()-90))
        self.check()

    def seal(self,reads,stores=(),*,bind_words=True):
        self.check()
        trace = self.native_guard(lambda:self.logs.switch(read_allowed=lambda a:a in reads,
            expected_stores=stores,bind_words=bind_words),seconds=min(300,self.left()-90))
        self.index += 1
        self.check()
        if trace['target_writes']!=len(stores) or trace['native_close'] or trace['log_file_closed']!=1:
            raise ValueError('complete-install segment audit mismatch')
        return trace

    def phase_start(self,name):
        self.check()
        self.phase = name
        self.logs.emit('recovery-install-phase',phase=name,remaining=self.left())
        self.check()

    def entry(self):
        self.phase_start('RETAINED_ENTRY' if self.retained_entry is not None else 'FRESH_ENTRY')
        self.observation.emit = self.logs.emit
        result = (install_entry.retained(self.control,self.retained_entry) if self.retained_entry is not None else
                  rendezvous.acquire(self.control,self.logs.emit,seconds=15,clock=self.clock,sleep=self.sleep))
        self.results['entry'] = result
        expected_result = ('APP_WFI_RETAINED_AFTER_RECONNECT' if self.retained_entry is not None else
                           'APP_WFI_HALTED_RETAINED_NOT_RESET')
        if result['result']!=expected_result or result['media']['observed_blockers']:
            raise ValueError('fresh WFI/media entry failed; never auto-resume')
        self.held = True
        owners = []
        for _ in range(2):
            reader = owner_probe.Reader(self.dap,self.logs.emit)
            state = owner_probe.collect(reader)
            if not state['no_scheduled_sd_ota_owner']:
                raise ValueError('scheduled SD update owner present')
            owners.append(state)
        if owners[0]!=owners[1] or self.control.context()!=result['context']:
            raise ValueError('newly stopped context/software owner drift')
        if any(result['context'][name] for name in ('faultmask','basepri','primask')):
            raise ValueError('unexpected retained interrupt mask')
        for sample in result['state_samples']: install_entry.qualify_masters(sample)
        raw = result['state_samples'][-1]['raw']
        self.pin_config = {address:raw['gpiob_'+name] for address,name in (
            (gpio.MODE,'mode'),(gpio.TYPE,'type'),(gpio.DRIVE,'drive'),(gpio.PULL,'pull'),(gpio.OUTPUT,'output'))}
        selectors = tuple((DCRSR,value) for value in (15,16,17,20))
        expected = ((control_probe.PAUSE,result['before']['debug_apb1_frz']|0x1000),
                    (control_probe.COMP,rendezvous.WFI_COMPARATOR))+selectors+((control_probe.COMP,0),)+selectors+selectors
        if self.retained_entry is not None: expected = selectors*3
        reads = {*control_probe.READ_WORDS,*STATE_WORDS,*owner_probe.QSPI_REGS.values(),
                 *range(0x20000000,0x20058000,4),*range(APP_START,APP_START+617588,4)}
        self.results['entry_audit'] = self.seal(reads,expected,bind_words=False)
        self.results['entry_owners'] = owners

    def state(self):
        port = self.words(STATE_EXTRA,60)
        samples = []
        for _ in range(2):
            if port.read32(flash.DHCSR)&0x020a0000!=0x20000 or port.read32(flash.PAUSE)!=0x1000:
                raise ValueError('held epoch changed during final media observation')
            window = Window(self.dap,self.logs.emit,self.owner,lambda:self.left()-90,seconds=60,clock=self.clock,
                            guard=self.native_guard)
            sample = window.capture()
            sample['control_extra'] = {'wwdt_ctrl':port.read32(0x40002c00)}
            install_entry.qualify_masters(sample)
            wanted = self.assets['image' if self.after_app else 'old_app'][0x400:0x460]
            if sample['header_hex']!=wanted.hex(): raise ValueError('held state header phase changed')
            samples.append(sample)
        if rendezvous.stopped_media_observation(samples)['observed_blockers']:
            raise ValueError('held media no longer settled')
        self.seal({*STATE_WORDS,*STATE_EXTRA})
        return samples

    def internal(self,label):
        self.phase_start(label.upper()+'_INTERNAL_CAPTURE')
        port = self.words(INTERNAL_READS,900)
        def held():
            if port.read32(flash.DHCSR)&0x020a0000!=0x20000 or port.read32(flash.PAUSE)!=0x1000:
                raise ValueError('internal archive lost held epoch')
        held()
        metadata = {address:port.read32(address) for address in META}
        status_addresses = {status for _,status,_,_ in flash.BANKS}
        invariant = {address:value for address,value in metadata.items() if address not in status_addresses}
        if self.config_before is None: self.config_before = invariant
        elif invariant!=self.config_before: raise ValueError('Flash configuration/protection changed')
        for _,status,control,_ in flash.BANKS:
            if metadata[status]&0x15 or metadata[control]!=0x80:
                raise ValueError('Flash archive requires both banks idle/locked')
        envelope = (self.assets['image']+self.assets['envelope'][len(self.assets['image']):]
                    if self.after_app else self.assets['envelope'])
        for name,origin,expected in (('boot',0x08000000,self.assets['boot']),('envelope',APP_START,envelope)):
            for offset in range(0,len(expected),BLOCK):
                stop = min(offset+BLOCK,len(expected))
                raw = bytearray()
                for at in range(offset,stop,1024):
                    held()
                    raw.extend(port.read_bytes(origin+at,min(1024,stop-at)))
                    held()
                self.save(label+'-'+name,offset,bytes(raw))
                if bytes(raw)!=expected[offset:stop]: raise ValueError('complete internal preimage/readback differs')
                if name=='envelope' and stop==len(expected):
                    after = {address:port.read32(address) for address in META}
                    if after!=metadata: raise ValueError('Flash configuration drift during complete archive')
                self.seal(INTERNAL_READS)

    def pair(self,label,expected):
        self.phase_start(label.upper()+'_BCB_CAPTURE')
        port = self.words(gpio.READS,900,write_allowed=gpio.allowed_write)
        pins = gpio.Pins(port,self.pin_config,self.owner)
        pins.verify_idle()
        started = self.clock()
        self.native_guard(self.sleep,.006,seconds=min(5,self.left()-90))
        if self.clock()<started+.005: raise ValueError('EEPROM initial settlement wait returned early')
        wire = ReadPair(pins,clock=self.clock,sleep=self.sleep,emit=self.logs.emit)
        def after(index,address,raw):
            self.save(label+'-bcb',index*64,raw)
            self.seal(gpio.READS,eeprom_stores('read',address,size=64))
        raw = wire.capture(after)
        self.check()
        if raw!=expected: raise ValueError('complete stable BCB pair differs from expected phase')
        return raw

    def nor(self,label):
        self.phase_start(label.upper()+'_NOR_CAPTURE')
        results = []
        for name in REGIONS:
            capture = Capture(self.dap,name,self.assets[name],self.owner,self.logs,self.remaining,
                lambda name,offset,raw:self.archive(label+'-'+name,offset,raw),
                seconds=1800,reserve=1500,clock=self.clock,sleep=self.sleep,guard=self.native_guard)
            result = self.component(capture.run)
            self.check(1500)
            if result['result']!='NOR_REGION_CAPTURED_AUDITED' or not result['configuration_restored']:
                raise ValueError('NOR region capture did not finish audited/restored')
            results.append(result)
        self.results[label+'_nor'] = results

    def boot_and_health(self):
        if self.boot_used or not self.final_confirmed or not self.owner():
            raise ValueError('full final integrity and C confirmation required before Boot exit')
        self.boot_used = True
        self.phase_start('ORIGINAL_BOOT_RESET')
        def admit(phase):
            return self.final_confirmed and self.owner() and phase in ('before-reset','before-reset-store','before-release')
        def reset_guard(function,*args,seconds):
            return self.guard_for(self.exit_port.io)(function,*args,seconds=seconds)
        self.exit_port = Exit(self.dap,self.assets['boot'],admit,self.logs.emit,seconds=120,
                              clock=self.clock,sleep=self.sleep,guard=reset_guard)
        caught = self.exit_port.reset_and_catch()
        self.results['reset'] = caught
        if caught['result']!='FRESH_BOOT_CAUGHT' or not caught['release_allowed']:
            raise ValueError('fresh original-Boot catch uncertain')
        selectors = tuple((DCRSR,value) for value in (15,16,17,20))
        reset_stores = ((DFSR,8),(DEMCR,self.exit_port.original_demcr|1),(AIRCR,self.exit_port.aircr_value))+selectors
        self.seal(EXIT_READS,reset_stores)
        self.phase_start('ORIGINAL_BOOT_RELEASE')
        self.results['release'] = self.exit_port.release()
        self.released = True
        self.held = False
        self.seal(EXIT_READS,selectors+((DEMCR,self.exit_port.original_demcr),(DHCSR,0xa05f0001)))
        self.phase_start('R2_HEALTH')
        monitor = Monitor(self.dap,self.assets['image'],self.assets['map'],
            lambda:self.active and self.released and self.error is None,self.logs,self.remaining,
            clock=self.clock,sleep=self.sleep,guard=self.native_guard)
        self.results['health'] = monitor.run()
        self.index = self.logs.gate.index
        self.check()
        if self.index!=len(self.logs.gate.paths)-1:
            raise ValueError('body phase/log count differs from frozen plan')

    def run(self):
        if self.used: raise ValueError('complete installation cannot replay')
        self.used = self.active = True
        try:
            self.entry()
            self.internal('before')
            before = self.pair('before',self.assets['bcb'])
            self.plan = draft(self.function,before,self.assets['boot'],self.assets['image'])
            if self.plan.address!=0: raise ValueError('original C selected an unauthorized record')
            self.save('draft-a',0,self.plan.record)
            self.nor('before')
            self.results['preflash_state'] = self.state()
            self.phase_start('FLASH')
            self.flash_sequence = Sequence(self.dap,self.assets['image'],self.assets['envelope'],self.owner,
                self.logs.emit,self.logs,self.remaining,clock=self.clock,sleep=self.sleep,native_guard=self.native_guard)
            try: self.results['flash'] = self.component(self.flash_sequence.run)
            finally: self.app_may_have_changed |= self.flash_sequence.app_may_have_changed
            self.index = self.logs.gate.index
            if self.results['flash']['result']!='ALL_FLASH_SECTORS_AUDITED': raise ValueError('incomplete Flash sequence')
            self.after_app = True
            self.phase_start('EEPROM_CONFIRM')
            def archive_operation(index,kind,address,value):
                if kind=='read': self.archive('confirm-read-'+str(index),0,value)
            self.eeprom_wire = Wire(self.dap,self.pin_config,self.plan,self.owner,self.logs.emit,self.logs,
                self.remaining,archive_operation,clock=self.clock,sleep=self.sleep,guard=self.native_guard)
            transaction = Transaction(self.function,self.plan,self.eeprom_wire,clock=self.clock,sleep=self.sleep)
            confirmation = self.component(transaction.run)
            self.results['confirmation'] = confirmation
            self.index = self.logs.gate.index
            if (confirmation['result']!='EEPROM_BYTES_CONFIRMED' or confirmation['error'] is not None or
                    confirmation['pages']!=8 or not observe(self.function,self.plan,confirmation['after'])):
                raise ValueError('original C transaction not confirmed; no retry/reset')
            self.internal('after')
            self.nor('after')
            self.results['final_state'] = self.state()
            final = self.pair('after',self.plan.target*2)
            if not observe(self.function,self.plan,final): raise ValueError('final C observer rejected BCB')
            self.final_confirmed = True
            self.boot_and_health()
            self.phase = 'READY_FOR_FINAL_NATIVE_CLOSE'
            return dict(result=self.phase,app_may_have_changed=self.app_may_have_changed,
                        runtime_health_observed=True,final_native_close_audited=False,
                        historical_sdk_audit_passed=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise
        finally:
            self.active = False
