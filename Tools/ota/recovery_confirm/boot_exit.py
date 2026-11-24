"""Fresh Boot reset/catch/release capability. Requires supervisor admission; no CLI."""
import hashlib
import time

from .native_io import Words

DHCSR,DCRSR,DCRDR = 0xe000edf0,0xe000edf4,0xe000edf8
AIRCR,DEMCR,DFSR,VTOR,PAUSE = 0xe000ed0c,0xe000edfc,0xe000ed30,0xe000ed08,0xe0042008
BOOT_SHA = 'a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4'
READS = (DHCSR,DCRDR,AIRCR,DEMCR,DFSR,VTOR,PAUSE,0,4,0x08000000,0x08000004)


class Exit:
    def __init__(self,dap,boot,admit,emit,*,seconds=60,clock=time.monotonic,sleep=time.sleep,guard=None):
        if type(boot) is not bytes or len(boot)!=65536 or hashlib.sha256(boot).hexdigest()!=BOOT_SHA:
            raise ValueError('exact original whole Boot required')
        self.boot,self.admit,self.emit,self.sleep = boot,admit,emit,sleep
        self.expected_write = None
        self.kwargs = {} if guard is None else dict(guard=guard)
        self.io = Words(dap,emit,reads=READS,write_allowed=self.allowed,seconds=seconds,clock=clock,**self.kwargs)
        self.deadline = self.io.budget.end
        self.reset_attempted = self.release_attempted = self.caught = False
        self.reset_seen = self.reset_uncertain = False
        self.original_demcr = None
        self.error = None
        self.context = None
        self.aircr_value = None
        self.releasing = False
        self.aircr_writes = self.release_writes = 0

    def allowed(self,address,value):
        if self.expected_write != (address,value): return False
        if address == DCRSR: return self.reset_seen and value in (15,16,17,20)
        if self.reset_uncertain: return False
        if address == DFSR: return not self.reset_attempted and value == 8
        if address == DEMCR:
            return self.original_demcr is not None and ((not self.reset_attempted and value == self.original_demcr|1) or
                                                        (self.releasing and value == self.original_demcr))
        if address == AIRCR: return self.reset_attempted and not self.caught and value == self.aircr_value
        if address == DHCSR: return self.caught and self.release_attempted and value == 0xa05f0001
        return False

    def admission(self,phase):
        self.io.check()
        if self.admit(phase) is not True:
            raise ValueError('complete-state supervisor admission missing')
        self.io.check()

    def write(self,address,value):
        if address == AIRCR:
            if self.aircr_writes: raise ValueError('AIRCR store already consumed')
            self.aircr_writes += 1
        if address == DHCSR:
            if self.release_writes: raise ValueError('release store already consumed')
            self.release_writes += 1
        self.expected_write = (address,value)
        try:
            self.io.write32(address,value)
        finally:
            self.expected_write = None

    def held(self,*,after=False):
        status = self.io.read32(DHCSR)
        if status & 0x020a0000 != 0x20000 or status & 0x0c or not status & 1:
            raise ValueError('known held core changed/reset/lockup/step/mask')
        if not self.io.read32(PAUSE) & 0x1000:
            raise ValueError('watchdog halt pause missing')
        if after and not self.reset_seen:
            raise ValueError('no new observed reset')
        return status

    def core(self,selector):
        if type(selector) is not int or selector not in (15,16,17,20):
            raise ValueError('read-only core selector scope')
        self.held(after=True)
        self.write(DCRSR,selector)
        for _ in range(16):
            if self.held(after=True) & 0x10000:
                return self.io.read32(DCRDR)
        raise ValueError('core register read timeout')

    def verify_catch(self):
        self.held(after=True)
        if not self.io.read32(DFSR) & 8:
            raise ValueError('fresh reset vector catch absent')
        pc,xpsr,msp,special = (self.core(i) for i in (15,16,17,20))
        expected_sp = int.from_bytes(self.boot[:4],'little')
        expected_pc = int.from_bytes(self.boot[4:8],'little')
        if (pc != expected_pc & ~1 or msp != expected_sp or not xpsr & 0x1000000 or
                xpsr & 0x1ff or special != 0):
            raise ValueError('not fresh original Boot reset context')
        if self.io.read32(VTOR) != 0:
            raise ValueError('reset vector base is not architectural reset value')
        for origin in (0,0x08000000):
            if self.io.read32(origin) != expected_sp or self.io.read32(origin+4) != expected_pc:
                raise ValueError('reset alias/Boot vector identity differs')
        self.held(after=True)
        return dict(pc=pc,xpsr=xpsr,msp=msp,special=special)

    def reset_and_catch(self):
        try:
            if self.reset_attempted or self.error is not None:
                raise ValueError('reset capability consumed/failed')
            self.admission('before-reset')
            self.held()
            self.original_demcr = self.io.read32(DEMCR)
            if self.original_demcr & 1:
                raise ValueError('preexisting vector catch not owned')
            self.write(DFSR,8)
            if self.io.read32(DFSR) & 8:
                raise ValueError('stale vector catch not cleared')
            self.write(DEMCR,self.original_demcr|1)
            if self.io.read32(DEMCR) != self.original_demcr|1:
                raise ValueError('reset vector catch not armed')
            aircr = self.io.read32(AIRCR)
            self.held()
            self.admission('before-reset-store')
            self.reset_attempted = True
            self.aircr_value = 0x05fa0004|(aircr&0x700)
            try:
                self.write(AIRCR,self.aircr_value)
            except (OSError,ValueError) as error:
                # Preserve the failed store and use a new observation-only phase.
                # Its only possible target writes are read-register selectors.
                self.reset_uncertain = True
                self.error = type(error).__name__+': '+str(error)
                old = self.io
                left = self.deadline-old.budget.now()
                self.io = Words(old.dap,self.emit,reads=READS,write_allowed=self.allowed,
                                seconds=left,clock=old.budget.clock,**self.kwargs)
            end = min(self.deadline,self.io.budget.now()+10)
            while True:
                status = self.io.read32(DHCSR)
                self.reset_seen |= bool(status & 0x02000000)
                if self.io.budget.now() >= end:
                    raise ValueError('fresh reset/catch not observed within deadline')
                if self.reset_seen and not status & 0x02000000 and status & 0x20000:
                    break
                self.sleep(.001)
            self.context = self.verify_catch()
            self.caught = True
            return dict(result='RESET_CAUGHT_DELIVERY_UNCERTAIN' if self.reset_uncertain else 'FRESH_BOOT_CAUGHT',
                        context=self.context,release_allowed=not self.reset_uncertain)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise

    def release(self):
        if not self.caught or self.reset_uncertain or self.release_attempted or self.error is not None:
            raise ValueError('fresh proven Boot catch required; no retry')
        try:
            self.admission('before-release')
            if self.verify_catch() != self.context:
                raise ValueError('Boot catch context changed')
            if self.io.read32(DEMCR) != self.original_demcr|1:
                raise ValueError('vector catch configuration changed')
            self.releasing = True
            self.write(DEMCR,self.original_demcr)
            if self.io.read32(DEMCR) != self.original_demcr:
                raise ValueError('owned DEMCR restore failed')
            self.held(after=True)
            self.release_attempted = True
            self.write(DHCSR,0xa05f0001)
            return dict(result='FRESH_BOOT_RELEASE_STORE_RETURNED',runtime_health_verified=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise
