"""Explicit R2-A/B health only; no device entry or whole-checkpoint authority.

The enclosing checkpoint must share a reset latch across every DHCSR consumer,
including this monitor's reset_seen, and supply owner=False once that latch sets.
"""
import hashlib
import math
import time

import p34_finalized_vtor_capture as binding
from . import r2_health as old


class Monitor(old.Monitor):
    def __init__(self,dap,image,map_bytes,owner,logs,remaining,*,seconds=240,reserve=90,
                 clock=time.monotonic,sleep=time.sleep,guard=old.guarded):
        if type(image) is not bytes or len(image)!=binding.IMAGE_BYTES:
            raise ValueError('exact paired R2 bytes required')
        digest=hashlib.sha256(image).hexdigest()
        if digest not in binding.PLANNED:raise ValueError('unknown paired R2 image')
        binding.policy.sources.verify(image)
        self.version=int.from_bytes(image[0x408:0x40c],'little')
        if self.version!=binding.PLANNED[digest]:raise ValueError('R2 version/hash pair differs')
        old.verify_map(map_bytes)
        if type(reserve) not in (int,float) or not math.isfinite(reserve) or not 60<=reserve<=600:
            raise ValueError('explicit normal-close reserve required')
        self.dap,self.image,self.owner,self.logs,self.remaining=dap,image,owner,logs,remaining
        self.reserve,self.native_guard,self.sleep=reserve,guard,sleep
        self.previous_left=None
        self.index=logs.gate.index
        self.used=self.active=self.reset_seen=False
        self.error=None
        self.samples=[]
        self.words=old.Words(dap,logs.emit,reads=old.READS,write_allowed=lambda a,v:False,
                             seconds=seconds,clock=clock,guard=self.bounded_call)
        self.boundary()
        if self.index<=0 or logs.gate.boundary is None or len(logs.gate.paths)-self.index<2:
            raise ValueError('sealed checkpoint handoff and successor log required')
        self.native_guard(logs.verify_head,seconds=min(60,self.left()-reserve,self.words.budget.left()))
        self.boundary()

    def running(self):
        status=self.words.read32(old.DHCSR)
        self.reset_seen|=bool(status&0x02000000)
        if self.reset_seen or status&0x000a0000:
            raise ValueError('reset/halt/lockup during paired R2 observation')
        if self.words.read32(old.CFSR) or self.words.read32(old.HFSR):
            raise ValueError('R2 fault status is not clear')

    def run(self):
        if self.used:raise ValueError('paired R2 monitor cannot replay')
        self.used=self.active=True
        try:
            readiness_end=self.words.budget.now()+120
            while True:
                if self.words.budget.now()>=readiness_end:raise ValueError('R2 runtime readiness timeout')
                row=self.sample()
                if self.words.budget.now()>=readiness_end:raise ValueError('R2 runtime readiness timeout')
                if row['ready']:break
                self.pause()
            self.identity()
            self.samples.append(row)
            while self.words.budget.now()-self.samples[0]['ended']<30:
                self.pause()
                row=self.sample();previous=self.samples[-1]
                if not row['ready'] or row['health'][3]!=previous['health'][3]:
                    raise ValueError('R2 ready state/health epoch changed')
                elapsed=row['ended']-previous['ended']
                tick=(row['tick']-previous['tick'])&0xffffffff
                loops=(row['health'][4]-previous['health'][4])&0xffffffff
                feeds=(row['health'][5]-previous['health'][5])&0xffffffff
                if not 500*elapsed<=tick<=2000*elapsed or not 0<loops<0x80000000 or not 0<feeds<0x80000000:
                    raise ValueError('R2 time/main-loop/watchdog progress missing')
                self.samples.append(row)
            self.identity()
            duration=self.samples[-1]['ended']-self.samples[0]['ended']
            if duration<30 or len(self.samples)<20:raise ValueError('full stable observation window missing')
            self.active=False
            trace=self.native_guard(lambda:self.logs.switch(read_allowed=lambda a:a in old.READS,expected_stores=[]),
                seconds=min(60,self.left()-self.reserve,self.words.budget.left()))
            self.index+=1
            self.boundary()
            if trace['target_writes'] or trace['native_close'] or trace['log_file_closed']!=1:
                raise ValueError('paired health audit differs from read-only phase')
            return dict(result='R2_RUNTIME_HEALTH_OBSERVED',seconds=duration,samples=len(self.samples),
                version_code=self.version,image_sha256=hashlib.sha256(self.image).hexdigest(),reset_seen=self.reset_seen,
                full_install_qualified=False,eeprom_observed=False,backup_observed=False)
        except BaseException as error:
            if self.error is None:self.error=type(error).__name__+': '+str(error)
            raise
        finally:self.active=False
