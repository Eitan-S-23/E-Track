"""Bounded fresh NOR archives through word/increment AP and bypassed XIP.

Reads SR1/SR2, never JEDEC FIFO, never sends a payload mutation opcode. This
does not repair the historical provisioning audit or establish package type.
"""
import hashlib
import math
import time

from recovery_entry import host_nor as hn
from recovery_entry.owner_probe import QSPI_REGS
from .native_io import Words, guarded

DHCSR, PAUSE, XIP3, MAPPED = 0xe000edf0, 0xe0042008, 0xa000103c, 0x90000000
REGIONS = {
    'candidate-backup': (0, 0x200000, 'c5a72cbf45608b25edcc5939ff8ac8fbbed25b970bb6e1d2830d2a50f36e1a48'),
    'recovery': (0x200000, 0x299000, '02e35c470eda1f44d3db3484574eab4d02a9da61e064ab54cef785b64f5e412d'),
    'tail': (0x299000, 0x300000, 'f0f4a7b280963efdd30890ab5b45ac0c23433dd54d93f11628c78ae8838c4d7e'),
    'staging': (0x300000, 0x500000, '2f4dccf87370e0f55e4e2ce968d27828e88bf48882fe67f7675fa53b9a909257'),
}
BLOCK = 32768


def status_stores():
    return tuple(item for opcode in (5,0x35) for item in (
        (hn.BASE,0), (hn.BASE+4,0x1000000), (hn.BASE+8,0), (hn.BASE+12,(opcode<<24)|0xc), (hn.CMDSTS,1)))


OPEN = ((hn.CTRL,hn.XIP|7),(hn.CTRL,7))+status_stores()+((XIP3,1),(hn.CTRL,hn.XIP|7))
CLOSE = ((hn.CTRL,7),)+status_stores()+((XIP3,0),(hn.CTRL,hn.XIP|7),(hn.CTRL,hn.XIP))


class Capture:
    def __init__(self,dap,name,expected,owner,logs,remaining,archive,*,seconds=1800,reserve=600,
                 clock=time.monotonic,sleep=time.sleep,guard=guarded):
        if name not in REGIONS:
            raise ValueError('unknown fixed NOR region')
        start,end,digest = REGIONS[name]
        if type(expected) is not bytes or len(expected)!=end-start or hashlib.sha256(expected).hexdigest()!=digest:
            raise ValueError('exact retained NOR region required')
        if type(reserve) not in (int,float) or not math.isfinite(reserve) or not 0 < reserve <= 7200:
            raise ValueError('finite downstream reserve required')
        self.dap,self.name,self.expected,self.start = dap,name,expected,start
        self.owner,self.logs,self.remaining,self.archive = owner,logs,remaining,archive
        self.reserve,self.native_guard,self.sleep = reserve,guard,sleep
        self.index = logs.gate.index
        self.previous_left = None
        self.used = self.active = self.sealing = self.restored = False
        self.error = None
        self.plan,self.position = (),0
        self.completed_bytes = 0
        self.completed_segments = 0
        if len(logs.gate.paths)-self.index < (len(expected)+BLOCK-1)//BLOCK+2:
            raise ValueError('preflighted NOR block/final/successor logs required')
        reads = {DHCSR,PAUSE,*QSPI_REGS.values(),*range(MAPPED+start,MAPPED+end,4)}
        self.words = Words(dap,logs.emit,reads=reads,write_allowed=self.allowed,
                           seconds=seconds,clock=clock,guard=self.bounded_call)
        self.boundary()
        self.fresh_head()

    def left(self):
        value = self.remaining()
        if (type(value) not in (int,float) or not math.isfinite(value) or not 0 < value <= 28800 or
                self.previous_left is not None and value > self.previous_left):
            raise ValueError('global NOR allowance invalid/nonmonotonic')
        self.previous_left = value
        return value

    def boundary(self):
        if (self.error is not None or self.logs.dap is not self.dap or self.owner() is not True or
                self.logs.target_allowed() is not True or self.logs.gate.index!=self.index or self.left()<=self.reserve):
            raise ValueError('NOR capture owner/log/reserve missing')
        self.words.check()

    def fresh_head(self):
        if self.index<=0 or self.logs.gate.boundary is None:
            raise ValueError('fresh accepted AP-only head required')
        self.native_guard(self.logs.verify_head,seconds=min(300,self.left()-self.reserve,self.words.budget.left()))
        self.boundary()

    def allowed(self,address,value):
        return (self.active and not self.sealing and self.position<len(self.plan) and
                self.plan[self.position]==(address,value))

    def bounded_call(self,function,*args,seconds):
        self.boundary()
        if not self.active or self.sealing: raise ValueError('NOR capture not active')
        self.words.budget.end = min(self.words.budget.end,self.words.budget.now()+self.left()-self.reserve)
        result = self.native_guard(function,*args,seconds=min(seconds,self.words.budget.left()))
        self.boundary()
        return result

    def held(self):
        self.boundary()
        if self.words.read32(DHCSR)&0x020a0000!=0x20000 or self.words.read32(PAUSE)!=0x1000:
            raise ValueError('lost held core/watchdog pause')

    def write(self,address,value):
        self.held()
        if not self.allowed(address,value): raise ValueError('NOR write differs from independent phase plan')
        self.words.write32(address,value)
        self.position += 1
        self.held()

    def wait(self,address,mask,value):
        for _ in range(32):
            self.held()
            if self.words.read32(address)&mask==value: return
            self.sleep(.001)
        raise ValueError('NOR status transition not observed')

    def transition(self,value):
        if self.words.read32(hn.CTRL)&(hn.IDLE|hn.ABORT)!=hn.IDLE or self.words.read32(hn.CTRL2)!=0:
            raise ValueError('NOR transition not idle/owned')
        self.write(hn.CTRL,value)
        self.wait(hn.CTRL,hn.ABORT|hn.XIP|7,value)
        if not self.words.read32(hn.CTRL)&hn.IDLE: raise ValueError('NOR transition lost idle')

    def status(self):
        for opcode,wanted in ((5,0),(0x35,2)):
            if (self.words.read32(hn.CTRL)!=hn.IDLE|7 or self.words.read32(hn.CTRL2)!=0 or
                    self.words.read32(hn.CMDSTS)!=0 or self.words.read32(hn.FIFO)!=1):
                raise ValueError('status read entry not settled')
            for address,value in status_stores()[:5] if opcode==5 else status_stores()[5:]:
                if address==hn.CMDSTS:
                    self.wait(hn.CMDSTS,1,1)
                    if self.words.read32(hn.RSTS)&0xff!=wanted:
                        raise ValueError('NOR busy/write-enabled/protected/quad state changed')
                self.write(address,value)
            if self.words.read32(hn.CMDSTS)!=0 or self.words.read32(hn.FIFO)!=1:
                raise ValueError('NOR status completion did not clear')

    def configuration(self):
        values = {key:self.words.read32(QSPI_REGS[key]) for key in hn.CONFIG}
        values['qspi_xip3'] &= ~8
        return values

    def bypass(self,value):
        if (self.words.read32(hn.CTRL)!=hn.IDLE|7 or self.words.read32(hn.CMDSTS)!=0 or
                self.words.read32(hn.CTRL2)!=0 or self.words.read32(XIP3)&~8!=1-value):
            raise ValueError('cache bypass phase changed')
        self.write(XIP3,value)
        if self.words.read32(XIP3)&~8!=value: raise ValueError('cache bypass readback mismatch')

    def seal(self):
        if self.position!=len(self.plan): raise ValueError('NOR phase store sequence incomplete')
        self.boundary()
        self.sealing = True
        trace = self.native_guard(lambda:self.logs.switch(read_allowed=lambda a:a in self.words.reads,
            expected_stores=self.plan),seconds=min(300,self.left()-self.reserve,self.words.budget.left()))
        if trace['target_writes']!=len(self.plan) or trace['native_close']!=0 or trace['log_file_closed']!=1:
            raise ValueError('NOR segment audit mismatch')
        self.index += 1
        self.completed_segments += 1
        self.sealing = False
        self.plan,self.position = (),0
        self.boundary()

    def run(self):
        if self.used: raise ValueError('NOR capture cannot replay')
        self.used = self.active = True
        try:
            self.held()
            original = self.configuration()
            if original!=hn.CONFIG: raise ValueError('unqualified initial QSPI profile')
            self.plan = OPEN
            self.transition(hn.XIP|7)
            self.transition(7)
            self.status()
            self.bypass(1)
            self.transition(hn.XIP|7)
            for offset in range(0,len(self.expected),BLOCK):
                end = min(offset+BLOCK,len(self.expected))
                raw = bytearray()
                for at in range(offset,end,1024):
                    self.held()
                    if (self.words.read32(hn.CTRL)!=hn.XIP|hn.IDLE|7 or self.words.read32(hn.CTRL2)!=0 or
                            self.words.read32(XIP3)&~8!=1):
                        raise ValueError('mapped read lacks bypassed /12 XIP')
                    chunk = self.words.read_bytes(MAPPED+self.start+at,min(1024,end-at))
                    self.held()
                    raw.extend(chunk)
                data = bytes(raw)
                self.native_guard(self.archive,self.name,offset,data,
                                  seconds=min(300,self.left()-self.reserve,self.words.budget.left()))
                self.boundary()
                if data!=self.expected[offset:end]: raise ValueError('fresh NOR archive differs from retained bytes')
                self.completed_bytes = end
                self.seal()
            self.plan = CLOSE
            self.transition(7)
            self.status()
            self.bypass(0)
            self.transition(hn.XIP|7)
            self.transition(hn.XIP)
            if self.configuration()!=original: raise ValueError('NOR passive configuration not restored')
            self.held()
            self.seal()
            self.restored = True
            self.logs.emit('nor-region-captured-audited',name=self.name,bytes=self.completed_bytes)
            self.boundary()
            return dict(result='NOR_REGION_CAPTURED_AUDITED',name=self.name,bytes=self.completed_bytes,
                        configuration_restored=True,nor_payload_writes=0,reset_allowed=False,
                        historical_sdk_audit_passed=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise
        finally:
            self.active = self.sealing = False
