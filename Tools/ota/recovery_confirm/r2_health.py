"""Read-only, exact-R2 runtime observation after externally proven Boot release."""
import hashlib
import math
import re
import time

from .native_io import Words, guarded
from .flash_plan import geometry

MAP_SHA = '969986b60b92663feb48cb4e32579bb2d791c2c16a0ce1497392fbb02b5705d8'
SYMBOLS = {
    'SystemTickCount': (0x20004440,4),
    '_ZL20g_ota_state_snapshot': (0x20053a98,1),
    '_ZL19g_ota_state_snapped': (0x20053a99,1),
    '_ZL18g_ota_confirm_done': (0x20053a9a,1),
    '_ZL12g_ota_health': (0x20053a9c,36),
    '_ZL10SD_IsReady': (0x20052ddc,1),
    '_ZL18s_faultHandleReady': (0x20052d48,1),
    'on_fault': (0x200039d9,1),
}
DHCSR,VTOR,CFSR,HFSR = 0xe000edf0,0xe000ed08,0xe000ed28,0xe000ed2c
PRIMARY,RUNTIME = 0x08010000,0x08010800
TICK,FLAGS,HEALTH,SD,DIAG,FAULT = (0x20004440,0x20053a98,0x20053a9c,0x20052ddc,0x20052d48,0x200039d8)
READS = {DHCSR,VTOR,CFSR,HFSR,TICK,FLAGS,SD,DIAG,FAULT,*range(HEALTH,HEALTH+36,4),
         *range(PRIMARY+0x400,PRIMARY+0x460,4),*range(RUNTIME,RUNTIME+524,4)}


def verify_map(raw):
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest()!=MAP_SHA:
        raise ValueError('exact source-bound R2 map required')
    text = raw.decode('utf-8')
    for symbol,wanted in SYMBOLS.items():
        matches = re.findall(r'^ \.bss\.'+re.escape(symbol)+r'\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s',text,re.M)
        if len(matches)!=1 or tuple(int(x,16) for x in matches[0])!=wanted:
            raise ValueError('R2 diagnostic symbol/size differs: '+symbol)


class Monitor:
    def __init__(self,dap,image,map_bytes,owner,logs,remaining,*,seconds=240,reserve=90,
                 clock=time.monotonic,sleep=time.sleep,guard=guarded):
        geometry(image)
        verify_map(map_bytes)
        if type(reserve) not in (int,float) or not math.isfinite(reserve) or not 60<=reserve<=600:
            raise ValueError('explicit normal-close reserve required')
        self.dap,self.image,self.owner,self.logs,self.remaining = dap,image,owner,logs,remaining
        self.reserve,self.native_guard,self.sleep = reserve,guard,sleep
        self.previous_left = None
        self.index = logs.gate.index
        self.used = self.active = False
        self.error = None
        self.samples = []
        self.words = Words(dap,logs.emit,reads=READS,write_allowed=lambda a,v:False,
                           seconds=seconds,clock=clock,guard=self.bounded_call)
        self.boundary()
        if self.index<=0 or self.logs.gate.boundary is None or len(logs.gate.paths)-self.index<2:
            raise ValueError('separately sealed Boot release and successor log required')
        self.native_guard(logs.verify_head,seconds=min(60,self.left()-reserve,self.words.budget.left()))
        self.boundary()

    def left(self):
        value = self.remaining()
        if (type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=28800 or
                self.previous_left is not None and value>self.previous_left):
            raise ValueError('global health allowance invalid/nonmonotonic')
        self.previous_left = value
        return value

    def boundary(self):
        if (self.error is not None or self.dap is not self.logs.dap or self.owner() is not True or
                not self.logs.target_allowed() or self.logs.gate.index!=self.index or self.left()<=self.reserve):
            raise ValueError('health owner/log/reserve missing')
        self.words.check()

    def bounded_call(self,function,*args,seconds):
        self.boundary()
        if not self.active: raise ValueError('health collection not active')
        self.words.budget.end = min(self.words.budget.end,self.words.budget.now()+self.left()-self.reserve)
        result = self.native_guard(function,*args,seconds=min(seconds,self.words.budget.left()))
        self.boundary()
        return result

    def running(self):
        status = self.words.read32(DHCSR)
        if status&0x020a0000:
            raise ValueError('reset/halt/lockup during R2 observation')
        if self.words.read32(CFSR) or self.words.read32(HFSR):
            raise ValueError('R2 fault status is not clear')

    def sample(self):
        self.running()
        phase = self.words.read32(VTOR)
        if phase not in (0,0x08000000,PRIMARY,RUNTIME):
            raise ValueError('unrelated Boot/App vector phase')
        row = dict(started=self.words.budget.now(),vtor=phase,ready=False)
        if phase==RUNTIME:
            values = [self.words.read32(a) for a in range(HEALTH,HEALTH+36,4)]
            flags = self.words.read32(FLAGS)&0xffffff
            sd,diag = (self.words.read32(a)&255 for a in (SD,DIAG))
            fault_word = self.words.read32(FAULT)
            if fault_word&0xffff:
                raise ValueError('backtrace fault or stack overflow observed')
            if values[:3]!=[30000,30,1000] or values[7]!=1 or values[8] not in (0,1):
                raise ValueError('R2 health structure not initialized/coherent')
            row.update(health=values,flags=flags,sd=sd,diagnostics=diag,tick=self.words.read32(TICK),
                       ready=values[8]==1 and flags==0x010104 and sd==diag==1)
        self.running()
        if self.words.read32(VTOR)!=phase:
            # A transitional sample is not reused as the start of stable health.
            row['ready'] = False
        row['ended'] = self.words.budget.now()
        self.logs.emit('r2-health-sample',**row)
        self.boundary()
        return row

    def identity(self):
        self.running()
        if self.words.read32(VTOR)!=RUNTIME: raise ValueError('R2 runtime VTOR absent')
        if (self.words.read_bytes(PRIMARY+0x400,96)!=self.image[0x400:0x460] or
                self.words.read_bytes(RUNTIME,524)!=self.image[0x800:0x800+524]):
            raise ValueError('R2 runtime table/header differs')
        self.running()
        if self.words.read32(VTOR)!=RUNTIME: raise ValueError('R2 VTOR changed during identity read')

    def pause(self):
        start = self.words.budget.now()
        self.native_guard(self.sleep,1.,seconds=min(2,self.left()-self.reserve,self.words.budget.left()))
        if self.words.budget.now()<start+1.: raise ValueError('health sleep returned early')
        self.boundary()

    def run(self):
        if self.used: raise ValueError('health monitor cannot replay')
        self.used = self.active = True
        try:
            start = self.words.budget.now()
            readiness_end = start+120
            while True:
                if self.words.budget.now()>=readiness_end: raise ValueError('R2 runtime readiness timeout')
                row = self.sample()
                if self.words.budget.now()>=readiness_end: raise ValueError('R2 runtime readiness timeout')
                if row['ready']: break
                self.pause()
            self.identity()
            self.samples.append(row)
            while self.words.budget.now()-self.samples[0]['ended']<30:
                self.pause()
                row = self.sample()
                previous = self.samples[-1]
                if not row['ready'] or row['health'][3]!=previous['health'][3]:
                    raise ValueError('R2 ready state/health epoch changed')
                elapsed = row['ended']-previous['ended']
                tick = (row['tick']-previous['tick'])&0xffffffff
                loops = (row['health'][4]-previous['health'][4])&0xffffffff
                feeds = (row['health'][5]-previous['health'][5])&0xffffffff
                if not 500*elapsed<=tick<=2000*elapsed or not 0<loops<0x80000000 or not 0<feeds<0x80000000:
                    raise ValueError('R2 time/main-loop/watchdog progress missing')
                self.samples.append(row)
            self.identity()
            duration = self.samples[-1]['ended']-self.samples[0]['ended']
            if duration<30 or len(self.samples)<20: raise ValueError('full stable observation window missing')
            self.active = False
            trace = self.native_guard(lambda:self.logs.switch(read_allowed=lambda a:a in READS,expected_stores=[]),
                seconds=min(60,self.left()-self.reserve,self.words.budget.left()))
            self.index += 1
            self.boundary()
            if trace['target_writes'] or trace['native_close'] or trace['log_file_closed']!=1:
                raise ValueError('health audit differs from read-only phase')
            return dict(result='R2_RUNTIME_HEALTH_OBSERVED',seconds=duration,samples=len(self.samples),
                        version_code=30276,full_install_qualified=False,eeprom_observed=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise
        finally:
            self.active = False
